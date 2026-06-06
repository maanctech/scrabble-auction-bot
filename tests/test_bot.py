from __future__ import annotations

import time
import unittest

from bot import (
    DEFAULT_MODEL,
    GameState,
    canonical_signature,
    decide_bid,
    score_components,
    word_score,
)


class BotTests(unittest.TestCase):
    def test_scrabble_values_and_signatures(self) -> None:
        self.assertEqual(word_score("QUIZ"), 22)
        self.assertEqual(canonical_signature("TRAIN"), "AINRT")
        self.assertEqual(canonical_signature(["A", "blank", "S"]), "?AS")

    def test_best_word_improvement_values_s(self) -> None:
        current = DEFAULT_MODEL.best_word_score("TRAIN")
        with_s = DEFAULT_MODEL.best_word_score("TRAINS")
        self.assertGreater(with_s, current)
        self.assertGreater(DEFAULT_MODEL.marginal_word_score("TRAIN", "S"), 0)

    def test_blank_is_high_priority(self) -> None:
        blank_bid = decide_bid(
            GameState(rack="TRAI", offered_letter="?", budget_remaining=100, auction_index=6)
        )
        q_bid = decide_bid(
            GameState(rack="TRAI", offered_letter="Q", budget_remaining=100, auction_index=6)
        )
        self.assertGreater(blank_bid, q_bid)

    def test_budget_cap_early_game(self) -> None:
        bid = decide_bid(
            GameState(rack="RSTLNE", offered_letter="?", budget_remaining=100, auction_index=0)
        )
        self.assertLessEqual(bid, 15)

    def test_q_without_u_is_penalized(self) -> None:
        q_without_u = score_components(GameState(rack="TRAI", offered_letter="Q"))[
            "private_value"
        ]
        u_with_q = score_components(GameState(rack="QAT", offered_letter="U"))[
            "private_value"
        ]
        self.assertLess(float(q_without_u), float(u_with_q))

    def test_incomplete_state_falls_back_to_zero(self) -> None:
        self.assertEqual(decide_bid(GameState(offered_letter="", budget_remaining=100)), 0)
        self.assertEqual(decide_bid(GameState(rack="TRAIN", offered_letter="S", budget_remaining=0)), 0)

    def test_bid_function_is_under_deadline(self) -> None:
        states = [
            GameState(rack="TRAIN", offered_letter="S", budget_remaining=100),
            GameState(rack="QAT", offered_letter="U", budget_remaining=80, auction_index=12),
            GameState(rack="RSTLNE", offered_letter="?", budget_remaining=50, auction_index=22),
            GameState(rack="ETAOINSHRDLU", offered_letter="Z", budget_remaining=45, auction_index=25),
        ]
        for state in states:
            decide_bid(state)

        iterations = 5000
        start = time.perf_counter()
        for index in range(iterations):
            decide_bid(states[index % len(states)])
        avg_ms = (time.perf_counter() - start) * 1000 / iterations
        self.assertLess(avg_ms, 15.0)


if __name__ == "__main__":
    unittest.main()
