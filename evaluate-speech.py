"""Reading + speaking evaluator using Whisper, pause analysis, and SCORM export.

What this version adds:
- pause-aware fluency scoring (fewer/shorter pauses => better score)
- multi-audio support (evaluate several voices/recordings in one run)
- SCORM-ready export files (JSON + JS snippet)
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import librosa
import numpy as np
import whisper
from jiwer import wer

# ====== Config ======
# You can pass files via CLI too, e.g.:
#   py evaluate_speech.py student1.wav student2.wav
AUDIO_FILES = ["student.wav"]
TARGET_TEXT = "I study under the palm tree every morning."
MODEL_SIZE = "base"  # tiny / base / small
PAUSE_MIN_SEC = 0.35  # anything >= this is counted as a pause
SCORM_JSON = "scorm_result.json"
SCORM_JS = "scorm_result.js"
# ====================


@dataclass
class Scores:
    file: str
    transcript: str
    duration_sec: float
    word_error_rate: float
    wpm: float
    pause_count: int
    pause_ratio: float
    accuracy: float
    fluency: float
    pronunciation_proxy: float
    final_score: float


def normalize_text(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text


def find_ffmpeg() -> str | None:
    if shutil.which("ffmpeg"):
        return "ffmpeg"

    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        candidate = os.path.join(
            local_app_data,
            "Microsoft",
            "WinGet",
            "Packages",
            "Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe",
            "ffmpeg-8.1-full_build",
            "bin",
            "ffmpeg.exe",
        )
        if os.path.isfile(candidate):
            return candidate
    return None


def ensure_ffmpeg_ready() -> str:
    ffmpeg_path = find_ffmpeg()
    if not ffmpeg_path:
        raise RuntimeError(
            "FFmpeg not found. Install with `winget install Gyan.FFmpeg` and reopen terminal."
        )

    if ffmpeg_path != "ffmpeg":
        ffmpeg_dir = os.path.dirname(ffmpeg_path)
        os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")

    subprocess.run([ffmpeg_path, "-version"], check=True, capture_output=True, text=True)
    return ffmpeg_path


def calc_wpm(word_count: int, duration_sec: float) -> float:
    if duration_sec <= 0:
        return 0.0
    return (word_count / duration_sec) * 60.0


def analyze_pauses(y: np.ndarray, sr: int, min_pause_sec: float = PAUSE_MIN_SEC) -> tuple[int, float]:
    """Return (pause_count, pause_ratio).

    pause_ratio = total silence duration / full duration.
    """
    if sr <= 0 or len(y) == 0:
        return 0, 0.0

    duration_sec = len(y) / sr
    intervals = librosa.effects.split(y, top_db=35)

    if len(intervals) == 0:
        return 0, 1.0

    speech_sec = float(sum((end - start) / sr for start, end in intervals))
    silence_sec = max(0.0, duration_sec - speech_sec)

    # Count significant pauses between speech chunks
    pause_count = 0
    for i in range(1, len(intervals)):
        prev_end = intervals[i - 1][1]
        curr_start = intervals[i][0]
        gap = (curr_start - prev_end) / sr
        if gap >= min_pause_sec:
            pause_count += 1

    pause_ratio = float(np.clip(silence_sec / duration_sec, 0.0, 1.0))
    return pause_count, pause_ratio


def fluency_score(wpm: float, pause_ratio: float, pause_count: int) -> float:
    # Base speed score
    if wpm < 50:
        speed = 35
    elif wpm < 90:
        speed = 65
    elif wpm <= 160:
        speed = 100
    elif wpm <= 200:
        speed = 80
    else:
        speed = 60

    # Penalize pauses to encourage smoother reading
    pause_penalty = min(35.0, (pause_ratio * 45.0) + (pause_count * 1.5))
    return float(np.clip(speed - pause_penalty, 0.0, 100.0))


def evaluate_one(model: whisper.Whisper, audio_file: str, target_text: str) -> Scores:
    path = Path(audio_file)
    if not path.is_file():
        raise FileNotFoundError(f"Audio file not found: {audio_file}")

    result = model.transcribe(str(path), language="en", task="transcribe")
    transcript = result.get("text", "").strip()
    segments = result.get("segments", [])

    y, sr = librosa.load(str(path), sr=None)
    duration_sec = len(y) / sr if sr else 0.0

    ref = normalize_text(target_text)
    hyp = normalize_text(transcript)

    word_error_rate = wer(ref, hyp)
    accuracy = max(0.0, 100.0 * (1.0 - word_error_rate))

    words_spoken = len(hyp.split()) if hyp else 0
    wpm = calc_wpm(words_spoken, duration_sec)

    pause_count, pause_ratio = analyze_pauses(y, sr)
    flu = fluency_score(wpm, pause_ratio, pause_count)

    if segments:
        avg_logprob = float(np.mean([seg.get("avg_logprob", -2.0) for seg in segments]))
    else:
        avg_logprob = -2.0
    pronunciation_proxy = float(np.clip(np.exp(avg_logprob), 0.0, 1.0) * 100.0)

    final_score = (0.50 * accuracy) + (0.30 * flu) + (0.20 * pronunciation_proxy)

    return Scores(
        file=str(path),
        transcript=transcript,
        duration_sec=float(duration_sec),
        word_error_rate=float(word_error_rate),
        wpm=float(wpm),
        pause_count=int(pause_count),
        pause_ratio=float(pause_ratio),
        accuracy=float(accuracy),
        fluency=float(flu),
        pronunciation_proxy=float(pronunciation_proxy),
        final_score=float(final_score),
    )


def export_scorm(best: Scores, all_scores: list[Scores]) -> None:
    payload = {
        "target_text": TARGET_TEXT,
        "best_attempt": asdict(best),
        "attempt_count": len(all_scores),
        "all_attempts": [asdict(s) for s in all_scores],
        "scorm": {
            "score_raw": round(best.final_score, 1),
            "score_min": 0,
            "score_max": 100,
            "lesson_status": "passed" if best.final_score >= 70 else "failed",
            "completion_status": "completed",
        },
    }

    Path(SCORM_JSON).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    # SCORM API wrapper snippet (works if parent course exposes SCORM API helpers)
    js = f"""(function() {{
  var score = {round(best.final_score, 1)};
  var status = score >= 70 ? 'passed' : 'failed';

  // SCORM 1.2
  if (window.API && typeof window.API.LMSSetValue === 'function') {{
    window.API.LMSInitialize('');
    window.API.LMSSetValue('cmi.core.score.min', '0');
    window.API.LMSSetValue('cmi.core.score.max', '100');
    window.API.LMSSetValue('cmi.core.score.raw', String(score));
    window.API.LMSSetValue('cmi.core.lesson_status', status);
    window.API.LMSCommit('');
    return;
  }}

  // SCORM 2004
  if (window.API_1484_11 && typeof window.API_1484_11.SetValue === 'function') {{
    window.API_1484_11.Initialize('');
    window.API_1484_11.SetValue('cmi.score.min', '0');
    window.API_1484_11.SetValue('cmi.score.max', '100');
    window.API_1484_11.SetValue('cmi.score.raw', String(score));
    window.API_1484_11.SetValue('cmi.success_status', status === 'passed' ? 'passed' : 'failed');
    window.API_1484_11.SetValue('cmi.completion_status', 'completed');
    window.API_1484_11.Commit('');
  }}
}})();
"""
    Path(SCORM_JS).write_text(js, encoding="utf-8")


def print_report(scores: list[Scores]) -> None:
    print("\n===== SPEAKING + READING REPORT =====")
    for idx, s in enumerate(scores, start=1):
        print(f"\nAttempt #{idx}: {s.file}")
        print(f"Transcript            : {s.transcript}")
        print(f"Duration (sec)        : {s.duration_sec:.2f}")
        print(f"WPM                   : {s.wpm:.2f}")
        print(f"Pause count           : {s.pause_count}")
        print(f"Pause ratio           : {s.pause_ratio:.3f}")
        print(f"WER                   : {s.word_error_rate:.3f}")
        print(f"Accuracy (/100)       : {s.accuracy:.1f}")
        print(f"Fluency (/100)        : {s.fluency:.1f}")
        print(f"Pron proxy (/100)     : {s.pronunciation_proxy:.1f}")
        print(f"Final score (/100)    : {s.final_score:.1f}")

    best = max(scores, key=lambda s: s.final_score)
    print("\n--- Best Attempt ---")
    print(f"File                  : {best.file}")
    print(f"Best final score      : {best.final_score:.1f}")
    print(f"Exported              : {SCORM_JSON}, {SCORM_JS}")


def main() -> int:
    cli_files = sys.argv[1:] if len(sys.argv) > 1 else AUDIO_FILES
    if not cli_files:
        print("❌ No audio files provided.")
        return 1

    try:
        ensure_ffmpeg_ready()
        print(f"Loading Whisper model: {MODEL_SIZE}")
        model = whisper.load_model(MODEL_SIZE)

        scores = [evaluate_one(model, f, TARGET_TEXT) for f in cli_files]
        print_report(scores)
        best = max(scores, key=lambda s: s.final_score)
        export_scorm(best, scores)
        return 0
    except Exception as exc:
        print("\n❌ Evaluation failed.")
        print(f"Reason: {exc}")
        print(
            "\nQuick checks:\n"
            "1) Audio files exist in this folder (or pass full paths).\n"
            "2) `ffmpeg -version` works in a NEW terminal.\n"
            "3) If not, run: `winget install Gyan.FFmpeg` then reopen terminal."
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
