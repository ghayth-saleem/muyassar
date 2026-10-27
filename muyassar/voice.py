"""Speech to text for the voice assistant: local faster-whisper, Arabic.

    from muyassar.voice import transcribe
    result = transcribe(audio_bytes)   # {"text", "duration", "ms", "model"}

The audio is decoded from memory and never written to disk or logged; only
the transcript is kept, marked source: voice. That matters for the health-data
scenario: what the system holds is what it heard, as text, and nothing else.

MUYASSAR_WHISPER_MODEL picks the model, MUYASSAR_WHISPER_DEVICE the device.
Defaults: large-v3-turbo on the CPU in int8. Measured on the dev laptop
(RTX 3050, 4 GB) for a 13.9 s clip: 1.3 s on the GPU alone, but the server's
retrieval models already hold 3.2–3.8 GB, so next to them Whisper spills into
shared memory and takes 17–22 s; on the CPU it takes 14.6 s, about real time.
large-v3 is 2.8 s on a free GPU and about three times turbo's time on the CPU.
Set MUYASSAR_WHISPER_DEVICE=cuda on a GPU with room for both.
"""
import io
import os
import time

from muyassar import ROOT

MODEL = os.environ.get("MUYASSAR_WHISPER_MODEL", "large-v3-turbo")
DEVICE = os.environ.get("MUYASSAR_WHISPER_DEVICE", "cpu")
# A plain folder, not the Hugging Face cache: on Windows the cache needs
# symlinks, which fail without developer mode (WinError 1314). Git-ignored.
MODEL_DIR = ROOT / "models" / "whisper"
MAX_BYTES = 10 * 1024 * 1024  # about 10 minutes of browser opus; a request is a sentence or two
_model = None


def model_path() -> str:
    """Local folder of the model, downloaded on first use as plain files."""
    from faster_whisper.utils import download_model

    target = MODEL_DIR / MODEL
    if (target / "model.bin").is_file():
        return str(target)
    return download_model(MODEL, output_dir=str(target))


def _load():
    global _model
    if _model is None:
        from faster_whisper import WhisperModel

        gpu = DEVICE == "cuda"
        _model = WhisperModel(model_path(), device=DEVICE, compute_type="int8_float16" if gpu else "int8",
                              cpu_threads=os.cpu_count() or 4)
    return _model


def transcribe(audio: bytes) -> dict:
    if not audio:
        raise ValueError("ما وصل صوت")
    if len(audio) > MAX_BYTES:
        raise ValueError("الملف أكبر من 10 ميغا")
    started = time.perf_counter()
    segments, info = _load().transcribe(io.BytesIO(audio), language="ar", beam_size=5, vad_filter=True)
    text = " ".join(s.text.strip() for s in segments).strip()
    return {
        "text": text,
        "duration": round(info.duration, 1),
        "ms": round((time.perf_counter() - started) * 1000),
        "model": f"faster-whisper {MODEL}",
    }
