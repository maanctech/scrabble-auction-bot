"""Build offline signature tables for the Scrabble auction bot."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from bot import (
    MINI_DICTIONARY,
    ValuationModel,
    canonical_signature,
    clean_letters,
    word_score,
)


def load_words(path: Path | None) -> list[str]:
    if path is None or not path.exists():
        return list(MINI_DICTIONARY)
    words: list[str] = []
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            word = clean_letters(line.strip())
            if word:
                words.append(word)
    return words


def build_payload(words: list[str], max_word_length: int) -> dict[str, object]:
    model = ValuationModel.from_words(words, max_word_length=max_word_length)
    return {
        "max_word_length": max_word_length,
        "word_count": len(words),
        "signature_count": len(model.best_exact_score_by_signature),
        "best_exact_score_by_signature": model.best_exact_score_by_signature,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Precompute Scrabble word signature scores.")
    parser.add_argument("--word-list", type=Path, default=None, help="Path to dictionary word list.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/precomputed.json"),
        help="Output JSON path.",
    )
    parser.add_argument("--max-word-length", type=int, default=7)
    args = parser.parse_args()

    words = [
        word
        for word in load_words(args.word_list)
        if 1 <= len(clean_letters(word)) <= args.max_word_length
    ]
    payload = build_payload(words, args.max_word_length)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, separators=(",", ":"), sort_keys=True)
    print(
        "wrote",
        args.output,
        "with",
        payload["signature_count"],
        "signatures from",
        payload["word_count"],
        "words",
    )


if __name__ == "__main__":
    main()
