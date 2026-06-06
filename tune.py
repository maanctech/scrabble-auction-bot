"""Tiny offline grid search for bidding weights.

This is intentionally small. Once tournament logs are available, replace the
mock opponents in simulate.py with observed opponent policies or bid histories.
"""

from __future__ import annotations

from dataclasses import replace

from bot import DEFAULT_CONFIG
from simulate import run_tournament


def main() -> None:
    candidates = []
    for pacing_beta in (1.5, 2.5, 3.0, 4.0):
        for word_delta_weight in (1.8, 2.35, 2.8):
            config = replace(
                DEFAULT_CONFIG,
                pacing_beta=pacing_beta,
                word_delta_weight=word_delta_weight,
            )
            result = run_tournament(
                games=150,
                seed=11,
                auctions=30,
                starting_budget=100,
                our_config=config,
            )
            candidates.append((result["win_rate"], pacing_beta, word_delta_weight))

    candidates.sort(reverse=True)
    for win_rate, pacing_beta, word_delta_weight in candidates[:5]:
        print(
            f"win_rate={win_rate:.1%} "
            f"pacing_beta={pacing_beta} "
            f"word_delta_weight={word_delta_weight}"
        )


if __name__ == "__main__":
    main()
