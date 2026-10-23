from unittest.mock import patch

import pytest

from backend.m0_review import check_alignment, confirm_segment, suggest_segments


def test_alignment_detects_missing_duplicate_and_invalid_answer():
    result = check_alignment(
        [{"number": 1, "kind": "careful", "options": ["A", "B"]},
         {"number": 1, "kind": "careful", "options": ["A", "B"]},
         {"number": 2, "kind": "careful", "options": ["A", "B"]}],
        [{"number": 1, "answer": "C"}],
    )
    assert "duplicate_question:1" in result["issues"]
    assert "invalid_answer:1" in result["issues"]
    assert "missing_answer:2" in result["issues"]
    assert not result["structure_valid"]


def test_segment_suggestion_remains_pending():
    class Result:
        returncode = 0
        stderr = "silence_start: 2.0\nsilence_end: 3.0\n"

    with patch("backend.m0_review.shutil.which", return_value="ffmpeg"), patch(
        "backend.m0_review.subprocess.run", return_value=Result()
    ):
        segments = suggest_segments("sample.mp3", 5000)
    assert segments == [
        {"start_ms": 0, "end_ms": 2500, "confirmation": "pending"},
        {"start_ms": 2500, "end_ms": 5000, "confirmation": "pending"},
    ]


def test_confirm_segment_bounds_and_shared_group():
    with pytest.raises(ValueError):
        confirm_segment(0, 5001, 5000, [1])
    assert confirm_segment(0, 5000, 5000, [2, 1, 2])["question_numbers"] == [1, 2]
