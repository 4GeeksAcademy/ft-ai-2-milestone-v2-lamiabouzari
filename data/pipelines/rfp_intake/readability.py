"""Readability metrics stored with RFP metadata. No extra dependency."""

from __future__ import annotations

import re

_WORD = re.compile(r"[A-Za-z0-9']+")
_SENTENCE = re.compile(r"[.!?]+")
_VOWEL_GROUP = re.compile(r"[aeiouy]+")


def _syllables(word: str) -> int:
    cleaned = re.sub(r"[^a-z]", "", word.lower())
    if not cleaned:
        return 0
    count = len(_VOWEL_GROUP.findall(cleaned))
    if cleaned.endswith("e") and count > 1:
        count -= 1
    return max(count, 1)


def readability_metrics(text: str) -> dict[str, float | int]:
    """Word, sentence, and Flesch reading-ease figures for the Markdown text."""
    words = _WORD.findall(text)
    sentence_count = len([chunk for chunk in _SENTENCE.split(text) if chunk.strip()])
    word_count = len(words)
    safe_sentences = max(sentence_count, 1)
    syllable_count = sum(_syllables(word) for word in words)
    avg_words = word_count / safe_sentences
    avg_syllables = (syllable_count / word_count) if word_count else 0.0
    flesch = 206.835 - (1.015 * avg_words) - (84.6 * avg_syllables)
    return {
        "word_count": word_count,
        "sentence_count": sentence_count,
        "avg_words_per_sentence": round(avg_words, 2),
        "flesch_reading_ease": round(flesch, 2),
    }
