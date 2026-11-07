"""SM-2 spaced repetition, in plain code. No model involved."""

from dataclasses import dataclass
from datetime import datetime, timedelta

MIN_EASE = 1.3


@dataclass(frozen=True)
class Review:
    ease: float
    interval_days: int
    repetitions: int
    due_at: datetime


def sm2(*, ease: float, interval_days: int, repetitions: int, grade: int, now: datetime) -> Review:
    """`grade` runs from 0 (blackout) to 5 (perfect); below 3 counts as a lapse."""
    if not 0 <= grade <= 5:
        raise ValueError("Grade must be between 0 and 5")
    if grade < 3:
        repetitions, interval_days = 0, 1
    else:
        repetitions += 1
        if repetitions == 1:
            interval_days = 1
        elif repetitions == 2:
            interval_days = 6
        else:
            interval_days = round(interval_days * ease)
    ease = max(MIN_EASE, ease + 0.1 - (5 - grade) * (0.08 + (5 - grade) * 0.02))
    return Review(round(ease, 2), interval_days, repetitions, now + timedelta(days=interval_days))
