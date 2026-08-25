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


if __name__ == "__main__":
    unittest.main()
