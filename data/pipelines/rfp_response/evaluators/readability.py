"""Readability evaluator. Returns its own result and does not mutate shared state."""

from __future__ import annotations

import re

from data.pipelines.rfp_intake.readability import readability_metrics

_HEADING = re.compile(r"^#{1,3} ", re.MULTILINE)
_MIN_WORDS = 40
_MAX_SENTENCE_WORDS = 40


def _sentences(text: str) -> list[str]:
    parts = re.split(r"[\n.!?]+", text)
    return [part.strip() for part in parts if part.strip()]


def evaluate(text: str) -> dict:
    """Score structure, length, and sentence size. Feedback names the failing sentence."""
    metrics = readability_metrics(text)
    problems: list[str] = []
    word_count = int(metrics["word_count"])
    if word_count < _MIN_WORDS:
        problems.append(
            f"The draft has {word_count} words. Write at least {_MIN_WORDS} words in complete sentences."
        )
    if _HEADING.search(text) is None:
        problems.append("Add a Markdown heading that names this department section.")
    for index, sentence in enumerate(_sentences(text), start=1):
        length = len(sentence.split())
        if length > _MAX_SENTENCE_WORDS:
            problems.append(
                f"Sentence {index} has {length} words. Split it so each sentence stays at or under {_MAX_SENTENCE_WORDS} words."
            )
    flesch = float(metrics["flesch_reading_ease"])
    if word_count >= _MIN_WORDS and flesch < 20:
        problems.append(
            f"Flesch reading ease is {flesch}. Use shorter words and shorter sentences."
        )
    if problems:
        score = max(0, 100 - (25 * len(problems)))
    else:
        score = max(0, min(100, round(flesch)))
    return {
        "pass": not problems,
        "score": score,
        "details": {
            "word_count": word_count,
            "sentence_count": metrics["sentence_count"],
            "flesch_reading_ease": metrics["flesch_reading_ease"],
            "problems": problems,
        },
    }
