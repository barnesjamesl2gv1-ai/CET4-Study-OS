"""M0 review helpers. Suggestions never become verified without human confirmation."""

from __future__ import annotations

import re
import shutil
import subprocess
from collections import Counter
from pathlib import Path

KINDS = {
    "listening_news": 7, "listening_dialogue": 8, "listening_passage": 10,
    "cloze": 10, "matching": 10, "careful": 10, "writing": 1, "translation": 1,
}


def check_alignment(questions: list[dict], answers: list[dict]) -> dict:
    """Check explicit IDs and types; extracted/OCR text alone cannot prove alignment."""
    issues = []
    question_ids = [str(item.get("number")) for item in questions]
    answer_ids = [str(item.get("number")) for item in answers]
    for label, identifiers in (("question", question_ids), ("answer", answer_ids)):
        for number, count in Counter(identifiers).items():
            if count > 1:
                issues.append(f"duplicate_{label}:{number}")
    question_map = {str(item.get("number")): item for item in questions}
    answer_map = {str(item.get("number")): item for item in answers}
    for number in sorted(question_map.keys() | answer_map.keys()):
        if number not in question_map:
            issues.append(f"answer_without_question:{number}")
        elif number not in answer_map and question_map[number].get("kind") not in ("writing", "translation"):
            issues.append(f"missing_answer:{number}")
        elif number in answer_map:
            choices = question_map[number].get("options") or []
            value = answer_map[number].get("answer")
            if choices and value not in choices:
                issues.append(f"invalid_answer:{number}")
    counts = Counter(item.get("kind") for item in questions)
    for kind, expected in KINDS.items():
        if counts[kind] != expected:
            issues.append(f"count_{kind}:{counts[kind]}/{expected}")
    return {"structure_valid": not issues, "human_verified": False, "issues": issues}


def suggest_segments(audio_path: Path, duration_ms: int) -> list[dict]:
    """Find silence midpoints as candidate cut marks, preserving the full source audio."""
    executable = shutil.which("ffmpeg")
    if not executable:
        return []
    completed = subprocess.run(
        [executable, "-hide_banner", "-nostdin", "-i", str(audio_path), "-af",
         "silencedetect=noise=-35dB:d=0.7", "-f", "null", "-"],
        capture_output=True, text=True, timeout=300,
    )
    if completed.returncode != 0:
        raise ValueError("无法分析音频")
    starts = [float(value) for value in re.findall(r"silence_start:\s*([0-9.]+)", completed.stderr)]
    ends = [float(value) for value in re.findall(r"silence_end:\s*([0-9.]+)", completed.stderr)]
    cuts = [0]
    for start, end in zip(starts, ends):
        midpoint = round((start + end) * 500)
        if cuts[-1] + 1000 < midpoint < duration_ms - 1000:
            cuts.append(midpoint)
    cuts.append(duration_ms)
    return [{"start_ms": a, "end_ms": b, "confirmation": "pending"}
            for a, b in zip(cuts, cuts[1:])]


def confirm_segment(start_ms: int, end_ms: int, duration_ms: int, question_numbers: list[int]) -> dict:
    if not (0 <= start_ms < end_ms <= duration_ms):
        raise ValueError("片段边界超出音频范围")
    if not question_numbers or any(number < 1 for number in question_numbers):
        raise ValueError("请指定至少一个有效题号")
    return {"start_ms": start_ms, "end_ms": end_ms,
            "question_numbers": sorted(set(question_numbers)), "confirmation": "confirmed"}
