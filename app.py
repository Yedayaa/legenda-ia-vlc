# -*- coding: utf-8 -*-
from __future__ import annotations

import gc
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
import traceback
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Sequence

import tkinter as tk
from tkinter import filedialog, messagebox, ttk


APP_NAME = "Legenda IA para VLC"
APP_VERSION = "1.5.0"
TRANSLATION_MODEL = "Helsinki-NLP/opus-mt-tc-big-en-pt"
TRANSLATION_TARGET_TOKEN = ">>pob<<"
CHUNK_SECONDS = 300
CHUNK_OVERLAP_SECONDS = 12.0
CHUNK_GUARD_SECONDS = 6.0
TEMP_PREFIX = "legenda-ia-"
VIDEO_TYPES = (
    ("Vídeos", "*.mkv *.mp4 *.avi *.mov *.webm *.m4v *.ts *.mpeg *.mpg"),
    ("Todos os arquivos", "*.*"),
)


def configure_process_streams() -> Path:
    """Give GUI-only Python a writable stream for model download progress."""
    runtime_dir = Path(tempfile.gettempdir()) / "LegendaIAVLC"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    log_path = runtime_dir / "app.log"
    if sys.stdout is None or sys.stderr is None:
        stream = log_path.open("a", encoding="utf-8", buffering=1)
        if sys.stdout is None:
            sys.stdout = stream
        if sys.stderr is None:
            sys.stderr = stream
    return log_path


def verify_output_location(output_path: Path) -> None:
    try:
        with tempfile.NamedTemporaryFile(
            dir=output_path.parent,
            prefix=".legenda-ia-teste-",
            delete=True,
        ):
            pass
    except OSError as exc:
        raise RuntimeError(
            "O aplicativo não consegue gravar na pasta do vídeo. "
            "Mova o vídeo para uma pasta comum, como Vídeos ou Downloads."
        ) from exc


def cleanup_stale_temp_dirs(max_age_hours: int = 24) -> None:
    temp_root = Path(tempfile.gettempdir())
    cutoff = time.time() - max_age_hours * 3600
    for path in temp_root.glob(f"{TEMP_PREFIX}*"):
        try:
            if path.is_dir() and path.stat().st_mtime < cutoff:
                shutil.rmtree(path, ignore_errors=True)
        except OSError:
            continue


def missing_runtime_dependencies() -> list[str]:
    dependencies = (
        ("torch", "PyTorch"),
        ("whisper", "Whisper"),
        ("transformers", "Transformers"),
        ("sentencepiece", "SentencePiece"),
        ("imageio_ffmpeg", "FFmpeg"),
    )
    return [
        label
        for module_name, label in dependencies
        if importlib.util.find_spec(module_name) is None
    ]


class CancelledError(RuntimeError):
    pass


@dataclass(frozen=True)
class Caption:
    start: float
    end: float
    text: str


@dataclass(frozen=True)
class AudioChunk:
    path: Path
    start: float
    duration: float


@dataclass(frozen=True)
class AudioStream:
    index: int
    language: str | None


def clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    return text


def prepare_translation_inputs(texts: Sequence[str]) -> list[str]:
    return [f"{TRANSLATION_TARGET_TOKEN} {text}" for text in texts]


def brazilianize(text: str) -> str:
    """Apply only conservative PT-PT -> PT-BR vocabulary substitutions."""
    replacements = {
        r"\bficheiros\b": "arquivos",
        r"\bficheiro\b": "arquivo",
        r"\becrãs\b": "telas",
        r"\becrã\b": "tela",
        r"\btelemóveis\b": "celulares",
        r"\btelemóvel\b": "celular",
        r"\bautocarros\b": "ônibus",
        r"\bautocarro\b": "ônibus",
        r"\bcomboios\b": "trens",
        r"\bcomboio\b": "trem",
        r"\bpeões\b": "pedestres",
        r"\bpeão\b": "pedestre",
        r"\braparigas\b": "garotas",
        r"\brapariga\b": "garota",
        r"\bgajos\b": "caras",
        r"\bgajo\b": "cara",
        r"\bequipas\b": "equipes",
        r"\bequipa\b": "equipe",
        r"\bgolos\b": "gols",
        r"\bgolo\b": "gol",
        r"\bdesportos\b": "esportes",
        r"\bdesporto\b": "esporte",
        r"\bpequeno-almoço\b": "café da manhã",
        r"\bcasa de banho\b": "banheiro",
        r"\bfrigorífico\b": "geladeira",
        r"\bpalhinha\b": "canudo",
        r"\bchávena\b": "xícara",
        r"\bdecerto\b": "com certeza",
        r"\bde certeza\b": "com certeza",
        r"\bfactos\b": "fatos",
        r"\bfacto\b": "fato",
        r"\bcontactos\b": "contatos",
        r"\bcontacto\b": "contato",
        r"\bacção\b": "ação",
        r"\bóptimo\b": "ótimo",
        r"\bóptima\b": "ótima",
    }
    for pattern, replacement in replacements.items():
        def preserve_case(match: re.Match[str]) -> str:
            source = match.group(0)
            if source.isupper():
                return replacement.upper()
            if source[:1].isupper():
                return replacement[:1].upper() + replacement[1:]
            return replacement

        text = re.sub(pattern, preserve_case, text, flags=re.IGNORECASE)
    return clean_text(text)


