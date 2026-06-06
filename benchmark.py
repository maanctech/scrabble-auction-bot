"""Micro-benchmark for the 15 ms bid deadline."""

from __future__ import annotations

import statistics
import time

from bot import GameState, decide_bid


def main() -> None:
    states = [
        GameState(rack="TRAIN", offered_letter="S", budget_remaining=100, auction_index=2),
        GameState(rack="TRAI", offered_letter="N", budget_remaining=88, auction_index=9),
        GameState(rack="QAT", offered_letter="U", budget_remaining=64, auction_index=14),
        GameState(rack="RSTLNE", offered_letter="?", budget_remaining=42, auction_index=22),
        GameState(rack="BCDFG", offered_letter="E", budget_remaining=35, auction_index=25),
    ]

    for state in states:
        decide_bid(state)

    samples_ns: list[int] = []
    iterations = 25_000
    for index in range(iterations):
        state = states[index % len(states)]
        start = time.perf_counter_ns()
        decide_bid(state)
        samples_ns.append(time.perf_counter_ns() - start)

    avg_ms = statistics.mean(samples_ns) / 1_000_000
    p95_ms = statistics.quantiles(samples_ns, n=20)[18] / 1_000_000
    worst_ms = max(samples_ns) / 1_000_000
    print(f"iterations: {iterations}")
    print(f"average_ms: {avg_ms:.6f}")
    print(f"p95_ms: {p95_ms:.6f}")
    print(f"worst_ms: {worst_ms:.6f}")
    print("deadline_ms: 15.000000")


if __name__ == "__main__":
    main()
