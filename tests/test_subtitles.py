import contextlib
import sys
import tempfile
import unittest
import wave
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app

from app import (
    CHUNK_GUARD_SECONDS,
    CHUNK_OVERLAP_SECONDS,
    CHUNK_SECONDS,
    Caption,
    brazilianize,
    captions_from_segment,
    choose_audio_stream_from_ffmpeg_output,
    create_overlapped_wav,
    format_timestamp,
    is_memory_error,
    prepare_translation_inputs,
    render_srt,
    source_units_from_whisper_segment,
    translate_to_portuguese,
    units_inside_chunk_window,
    wav_duration_seconds,
    write_srt_atomic,
)


class SubtitleTests(unittest.TestCase):
    def test_timestamp_rounding_and_hours(self):
        self.assertEqual(format_timestamp(0), "00:00:00,000")
        self.assertEqual(format_timestamp(3661.234), "01:01:01,234")

    def test_long_caption_is_split_and_wrapped(self):
        text = (
            "Esta é uma frase muito longa criada para verificar se a legenda "
            "é dividida em blocos pequenos e confortáveis para leitura na televisão."
        )
        captions = captions_from_segment(10, 18, text)
        self.assertGreater(len(captions), 1)
        self.assertAlmostEqual(captions[0].start, 10)
        self.assertAlmostEqual(captions[-1].end, 18)
        for caption in captions:
            self.assertTrue(all(len(line) <= 42 for line in caption.text.splitlines()))

    def test_wrapping_never_drops_words(self):
        text = " ".join(["três"] * 17)
        captions = captions_from_segment(0, 8, text)
        rebuilt = " ".join(caption.text.replace("\n", " ") for caption in captions)
        self.assertEqual(rebuilt, text)
        self.assertTrue(all(len(caption.text.splitlines()) <= 2 for caption in captions))

    def test_srt_rendering(self):
        output = render_srt([Caption(1.5, 3.25, "Olá, mundo!")])
        self.assertIn("1\n00:00:01,500 --> 00:00:03,250\nOlá, mundo!", output)

    def test_conservative_pt_br_words(self):
        self.assertEqual(
            brazilianize("O ficheiro está no telemóvel."),
            "O arquivo está no celular.",
        )
        self.assertEqual(
            brazilianize("Ficheiro, equipa e pequeno-almoço."),
            "Arquivo, equipe e café da manhã.",
        )

    def test_translation_explicitly_targets_brazilian_portuguese(self):
        self.assertEqual(
            prepare_translation_inputs(["Hello there."]),
            [">>pob<< Hello there."],
        )

    def test_translation_pipeline_loads_tokenizer_and_uses_pt_br_token(self):
        captured: dict[str, object] = {}

        class Encoded(dict):
            def to(self, device):
                captured["encoded_device"] = device.type
                return self

        class FakeTokenizer:
            @classmethod
            def from_pretrained(cls, model_name):
                captured["tokenizer_model"] = model_name
                return cls()

            def __call__(self, batch, **kwargs):
                captured["batch"] = list(batch)
                return Encoded(input_ids=[1, 2])

            def batch_decode(self, generated, **kwargs):
                return ["Olá.", "Tudo bem?"]

        class FakeModel:
            @classmethod
            def from_pretrained(cls, model_name, **kwargs):
                captured["translation_model"] = model_name
                return cls()

            def to(self, device):
                return self

            def eval(self):
                return None

            def generate(self, **kwargs):
                return [[1], [2]]

        fake_torch = SimpleNamespace(
            cuda=SimpleNamespace(is_available=lambda: False),
            device=lambda name: SimpleNamespace(type=name),
            float16="float16",
            float32="float32",
            inference_mode=contextlib.nullcontext,
        )
        fake_transformers = SimpleNamespace(
            AutoModelForSeq2SeqLM=FakeModel,
            AutoTokenizer=FakeTokenizer,
        )
        statuses: list[tuple[str, float]] = []
        with patch.dict(
            sys.modules,
            {"torch": fake_torch, "transformers": fake_transformers},
        ):
            translated = translate_to_portuguese(
                ["Hello.", "How are you?"],
                lambda message, progress: statuses.append((message, progress)),
                __import__("threading").Event(),
                force_cpu=True,
            )

        self.assertEqual(translated, ["Olá.", "Tudo bem?"])
        self.assertEqual(captured["encoded_device"], "cpu")
        self.assertEqual(captured["batch"], [">>pob<< Hello.", ">>pob<< How are you?"])
        self.assertTrue(any("PT-BR" in message for message, _ in statuses))

    def test_word_timestamps_define_caption_units(self):
        segment = {
            "start": 0.0,
            "end": 2.4,
            "text": "Hello there. How are you?",
            "words": [
                {"word": " Hello", "start": 0.1, "end": 0.5},
                {"word": " there.", "start": 0.5, "end": 1.1},
                {"word": " How", "start": 1.5, "end": 1.8},
                {"word": " are", "start": 1.8, "end": 2.0},
                {"word": " you?", "start": 2.0, "end": 2.4},
            ],
        }
        units = source_units_from_whisper_segment(segment, offset=600.0)
        self.assertEqual([unit["text"] for unit in units], ["Hello there.", "How are you?"])
        self.assertEqual((units[0]["start"], units[0]["end"]), (600.1, 601.1))
        self.assertEqual((units[1]["start"], units[1]["end"]), (601.5, 602.4))

    def test_source_file_is_valid_utf8_without_mojibake(self):
        source = (Path(__file__).resolve().parents[1] / "app.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('("Vídeos",', source)
        self.assertIn("AutoTokenizer.from_pretrained", source)
        self.assertNotIn("AutoTokenizer.frompretrained", source)
        self.assertIn('APP_VERSION = "1.4.0"', source)
        self.assertIn('mode="determinate"', source)
        self.assertNotIn("GTX 1070", source)
        for broken_text in ("VÃ", "ecrÃ", "telemÃ", "â†", "â€¦"):
            self.assertNotIn(broken_text, source)

    def test_audio_chunks_are_five_minutes_with_safe_overlap(self):
        self.assertEqual(CHUNK_SECONDS, 300)
        self.assertGreaterEqual(CHUNK_OVERLAP_SECONDS, CHUNK_GUARD_SECONDS * 2)

    def test_english_audio_track_is_preferred(self):
        probe_output = """
          Stream #0:1(por): Audio: eac3, 48000 Hz, stereo
          Stream #0:2[0x1100](eng): Audio: eac3, 48000 Hz, 5.1
        """
        stream = choose_audio_stream_from_ffmpeg_output(probe_output)
        self.assertIsNotNone(stream)
        self.assertEqual(stream.index, 2)
        self.assertEqual(stream.language, "eng")

    def test_first_audio_track_is_fallback_without_language(self):
        stream = choose_audio_stream_from_ffmpeg_output(
            "Stream #0:3: Audio: aac, 48000 Hz, stereo"
        )
        self.assertIsNotNone(stream)
        self.assertEqual(stream.index, 3)

    def test_regional_english_language_tag_is_supported(self):
        stream = choose_audio_stream_from_ffmpeg_output(
            "Stream #0:1(por): Audio: aac\nStream #0:4(en-US): Audio: aac"
        )
        self.assertIsNotNone(stream)
        self.assertEqual(stream.index, 4)

    def test_overlap_wav_contains_tail_and_current_audio(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            previous = root / "previous.wav"
            current = root / "current.wav"
            combined = root / "combined.wav"

            for path, seconds in ((previous, 2.0), (current, 1.0)):
                with wave.open(str(path), "wb") as audio:
                    audio.setnchannels(1)
                    audio.setsampwidth(2)
                    audio.setframerate(1000)
                    audio.writeframes(b"\x01\x00" * round(seconds * 1000))

            overlap = create_overlapped_wav(
                previous,
                current,
                combined,
                overlap_seconds=0.5,
            )
            self.assertAlmostEqual(overlap, 0.5)
            self.assertAlmostEqual(wav_duration_seconds(combined), 1.5)

    def test_overlap_window_avoids_duplicates_and_clamps_start(self):
        units = [
            {"start": 292.0, "end": 293.0, "text": "antiga"},
            {"start": 293.5, "end": 295.0, "text": "cruza"},
            {"start": 595.0, "end": 596.0, "text": "final"},
            {"start": 596.0, "end": 597.0, "text": "próxima"},
        ]
        selected = units_inside_chunk_window(units, lower_end=294.0, upper_end=596.0)
        self.assertEqual([unit["text"] for unit in selected], ["cruza", "final"])
        self.assertEqual(selected[0]["start"], 294.0)

    def test_srt_is_replaced_atomically(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "filme.pt-BR.srt"
            output.write_text("versão antiga", encoding="utf-8")
            write_srt_atomic(output, "1\n00:00:00,000 --> 00:00:01,000\nOlá!\n")
            self.assertEqual(
                output.read_text(encoding="utf-8-sig"),
                "1\n00:00:00,000 --> 00:00:01,000\nOlá!\n",
            )
            self.assertEqual(list(Path(directory).glob("*.tmp")), [])

    def test_wav_duration_uses_real_sample_count(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "chunk.wav"
            with wave.open(str(path), "wb") as audio:
                audio.setnchannels(1)
                audio.setsampwidth(2)
                audio.setframerate(16000)
                audio.writeframes(b"\x00\x00" * 20_000)
            self.assertAlmostEqual(wav_duration_seconds(path), 1.25)

    def test_memory_errors_are_recognized(self):
        self.assertTrue(is_memory_error(MemoryError()))
        self.assertTrue(is_memory_error(RuntimeError("CUDA out of memory")))
        self.assertFalse(is_memory_error(RuntimeError("arquivo inválido")))

    def test_whisper_oom_retries_with_economic_model(self):
        fake_torch = SimpleNamespace(
            cuda=SimpleNamespace(
                is_available=lambda: True,
                empty_cache=lambda: None,
            )
        )
        segment = {"start": 0.0, "end": 1.0, "text": "Hello."}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            video = root / "video.mkv"
            video.write_bytes(b"video")
            output = root / "video.pt-BR.srt"
            with patch.dict(sys.modules, {"torch": fake_torch}), patch(
                "app.missing_runtime_dependencies", return_value=[]
            ), patch(
                "app.transcribe_english",
                side_effect=[RuntimeError("CUDA out of memory"), ([segment], object())],
            ) as transcribe, patch(
                "app.translate_to_portuguese", return_value=["Olá."]
            ):
                app.build_subtitle(
                    video,
                    output,
                    "medium.en",
                    False,
                    lambda *_: None,
                    __import__("threading").Event(),
                )

            self.assertEqual(transcribe.call_count, 2)
            self.assertEqual(transcribe.call_args_list[1].args[1], "small.en")
            self.assertIn("Olá.", output.read_text(encoding="utf-8-sig"))

    def test_translation_oom_retries_on_cpu(self):
        fake_torch = SimpleNamespace(
            cuda=SimpleNamespace(
                is_available=lambda: True,
                empty_cache=lambda: None,
            )
        )
        segment = {"start": 0.0, "end": 1.0, "text": "Hello."}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            video = root / "video.mkv"
            video.write_bytes(b"video")
            output = root / "video.pt-BR.srt"
            with patch.dict(sys.modules, {"torch": fake_torch}), patch(
                "app.missing_runtime_dependencies", return_value=[]
            ), patch(
                "app.transcribe_english", return_value=([segment], object())
            ), patch(
                "app.translate_to_portuguese",
                side_effect=[RuntimeError("CUDA out of memory"), ["Olá."]],
            ) as translate:
                app.build_subtitle(
                    video,
                    output,
                    "medium.en",
                    False,
                    lambda *_: None,
                    __import__("threading").Event(),
                )

            self.assertEqual(translate.call_count, 2)
            self.assertTrue(translate.call_args_list[1].kwargs["force_cpu"])
            self.assertIn("Olá.", output.read_text(encoding="utf-8-sig"))


if __name__ == "__main__":
    unittest.main()