def format_timestamp(seconds: float) -> str:
    millis = max(0, round(seconds * 1000))
    hours, millis = divmod(millis, 3_600_000)
    minutes, millis = divmod(millis, 60_000)
    secs, millis = divmod(millis, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _wrapped_lines(text: str, line_width: int = 42) -> list[str]:
    return textwrap.wrap(
        text,
        width=line_width,
        break_long_words=False,
        break_on_hyphens=False,
    )


def _chunk_words(
    text: str,
    max_chars: int = 84,
    line_width: int = 42,
) -> list[str]:
    words = text.split()
    if not words:
        return []

    chunks: list[str] = []
    current: list[str] = []
    for word in words:
        candidate = " ".join((*current, word))
        too_long = len(candidate) > max_chars
        too_many_lines = len(_wrapped_lines(candidate, line_width)) > 2
        if current and (too_long or too_many_lines):
            chunks.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        chunks.append(" ".join(current))
    return chunks


def _wrap_two_lines(text: str, line_width: int = 42) -> str:
    return "\n".join(_wrapped_lines(text, line_width))


def captions_from_segment(start: float, end: float, text: str) -> list[Caption]:
    text = clean_text(text)
    chunks = _chunk_words(text)
    if not chunks:
        return []

    duration = max(0.25, end - start)
    weights = [max(1, len(chunk)) for chunk in chunks]
    total_weight = sum(weights)
    cursor = start
    captions: list[Caption] = []

    for index, (chunk, weight) in enumerate(zip(chunks, weights)):
        if index == len(chunks) - 1:
            chunk_end = max(cursor + 0.25, end)
        else:
            chunk_end = cursor + duration * (weight / total_weight)
        captions.append(Caption(cursor, chunk_end, _wrap_two_lines(chunk)))
        cursor = chunk_end
    return captions


def render_srt(captions: Iterable[Caption]) -> str:
    blocks = []
    for index, caption in enumerate(captions, start=1):
        blocks.append(
            f"{index}\n"
            f"{format_timestamp(caption.start)} --> {format_timestamp(caption.end)}\n"
            f"{caption.text}\n"
        )
    return "\n".join(blocks)


def write_srt_atomic(output_path: Path, content: str) -> None:
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8-sig",
            newline="\n",
            dir=output_path.parent,
            prefix=f".{output_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary.write(content)
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary_path = Path(temporary.name)
        os.replace(temporary_path, output_path)
        temporary_path = None
    except OSError as exc:
        raise RuntimeError(
            "Não foi possível salvar a legenda ao lado do vídeo. "
            "Verifique se a pasta permite gravação."
        ) from exc
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def find_vlc() -> Path | None:
    candidates: list[Path] = []
    saved_path_file = Path(tempfile.gettempdir()) / "LegendaIAVLC" / "vlc-path.txt"
    try:
        saved_path = Path(saved_path_file.read_text(encoding="utf-8").strip())
        candidates.append(saved_path)
    except OSError:
        pass
    for variable in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
        base = os.environ.get(variable)
        if base:
            candidates.append(Path(base) / "VideoLAN" / "VLC" / "vlc.exe")
    found = shutil.which("vlc") or shutil.which("vlc.exe")
    if found:
        candidates.insert(0, Path(found))
    return next((path for path in candidates if path.is_file()), None)


def remember_vlc(path: Path) -> None:
    runtime_dir = Path(tempfile.gettempdir()) / "LegendaIAVLC"
    try:
        runtime_dir.mkdir(parents=True, exist_ok=True)
        (runtime_dir / "vlc-path.txt").write_text(str(path), encoding="utf-8")
    except OSError:
        pass


def hidden_subprocess_options() -> dict[str, int]:
    if os.name == "nt":
        return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}
    return {}


def is_english_language(language: str | None) -> bool:
    if not language:
        return False
    normalized = language.strip().lower().replace("_", "-")
    return normalized in {"eng", "english"} or normalized.split("-", 1)[0] == "en"


def choose_audio_stream_from_ffmpeg_output(output: str) -> AudioStream | None:
    pattern = re.compile(
        r"Stream #0:(?P<index>\d+)"
        r"(?:\[[^\]]+\])?"
        r"(?:\((?P<language>[^)]+)\))?:\s*Audio:",
        flags=re.IGNORECASE,
    )
    streams: list[AudioStream] = []
    for match in pattern.finditer(output):
        language = match.group("language")
        streams.append(
            AudioStream(
                index=int(match.group("index")),
                language=language.lower() if language else None,
            )
        )
    if not streams:
        return None
    return next(
        (stream for stream in streams if is_english_language(stream.language)),
        streams[0],
    )


