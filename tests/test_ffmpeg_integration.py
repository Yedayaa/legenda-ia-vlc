import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
import wave
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app


def available_ffmpeg() -> Path | None:
    try:
        import imageio_ffmpeg

        return Path(imageio_ffmpeg.get_ffmpeg_exe())
    except (ImportError, RuntimeError):
        found = shutil.which("ffmpeg")
        return Path(found) if found else None


class FfmpegIntegrationTests(unittest.TestCase):
    def test_extraction_prefers_english_track(self):
        ffmpeg = available_ffmpeg()
        if ffmpeg is None:
            self.skipTest("FFmpeg não disponível neste ambiente")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            video = root / "duas-faixas.mkv"
            chunks_dir = root / "chunks"
            chunks_dir.mkdir()
            command = [
                str(ffmpeg),
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "lavfi",
                "-i",
                "anullsrc=r=16000:cl=mono",
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=1000:sample_rate=16000",
                "-t",
                "1",
                "-map",
                "0:a",
                "-map",
                "1:a",
                "-metadata:s:a:0",
                "language=por",
                "-metadata:s:a:1",
                "language=eng",
                "-c:a",
                "pcm_s16le",
                str(video),
            ]
            subprocess.run(command, check=True, capture_output=True)

            updates: list[tuple[str, float]] = []
            with patch("app.ensure_ffmpeg", return_value=ffmpeg):
                chunks = app.extract_audio_chunks(
                    video,
                    chunks_dir,
                    lambda message, progress: updates.append((message, progress)),
                    threading.Event(),
                )

            self.assertEqual(len(chunks), 1)
            self.assertTrue(any("inglês" in message for message, _ in updates))
            with wave.open(str(chunks[0].path), "rb") as audio:
                frames = audio.readframes(audio.getnframes())
            self.assertNotEqual(set(frames), {0})

    def test_creates_tv_mp4_with_burned_subtitle_and_preserves_original(self):
        ffmpeg = available_ffmpeg()
        if ffmpeg is None:
            self.skipTest("FFmpeg não disponível neste ambiente")
        if not app.ffmpeg_has_feature(ffmpeg, "-filters", "subtitles"):
            self.skipTest("FFmpeg sem filtro subtitles/libass")
        if not app.ffmpeg_has_feature(ffmpeg, "-encoders", "libx264"):
            self.skipTest("FFmpeg sem codificador libx264")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            video = root / "vídeo-teste.mp4"
            subtitle = root / "vídeo-teste.pt-BR.srt"
            output = root / "vídeo-teste.legendado-PT-BR.mp4"
            command = [
                str(ffmpeg),
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "lavfi",
                "-i",
                "color=c=black:s=320x180:r=24",
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=440:sample_rate=48000",
                "-t",
                "1.5",
                "-shortest",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                str(video),
            ]
            subprocess.run(command, check=True, capture_output=True)
            subtitle.write_text(
                "1\n00:00:00,100 --> 00:00:01,200\nOlá, televisão!\n",
                encoding="utf-8-sig",
            )
            original_bytes = video.read_bytes()
            updates: list[tuple[str, float]] = []

            with patch("app.ensure_ffmpeg", return_value=ffmpeg):
                app.create_tv_video(
                    video,
                    subtitle,
                    output,
                    force_cpu=True,
                    status=lambda message, progress: updates.append(
                        (message, progress)
                    ),
                    cancel_event=threading.Event(),
                )

            self.assertTrue(output.is_file())
            self.assertGreater(output.stat().st_size, 0)
            self.assertEqual(video.read_bytes(), original_bytes)
            self.assertTrue(any(progress == 100 for _, progress in updates))
            probe = subprocess.run(
                [str(ffmpeg), "-hide_banner", "-i", str(output)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
            self.assertIn("Video: h264", probe.stderr)
            self.assertIn("Audio: aac", probe.stderr)
            self.assertNotIn("Subtitle:", probe.stderr)
            frame = subprocess.run(
                [
                    str(ffmpeg),
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-ss",
                    "0.5",
                    "-i",
                    str(output),
                    "-frames:v",
                    "1",
                    "-pix_fmt",
                    "rgb24",
                    "-f",
                    "rawvideo",
                    "pipe:1",
                ],
                capture_output=True,
                check=True,
            )
            self.assertGreater(max(frame.stdout), 100)


if __name__ == "__main__":
    unittest.main()