def detect_audio_stream(ffmpeg: Path, video_path: Path) -> AudioStream:
    completed = subprocess.run(
        [str(ffmpeg), "-nostdin", "-hide_banner", "-i", str(video_path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        **hidden_subprocess_options(),
    )
    stream = choose_audio_stream_from_ffmpeg_output(completed.stderr)
    if stream is None:
        raise RuntimeError("O vídeo não possui uma faixa de áudio compatível.")
    return stream


def ensure_ffmpeg() -> Path:
    import imageio_ffmpeg

    source = Path(imageio_ffmpeg.get_ffmpeg_exe())
    runtime_dir = Path(tempfile.gettempdir()) / "LegendaIAVLC"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    destination = runtime_dir / "ffmpeg.exe"

    if not destination.exists() or destination.stat().st_size != source.stat().st_size:
        shutil.copy2(source, destination)

    os.environ["PATH"] = str(runtime_dir) + os.pathsep + os.environ.get("PATH", "")
    return destination


def ffmpeg_has_feature(ffmpeg: Path, listing_option: str, feature: str) -> bool:
    """Check an FFmpeg capability without depending on localized output."""
    completed = subprocess.run(
        [str(ffmpeg), "-hide_banner", listing_option],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        **hidden_subprocess_options(),
    )
    output = completed.stdout + "\n" + completed.stderr
    return re.search(rf"(?<![\w-]){re.escape(feature)}(?![\w-])", output) is not None


def parse_media_duration(output: str) -> float | None:
    match = re.search(
        r"Duration:\s*(\d+):(\d+):(\d+(?:[.,]\d+)?)",
        output,
        flags=re.IGNORECASE,
    )
    if match is None:
        return None
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds.replace(",", "."))


def probe_media_duration(ffmpeg: Path, video_path: Path) -> float:
    completed = subprocess.run(
        [str(ffmpeg), "-nostdin", "-hide_banner", "-i", str(video_path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        **hidden_subprocess_options(),
    )
    duration = parse_media_duration(completed.stderr)
    if duration is None or duration <= 0:
        raise RuntimeError("Não foi possível medir a duração do vídeo.")
    return duration


def parse_progress_time(value: str) -> float | None:
    match = re.fullmatch(r"(\d+):(\d+):(\d+(?:\.\d+)?)", value.strip())
    if match is None:
        return None
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def tv_video_output_path(video_path: Path) -> Path:
    return video_path.with_name(f"{video_path.stem}.legendado-PT-BR.mp4")


def build_tv_video_command(
    ffmpeg: Path,
    video_path: Path,
    temporary_output: Path,
    audio_stream_index: int,
    use_nvenc: bool,
) -> list[str]:
    # The worker runs inside a temporary folder containing only "subtitle.srt".
    # This avoids FFmpeg filter escaping bugs with Windows drive letters and accents.
    subtitle_filter = (
        "scale=trunc(iw/2)*2:trunc(ih/2)*2,"
        "subtitles=subtitle.srt:charenc=UTF-8:"
        "force_style='FontName=Arial,FontSize=22,Outline=2,Shadow=1,MarginV=26'"
    )
    if use_nvenc:
        video_codec = [
            "-c:v",
            "h264_nvenc",
            "-preset",
            "p5",
            "-rc",
            "vbr",
            "-cq",
            "20",
            "-b:v",
            "0",
        ]
    else:
        video_codec = [
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "20",
        ]
    return [
        str(ffmpeg),
        "-nostdin",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-stats_period",
        "0.5",
        "-i",
        str(video_path),
        "-map",
        "0:V:0",
        "-map",
        f"0:{audio_stream_index}",
        "-vf",
        subtitle_filter,
        *video_codec,
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-map_metadata",
        "0",
        "-map_chapters",
        "0",
        "-movflags",
        "+faststart",
        "-progress",
        "pipe:1",
        "-nostats",
        str(temporary_output),
    ]


def run_tv_video_command(
    command: Sequence[str],
    working_directory: Path,
    duration: float,
    processor_name: str,
    status: Callable[[str, float], None],
    cancel_event: threading.Event,
) -> None:
    process = subprocess.Popen(
        list(command),
        cwd=working_directory,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        **hidden_subprocess_options(),
    )
    output_tail: list[str] = []
    last_progress = -1
    assert process.stdout is not None
    try:
        for raw_line in process.stdout:
            if cancel_event.is_set():
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                raise CancelledError("Processamento cancelado.")

            line = raw_line.strip()
            if line.startswith("out_time="):
                elapsed = parse_progress_time(line.partition("=")[2])
                if elapsed is not None:
                    progress = min(98, max(0, round(elapsed / duration * 98)))
                    if progress != last_progress:
                        status(
                            f"Criando vídeo legendado na {processor_name}…",
                            float(progress),
                        )
                        last_progress = progress
            elif line and not re.match(
                r"^(frame|fps|stream_\d+_\d+_q|bitrate|total_size|"
                r"out_time_(?:us|ms)|dup_frames|drop_frames|speed|progress)=",
                line,
            ):
                output_tail.append(line)
                output_tail = output_tail[-40:]
        return_code = process.wait()
    finally:
        process.stdout.close()

    if cancel_event.is_set():
        raise CancelledError("Processamento cancelado.")
    if return_code != 0:
        detail = "\n".join(output_tail).strip()
        raise RuntimeError(detail or "O FFmpeg não conseguiu criar o vídeo.")


def create_tv_video(
    video_path: Path,
    subtitle_path: Path,
    output_path: Path,
    force_cpu: bool,
    status: Callable[[str, float], None],
    cancel_event: threading.Event,
) -> None:
    if not video_path.is_file():
        raise RuntimeError("O vídeo selecionado não foi encontrado.")
    if not subtitle_path.is_file():
        raise RuntimeError("A legenda PT-BR ainda não foi criada.")
    try:
        if video_path.resolve() == output_path.resolve():
            raise RuntimeError("Escolha outro nome para preservar o vídeo original.")
    except OSError:
        pass

    verify_output_location(output_path)
    status("Verificando o conversor de vídeo…", 0.0)
    ffmpeg = ensure_ffmpeg()
    if not ffmpeg_has_feature(ffmpeg, "-filters", "subtitles"):
        raise RuntimeError(
            "O FFmpeg instalado não possui suporte para incorporar legendas. "
            "Execute instalar.bat novamente para atualizar os componentes."
        )
    if not ffmpeg_has_feature(ffmpeg, "-encoders", "libx264"):
        raise RuntimeError(
            "O FFmpeg instalado não possui o codificador H.264 necessário. "
            "Execute instalar.bat novamente."
        )

    duration = probe_media_duration(ffmpeg, video_path)
    audio_stream = detect_audio_stream(ffmpeg, video_path)
    nvenc_available = (
        not force_cpu
        and ffmpeg_has_feature(ffmpeg, "-encoders", "h264_nvenc")
    )

    temporary_output: Path | None = None
    with tempfile.TemporaryDirectory(prefix=TEMP_PREFIX) as temp_dir:
        working_directory = Path(temp_dir)
        shutil.copy2(subtitle_path, working_directory / "subtitle.srt")
        try:
            with tempfile.NamedTemporaryFile(
                dir=output_path.parent,
                prefix=f".{output_path.stem}.",
                suffix=".part.mp4",
                delete=False,
            ) as temporary:
                temporary_output = Path(temporary.name)

            attempts = [True, False] if nvenc_available else [False]
            for attempt_index, use_nvenc in enumerate(attempts):
                processor_name = "GPU (NVIDIA)" if use_nvenc else "CPU"
                status(f"Criando vídeo legendado na {processor_name}…", 1.0)
                command = build_tv_video_command(
                    ffmpeg,
                    video_path,
                    temporary_output,
                    audio_stream.index,
                    use_nvenc,
                )
                try:
                    run_tv_video_command(
                        command,
                        working_directory,
                        duration,
                        processor_name,
                        status,
                        cancel_event,
                    )
                    break
                except RuntimeError as exc:
                    if not use_nvenc or attempt_index == len(attempts) - 1:
                        raise RuntimeError(
                            "Não foi possível criar o vídeo legendado. "
                            f"Detalhes do FFmpeg: {exc}"
                        ) from exc
                    temporary_output.unlink(missing_ok=True)
                    temporary_output.touch()
                    status(
                        "A aceleração NVIDIA falhou. Tentando pela CPU…",
                        1.0,
                    )

            if cancel_event.is_set():
                raise CancelledError("Processamento cancelado.")
            if temporary_output.stat().st_size <= 0:
                raise RuntimeError("O vídeo convertido ficou vazio.")
            status("Finalizando o novo arquivo de vídeo…", 99.0)
            os.replace(temporary_output, output_path)
            temporary_output = None
        finally:
            if temporary_output is not None:
                temporary_output.unlink(missing_ok=True)
    status("Vídeo legendado para TV concluído.", 100.0)


def wav_duration_seconds(path: Path) -> float:
    try:
        with wave.open(str(path), "rb") as audio:
            frame_rate = audio.getframerate()
            if frame_rate <= 0:
                raise RuntimeError(f"Taxa de áudio inválida no bloco {path.name}.")
            return audio.getnframes() / frame_rate
    except (OSError, wave.Error) as exc:
        raise RuntimeError(f"Não foi possível medir o bloco {path.name}.") from exc


def create_overlapped_wav(
    previous_path: Path,
    current_path: Path,
    destination: Path,
    overlap_seconds: float = CHUNK_OVERLAP_SECONDS,
) -> float:
    try:
        with wave.open(str(previous_path), "rb") as previous, wave.open(
            str(current_path), "rb"
        ) as current, wave.open(str(destination), "wb") as combined:
            previous_format = (
                previous.getnchannels(),
                previous.getsampwidth(),
                previous.getframerate(),
                previous.getcomptype(),
            )
            current_format = (
                current.getnchannels(),
                current.getsampwidth(),
                current.getframerate(),
                current.getcomptype(),
            )
            if previous_format != current_format:
                raise RuntimeError("Os blocos de áudio possuem formatos diferentes.")

            frame_rate = current.getframerate()
            overlap_frames = min(
                previous.getnframes(),
                max(0, round(overlap_seconds * frame_rate)),
            )
            previous.setpos(previous.getnframes() - overlap_frames)

            combined.setnchannels(current.getnchannels())
            combined.setsampwidth(current.getsampwidth())
            combined.setframerate(frame_rate)
            combined.setcomptype(current.getcomptype(), current.getcompname())
            combined.writeframes(previous.readframes(overlap_frames))

            while True:
                frames = current.readframes(frame_rate * 10)
                if not frames:
                    break
                combined.writeframes(frames)
            return overlap_frames / frame_rate
    except (OSError, wave.Error) as exc:
        raise RuntimeError("Não foi possível preparar a sobreposição do áudio.") from exc


def units_inside_chunk_window(
    units: Iterable[dict],
    lower_end: float | None,
    upper_end: float | None,
) -> list[dict]:
    tolerance = 0.01
    selected: list[dict] = []
    for original in units:
        start = float(original["start"])
        end = float(original["end"])
        if lower_end is not None and end <= lower_end + tolerance:
            continue
        if upper_end is not None and end > upper_end + tolerance:
            continue
        unit = dict(original)
        if lower_end is not None:
            start = max(start, lower_end)
        if end <= start:
            continue
        unit["start"] = start
        unit["end"] = end
        selected.append(unit)
    return selected


def source_units_from_whisper_segment(segment: dict, offset: float) -> list[dict]:
    words = segment.get("words") or []
    valid_words: list[dict] = []
    for word in words:
        text = clean_text(str(word.get("word", "")))
        if not text or word.get("start") is None or word.get("end") is None:
            continue
        valid_words.append(
            {
                "word": text,
                "start": float(word["start"]),
                "end": float(word["end"]),
            }
        )

    if not valid_words:
        text = clean_text(str(segment.get("text", "")))
        if not text:
            return []
        return [
            {
                "start": offset + float(segment["start"]),
                "end": offset + float(segment["end"]),
                "text": text,
            }
        ]

    units: list[dict] = []
    current: list[dict] = []

    def flush() -> None:
        if not current:
            return
        units.append(
            {
                "start": offset + current[0]["start"],
                "end": offset + current[-1]["end"],
                "text": clean_text(" ".join(item["word"] for item in current)),
            }
        )
        current.clear()

    for word in valid_words:
        if current:
            candidate = clean_text(
                " ".join(item["word"] for item in (*current, word))
            )
            candidate_duration = word["end"] - current[0]["start"]
            if len(candidate) > 72 or candidate_duration > 6.0:
                flush()

        current.append(word)
        current_duration = current[-1]["end"] - current[0]["start"]
        if current_duration >= 0.8 and re.search(r"[.!?][\"']?$", word["word"]):
            flush()

    flush()
    return units


def extract_audio_chunks(
    video_path: Path,
    destination: Path,
    status: Callable[[str, float], None],
    cancel_event: threading.Event,
) -> list[AudioChunk]:
    ffmpeg = ensure_ffmpeg()
    stream = detect_audio_stream(ffmpeg, video_path)
    if is_english_language(stream.language):
        status("Faixa de áudio em inglês selecionada.", 4.0)
    else:
        status(
            "Idioma da faixa não identificado; usando a primeira faixa de áudio.",
            4.0,
        )
    output_pattern = destination / "audio-%05d.wav"
    status("Preparando o áudio em blocos leves de 5 minutos…", 5.0)
    command = [
        str(ffmpeg),
        "-nostdin",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(video_path),
        "-map",
        f"0:{stream.index}",
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        "-f",
        "segment",
        "-segment_time",
        str(CHUNK_SECONDS),
        "-reset_timestamps",
        "1",
        str(output_pattern),
    ]
    process = subprocess.Popen(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        **hidden_subprocess_options(),
    )
    stderr = ""
    while True:
        try:
            _, stderr = process.communicate(timeout=0.2)
            break
        except subprocess.TimeoutExpired:
            if not cancel_event.is_set():
                continue
            process.terminate()
            try:
                process.communicate(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate()
            raise CancelledError("Processamento cancelado.")

    if process.returncode != 0:
        detail = stderr.strip() or "não foi possível ler a faixa de áudio"
        raise RuntimeError(f"Falha ao preparar o áudio: {detail}")

    chunk_paths = sorted(destination.glob("audio-*.wav"))
    if not chunk_paths:
        raise RuntimeError("O vídeo não possui uma faixa de áudio compatível.")

    chunks: list[AudioChunk] = []
    exact_start = 0.0
    for path in chunk_paths:
        duration = wav_duration_seconds(path)
        chunks.append(AudioChunk(path=path, start=exact_start, duration=duration))
        exact_start += duration
    status("Áudio preparado com sucesso.", 10.0)
    return chunks


def clear_gpu_cache(torch_module: object) -> None:
    gc.collect()
    if getattr(torch_module, "cuda").is_available():
        getattr(torch_module, "cuda").empty_cache()


def is_memory_error(error: BaseException) -> bool:
    message = str(error).lower()
    return isinstance(error, MemoryError) or any(
        marker in message
        for marker in ("out of memory", "not enough memory", "defaultcpuallocator")
    )


def transcribe_english(
    video_path: Path,
    whisper_model: str,
    status: Callable[[str, float], None],
    cancel_event: threading.Event,
    force_cpu: bool = False,
) -> tuple[list[dict], object]:
    try:
        import torch
        import whisper
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "As dependências não estão instaladas. Execute instalar.bat primeiro."
        ) from exc

    device = "cpu" if force_cpu or not torch.cuda.is_available() else "cuda"
    if device == "cpu":
        reason = "selecionada" if force_cpu else "não detectada"
        status(f"CPU {reason}. O processamento será mais lento.", 2.0)

    if cancel_event.is_set():
        raise CancelledError("Processamento cancelado.")

    available_models = set(whisper.available_models())
    if whisper_model not in available_models:
        fallback_model = "medium.en" if "medium.en" in available_models else "small.en"
        status(
            f"O modelo {whisper_model} não está disponível nesta instalação. "
            f"Usando {fallback_model}.",
            2.0,
        )
        whisper_model = fallback_model

    status(f"Carregando Whisper {whisper_model} na {device.upper()}…", 3.0)
    model = whisper.load_model(whisper_model, device=device)
    segments: list[dict] = []
    base_prompt = (
        "Accurate English dialogue transcription for movie subtitles. "
        "Preserve character names, places, punctuation, and natural sentences."
    )

    with tempfile.TemporaryDirectory(prefix=TEMP_PREFIX) as temp_dir:
        temp_path = Path(temp_dir)
        chunks = extract_audio_chunks(
            video_path,
            temp_path,
            status,
            cancel_event,
        )
        total_chunks = len(chunks)
        total_duration = sum(chunk.duration for chunk in chunks)
        previous_context = ""

        for chunk_index, chunk in enumerate(chunks):
            if cancel_event.is_set():
                raise CancelledError("Processamento cancelado.")
            progress = 10.0 + (chunk.start / max(total_duration, 0.001)) * 50.0
            status(
                f"Transcrevendo inglês… bloco {chunk_index + 1}/{total_chunks}",
                progress,
            )
            prompt = base_prompt
            if previous_context:
                prompt += " Previous dialogue: " + previous_context[-300:]

            transcription_path = chunk.path
            transcription_start = chunk.start
            overlap_path: Path | None = None
            lower_end: float | None = None
            if chunk_index > 0:
                overlap_path = temp_path / f"overlap-{chunk_index:05d}.wav"
                actual_overlap = create_overlapped_wav(
                    chunks[chunk_index - 1].path,
                    chunk.path,
                    overlap_path,
                )
                transcription_path = overlap_path
                transcription_start = chunk.start - actual_overlap
                lower_end = chunk.start - CHUNK_GUARD_SECONDS

            upper_end: float | None = None
            if chunk_index < total_chunks - 1:
                upper_end = chunk.start + chunk.duration - CHUNK_GUARD_SECONDS

            try:
                result = model.transcribe(
                    str(transcription_path),
                    language="en",
                    task="transcribe",
                    fp16=device == "cuda",
                    temperature=0,
                    beam_size=5,
                    patience=1.0,
                    condition_on_previous_text=True,
                    verbose=False,
                    word_timestamps=True,
                    initial_prompt=prompt,
                )
            finally:
                if overlap_path is not None:
                    overlap_path.unlink(missing_ok=True)

            current_texts: list[str] = []
            for segment in result.get("segments", []):
                source_units = source_units_from_whisper_segment(
                    segment,
                    transcription_start,
                )
                source_units = units_inside_chunk_window(
                    source_units,
                    lower_end,
                    upper_end,
                )
                segments.extend(source_units)
                current_texts.extend(unit["text"] for unit in source_units)
            if current_texts:
                previous_context = " ".join(current_texts[-4:])
    status("Transcrição concluída.", 60.0)
    return segments, model


def translate_to_portuguese(
    texts: Sequence[str],
    status: Callable[[str, float], None],
    cancel_event: threading.Event,
    force_cpu: bool = False,
) -> list[str]:
    try:
        import torch
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "As dependências não estão instaladas. Execute instalar.bat primeiro."
        ) from exc

    if not texts:
        return []

    use_cuda = torch.cuda.is_available() and not force_cpu
    device = torch.device("cuda" if use_cuda else "cpu")
    status(
        f"Carregando a IA de tradução para português na {device.type.upper()}…",
        62.0,
    )
    tokenizer = AutoTokenizer.from_pretrained(TRANSLATION_MODEL)
    model = AutoModelForSeq2SeqLM.from_pretrained(
        TRANSLATION_MODEL,
        torch_dtype=torch.float16 if device.type == "cuda" else torch.float32,
    ).to(device)
    model.eval()

    if device.type == "cuda":
        gpu_memory_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        batch_size = 4 if gpu_memory_gb <= 8.5 else 8
    else:
        batch_size = 2
    translated: list[str] = []
    total = len(texts)

    for offset in range(0, total, batch_size):
        if cancel_event.is_set():
            raise CancelledError("Processamento cancelado.")
        batch = prepare_translation_inputs(texts[offset : offset + batch_size])
        encoded = tokenizer(
            batch,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=256,
        ).to(device)
        with torch.inference_mode():
            generated = model.generate(
                **encoded,
                num_beams=5,
                max_new_tokens=256,
                length_penalty=1.0,
                early_stopping=True,
            )
        translated.extend(
            brazilianize(text)
            for text in tokenizer.batch_decode(generated, skip_special_tokens=True)
        )
        completed = min(offset + batch_size, total)
        progress = 65.0 + (completed / total) * 30.0
        status(f"Traduzindo para PT-BR… {completed}/{total}", progress)

    del model
    clear_gpu_cache(torch)
    return translated


def build_subtitle(
    video_path: Path,
    output_path: Path,
    whisper_model: str,
    force_cpu: bool,
    status: Callable[[str, float], None],
    cancel_event: threading.Event,
) -> None:
    status("Verificando os componentes instalados…", 1.0)
    missing = missing_runtime_dependencies()
    if missing:
        raise RuntimeError(
            "Componentes ausentes: "
            + ", ".join(missing)
            + ". Execute instalar.bat novamente."
        )
    verify_output_location(output_path)

    try:
        import torch
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "As dependências não estão instaladas. Execute instalar.bat primeiro."
        ) from exc

    try:
        segments, whisper_instance = transcribe_english(
            video_path, whisper_model, status, cancel_event, force_cpu
        )
    except Exception as exc:
        if not is_memory_error(exc):
            raise
        exc.__traceback__ = None
        del exc
        clear_gpu_cache(torch)
        if whisper_model == "small.en" or force_cpu:
            raise RuntimeError(
                "A memória disponível acabou. Feche outros programas e tente novamente."
            ) from None
        status(
            "Memória da GPU insuficiente. Tentando automaticamente o modo econômico…",
            3.0,
        )
        try:
            segments, whisper_instance = transcribe_english(
                video_path, "small.en", status, cancel_event, force_cpu=False
            )
        except Exception as exc_small:
            if not is_memory_error(exc_small):
                raise
            exc_small.__traceback__ = None
            del exc_small
            clear_gpu_cache(torch)
            raise RuntimeError(
                "A memória da GPU acabou mesmo no modo econômico. Feche jogos, "
                "o navegador e outros programas ou selecione 'Usar somente CPU'."
            ) from None

    if cancel_event.is_set():
        raise CancelledError("Processamento cancelado.")
    if not segments:
        raise RuntimeError("Nenhuma fala em inglês foi encontrada no vídeo.")
    segments.sort(key=lambda segment: (segment["start"], segment["end"]))

    # The translation model is loaded after Whisper is released to reduce VRAM use.
    del whisper_instance
    clear_gpu_cache(torch)
    source_texts = [segment["text"] for segment in segments]
    try:
        translations = translate_to_portuguese(
            source_texts, status, cancel_event, force_cpu
        )
    except Exception as exc:
        if is_memory_error(exc):
            exc.__traceback__ = None
            del exc
            clear_gpu_cache(torch)
            if force_cpu:
                raise RuntimeError(
                    "Não há memória RAM suficiente para traduzir o filme. "
                    "Feche outros programas e tente novamente."
                ) from None
            status(
                "Memória da GPU insuficiente na tradução. Continuando pela CPU…",
                62.0,
            )
            try:
                translations = translate_to_portuguese(
                    source_texts, status, cancel_event, force_cpu=True
                )
            except Exception as exc_cpu:
                if not is_memory_error(exc_cpu):
                    raise
                exc_cpu.__traceback__ = None
                del exc_cpu
                clear_gpu_cache(torch)
                raise RuntimeError(
                    "Não há memória RAM suficiente para traduzir o filme. "
                    "Feche outros programas e tente novamente."
                ) from None
        else:
            raise

    if len(translations) != len(segments):
        raise RuntimeError("A tradução retornou uma quantidade inesperada de frases.")

    status("Organizando os tempos da legenda…", 97.0)
    captions: list[Caption] = []
    for segment, translation in zip(segments, translations):
        captions.extend(
            captions_from_segment(segment["start"], segment["end"], translation)
        )
    if not captions:
        raise RuntimeError("A tradução não produziu nenhuma legenda utilizável.")

    status("Gravando a legenda…", 99.0)
    write_srt_atomic(output_path, render_srt(captions))
    status("Legenda concluída.", 100.0)


class LegendaApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(f"{APP_NAME} {APP_VERSION}")
        self.root.geometry("900x660")
        self.root.minsize(780, 610)
        self.root.configure(bg="#0B1220")

        self.video_path = tk.StringVar()
        self.quality = tk.StringVar(value="Recomendado — medium.en")
        self.force_cpu = tk.BooleanVar(value=False)
        self.status_text = tk.StringVar(value="Selecione um filme para começar.")
        self.cancel_event = threading.Event()
        self.worker: threading.Thread | None = None

        self._configure_style()
        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.close_app)

    def _configure_style(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background="#0B1220")
        style.configure("Card.TFrame", background="#111C31")
        style.configure(
            "Title.TLabel",
            background="#0B1220",
            foreground="#F8FAFC",
            font=("Segoe UI Semibold", 22),
        )
        style.configure(
            "Subtitle.TLabel",
            background="#0B1220",
            foreground="#9FB0C7",
            font=("Segoe UI", 10),
        )
        style.configure(
            "Card.TLabel",
            background="#111C31",
            foreground="#E5EDF8",
            font=("Segoe UI", 10),
        )
        style.configure(
            "Card.TCheckbutton",
            background="#111C31",
            foreground="#E5EDF8",
            font=("Segoe UI", 9),
        )
        style.map("Card.TCheckbutton", background=[("active", "#111C31")])
        style.configure(
            "Accent.TButton",
            font=("Segoe UI Semibold", 11),
            padding=(18, 11),
            background="#2563EB",
            foreground="#FFFFFF",
        )
        style.map("Accent.TButton", background=[("active", "#3B82F6")])
        style.configure(
            "TV.TButton",
            font=("Segoe UI Semibold", 11),
            padding=(18, 11),
            background="#0F766E",
            foreground="#FFFFFF",
        )
        style.map("TV.TButton", background=[("active", "#0D9488")])
        style.configure("TButton", font=("Segoe UI", 10), padding=(12, 8))
        style.configure("TCombobox", padding=7)
        style.configure(
            "Horizontal.TProgressbar",
            background="#3B82F6",
            troughcolor="#1E293B",
            bordercolor="#1E293B",
        )

    def _build_ui(self) -> None:
        shell = ttk.Frame(self.root, padding=28)
        shell.pack(fill="both", expand=True)

        ttk.Label(shell, text="Legenda IA para VLC", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            shell,
            text="Áudio em inglês → legenda sincronizada em português do Brasil",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(3, 20))

        card = ttk.Frame(shell, style="Card.TFrame", padding=22)
        card.pack(fill="x")

        ttk.Label(card, text="1. Filme ou episódio", style="Card.TLabel").pack(anchor="w")
        file_row = ttk.Frame(card, style="Card.TFrame")
        file_row.pack(fill="x", pady=(7, 17))
        self.file_entry = ttk.Entry(file_row, textvariable=self.video_path)
        self.file_entry.pack(side="left", fill="x", expand=True, ipady=6)
        self.select_button = ttk.Button(file_row, text="Selecionar", command=self.select_video)
        self.select_button.pack(side="left", padx=(9, 0))

        ttk.Label(card, text="2. Qualidade e desempenho", style="Card.TLabel").pack(
            anchor="w"
        )
        self.quality_box = ttk.Combobox(
            card,
            textvariable=self.quality,
            state="readonly",
            values=(
                "Recomendado — medium.en",
                "Menor uso de memória — small.en",
                "Mais qualidade — turbo",
            ),
        )
        self.quality_box.pack(fill="x", pady=(7, 8))

        self.cpu_check = ttk.Checkbutton(
            card,
            text="Usar somente CPU (muito mais lento; use apenas se a GPU falhar)",
            variable=self.force_cpu,
            style="Card.TCheckbutton",
        )
        self.cpu_check.pack(anchor="w", pady=(0, 18))

        button_row = ttk.Frame(card, style="Card.TFrame")
        button_row.pack(fill="x")
        self.start_button = ttk.Button(
            button_row,
            text="Gerar legenda e abrir no VLC",
            style="Accent.TButton",
            command=self.start,
        )
        self.start_button.pack(side="left")
        self.tv_button = ttk.Button(
            button_row,
            text="Criar vídeo legendado para TV",
            style="TV.TButton",
            command=self.start_tv_export,
        )
        self.tv_button.pack(side="left", padx=(10, 0))
        self.cancel_button = ttk.Button(
            button_row, text="Cancelar", command=self.cancel, state="disabled"
        )
        self.cancel_button.pack(side="left", padx=(10, 0))

        ttk.Label(
            card,
            text=(
                "A opção para TV usa o SRT já criado, preserva o original e gera "
                "um novo MP4 com legenda permanente."
            ),
            style="Card.TLabel",
        ).pack(anchor="w", pady=(12, 0))

        status_card = ttk.Frame(shell, style="Card.TFrame", padding=18)
        status_card.pack(fill="both", expand=True, pady=(16, 0))
        ttk.Label(status_card, textvariable=self.status_text, style="Card.TLabel").pack(
            anchor="w"
        )
        self.progress = ttk.Progressbar(
            status_card,
            mode="determinate",
            maximum=100,
        )
        self.progress.pack(fill="x", pady=(10, 14))

        self.log = tk.Text(
            status_card,
            height=6,
            bg="#0D1729",
            fg="#AFC1D9",
            insertbackground="#FFFFFF",
            relief="flat",
            font=("Consolas", 9),
            padx=10,
            pady=9,
            state="disabled",
        )
        self.log.pack(fill="both", expand=True)
        self._append_log("O vídeo permanece no seu computador.")
        self._append_log("Na primeira execução, os modelos de IA serão baixados.")

    def _append_log(self, message: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", message + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def update_status(self, message: str, progress_value: float | None = None) -> None:
        def apply() -> None:
            if progress_value is None:
                self.status_text.set(message)
            else:
                self.status_text.set(f"{message} ({progress_value:.0f}%)")
                self.progress["value"] = progress_value
            if not message.startswith(
                (
                    "Transcrevendo inglês",
                    "Traduzindo para PT-BR",
                    "Criando vídeo legendado",
                )
            ):
                self._append_log(message)

        self.root.after(0, apply)

    def select_video(self) -> None:
        selected = filedialog.askopenfilename(title="Selecione o vídeo", filetypes=VIDEO_TYPES)
        if selected:
            self.video_path.set(selected)

    def start(self) -> None:
        video = Path(self.video_path.get().strip().strip('"'))
        if not video.is_file():
            messagebox.showwarning(APP_NAME, "Selecione um arquivo de vídeo válido.")
            return

        output = video.with_name(f"{video.stem}.pt-BR.srt")
        if output.exists() and not messagebox.askyesno(
            APP_NAME, f"A legenda {output.name} já existe. Deseja substituí-la?"
        ):
            return

        selected_quality = self.quality.get()
        if "small.en" in selected_quality:
            model = "small.en"
        elif "turbo" in selected_quality:
            model = "turbo"
        else:
            model = "medium.en"
        force_cpu = self.force_cpu.get()
        self.cancel_event.clear()
        self._set_running(True)
        self.progress["value"] = 0
        self.update_status("Preparando o processamento…", 0.0)
        self.worker = threading.Thread(
            target=self._run_worker,
            args=(video, output, model, force_cpu),
            daemon=True,
        )
        self.worker.start()

    def start_tv_export(self) -> None:
        video = Path(self.video_path.get().strip().strip('"'))
        if not video.is_file():
            messagebox.showwarning(APP_NAME, "Selecione um arquivo de vídeo válido.")
            return

        subtitle = video.with_name(f"{video.stem}.pt-BR.srt")
        if not subtitle.is_file():
            messagebox.showinfo(
                APP_NAME,
                "Gere a legenda primeiro. Depois clique novamente em "
                "'Criar vídeo legendado para TV'.",
            )
            return

        suggested = tv_video_output_path(video)
        selected = filedialog.asksaveasfilename(
            title="Salvar novo vídeo com legenda permanente",
            initialdir=str(video.parent),
            initialfile=suggested.name,
            defaultextension=".mp4",
            filetypes=(("Vídeo MP4", "*.mp4"),),
        )
        if not selected:
            return
        output = Path(selected)
        if output.suffix.lower() != ".mp4":
            output = output.with_suffix(".mp4")
        if output.exists() and not messagebox.askyesno(
            APP_NAME,
            f"O arquivo {output.name} já existe. Deseja substituí-lo?",
        ):
            return

        self.cancel_event.clear()
        self._set_running(True)
        self.progress["value"] = 0
        self.update_status("Preparando o novo vídeo para TV…", 0.0)
        self.worker = threading.Thread(
            target=self._run_tv_worker,
            args=(video, subtitle, output, self.force_cpu.get()),
            daemon=True,
        )
        self.worker.start()

    def cancel(self) -> None:
        self.cancel_event.set()
        self.update_status("Cancelamento solicitado. Aguarde o fim da etapa atual…")

    def close_app(self) -> None:
        if self.worker is not None and self.worker.is_alive():
            should_close = messagebox.askyesno(
                APP_NAME,
                "O processamento ainda está em andamento. Deseja fechar mesmo assim?",
            )
            if not should_close:
                return
            self.cancel_event.set()
        self.root.destroy()

    def _set_running(self, running: bool) -> None:
        state = "disabled" if running else "normal"
        self.start_button.configure(state=state)
        self.tv_button.configure(state=state)
        self.select_button.configure(state=state)
        self.file_entry.configure(state=state)
        self.quality_box.configure(state="disabled" if running else "readonly")
        self.cpu_check.configure(state=state)
        self.cancel_button.configure(state="normal" if running else "disabled")

    def _run_worker(
        self,
        video: Path,
        output: Path,
        model: str,
        force_cpu: bool,
    ) -> None:
        try:
            build_subtitle(
                video,
                output,
                model,
                force_cpu,
                self.update_status,
                self.cancel_event,
            )
        except CancelledError:
            self.root.after(0, lambda: self._finish_cancelled())
        except Exception as exc:  # GUI boundary: show a readable error instead of exiting.
            traceback.print_exc(file=sys.stderr)
            self.root.after(0, lambda error=exc: self._finish_error(error))
        else:
            self.root.after(0, lambda: self._finish_success(video, output))

    def _run_tv_worker(
        self,
        video: Path,
        subtitle: Path,
        output: Path,
        force_cpu: bool,
    ) -> None:
        try:
            create_tv_video(
                video,
                subtitle,
                output,
                force_cpu,
                self.update_status,
                self.cancel_event,
            )
        except CancelledError:
            self.root.after(0, self._finish_cancelled)
        except Exception as exc:  # GUI boundary: preserve the original and report.
            traceback.print_exc(file=sys.stderr)
            self.root.after(0, lambda error=exc: self._finish_tv_error(error))
        else:
            self.root.after(0, lambda: self._finish_tv_success(output))

    def _finish_cancelled(self) -> None:
        self._set_running(False)
        self.status_text.set("Processamento cancelado.")
        self.progress["value"] = 0
        self._append_log("Processamento cancelado.")

    def _finish_error(self, error: Exception) -> None:
        self._set_running(False)
        self.status_text.set("Não foi possível gerar a legenda.")
        self.progress["value"] = 0
        self._append_log(f"ERRO: {error}")
        messagebox.showerror(APP_NAME, str(error))

    def _finish_tv_error(self, error: Exception) -> None:
        self._set_running(False)
        self.status_text.set("Não foi possível criar o vídeo legendado.")
        self.progress["value"] = 0
        self._append_log(f"ERRO AO CRIAR VÍDEO: {error}")
        messagebox.showerror(
            APP_NAME,
            f"{error}\n\nO vídeo original não foi alterado.",
        )

    def _find_or_choose_vlc(self) -> Path | None:
        vlc = find_vlc()
        if vlc is not None:
            return vlc
        selected = filedialog.askopenfilename(
            title="Localize o vlc.exe",
            filetypes=(("VLC", "vlc.exe"), ("Executáveis", "*.exe")),
        )
        vlc = Path(selected) if selected else None
        if vlc and vlc.is_file():
            remember_vlc(vlc)
            return vlc
        return None

    def _finish_success(self, video: Path, subtitle: Path) -> None:
        self._set_running(False)
        self.status_text.set("Legenda PT-BR criada com sucesso.")
        self.progress["value"] = 100
        self._append_log(f"Legenda salva em: {subtitle}")

        vlc = self._find_or_choose_vlc()

        if vlc and vlc.is_file():
            try:
                subprocess.Popen([str(vlc), f"--sub-file={subtitle}", str(video)])
            except OSError as exc:
                messagebox.showwarning(
                    APP_NAME,
                    f"A legenda foi criada, mas o VLC não abriu:\n{exc}\n\n"
                    f"Carregue manualmente o arquivo:\n{subtitle}",
                )
                return
            messagebox.showinfo(
                APP_NAME,
                f"Legenda criada e aberta no VLC:\n{subtitle.name}",
            )
        else:
            messagebox.showinfo(
                APP_NAME,
                f"Legenda criada:\n{subtitle}\n\nAbra o vídeo no VLC e carregue esse arquivo.",
            )

    def _finish_tv_success(self, output: Path) -> None:
        self._set_running(False)
        self.status_text.set("Vídeo com legenda permanente criado com sucesso.")
        self.progress["value"] = 100
        self._append_log(f"Vídeo para TV salvo em: {output}")

        vlc = self._find_or_choose_vlc()
        if vlc and vlc.is_file():
            try:
                subprocess.Popen([str(vlc), str(output)])
            except OSError as exc:
                messagebox.showwarning(
                    APP_NAME,
                    f"O vídeo foi criado, mas o VLC não abriu:\n{exc}\n\n"
                    f"Abra manualmente:\n{output}",
                )
                return
            messagebox.showinfo(
                APP_NAME,
                "Vídeo legendado criado e aberto no VLC.\n\n"
                "Agora use Reprodução > Renderizador para enviar à TV.\n"
                "O vídeo original foi preservado.",
            )
        else:
            messagebox.showinfo(
                APP_NAME,
                f"Vídeo legendado criado:\n{output}\n\n"
                "O vídeo original foi preservado.",
            )


def main() -> None:
    cleanup_stale_temp_dirs()
    configure_process_streams()
    root = tk.Tk()
    LegendaApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
