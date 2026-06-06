"""Local sealed-bid simulator for quick offline tuning."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import random
from typing import Callable

from bot import (
    BLANK,
    DEFAULT_CONFIG,
    DEFAULT_MODEL,
    SCRABBLE_VALUES,
    TILE_DISTRIBUTION,
    VOWELS,
    BotConfig,
    GameState,
    canonical_signature,
    decide_bid,
    normalize_letter,
)


Bidder = Callable[[GameState, random.Random], int]


@dataclass
class Player:
    name: str
    bidder: Bidder
    rack: str = ""
    budget: int = 100
    score: int = 0


def build_bag(rng: random.Random) -> list[str]:
    bag: list[str] = []
    for letter, count in TILE_DISTRIBUTION.items():
        bag.extend(letter for _ in range(count))
    rng.shuffle(bag)
    return bag


def our_bidder(config: BotConfig = DEFAULT_CONFIG) -> Bidder:
    def bid(state: GameState, rng: random.Random) -> int:
        del rng
        return decide_bid(state, config=config)

    return bid


def random_bidder(state: GameState, rng: random.Random) -> int:
    return rng.randint(0, min(state.budget_remaining, 5))


def face_value_bidder(state: GameState, rng: random.Random) -> int:
    del rng
    letter = normalize_letter(state.offered_letter)
    return min(state.budget_remaining, SCRABBLE_VALUES.get(letter, 0) + 1)


def vowel_hunter_bidder(state: GameState, rng: random.Random) -> int:
    del rng
    letter = normalize_letter(state.offered_letter)
    if letter in VOWELS:
        return min(state.budget_remaining, 7)
    if letter in {"S", BLANK}:
        return min(state.budget_remaining, 8)
    return min(state.budget_remaining, max(0, SCRABBLE_VALUES.get(letter, 0) - 1))


def conservative_bidder(state: GameState, rng: random.Random) -> int:
    del rng
    letter = normalize_letter(state.offered_letter)
    value = 4 if letter in "AEINORSTL" else SCRABBLE_VALUES.get(letter, 0)
    return min(state.budget_remaining, max(0, value // 2))


def run_game(
    rng: random.Random,
    auctions: int = 30,
    starting_budget: int = 100,
    our_config: BotConfig = DEFAULT_CONFIG,
) -> int:
    players = [
        Player("auction_bot", our_bidder(our_config), budget=starting_budget),
        Player("random", random_bidder, budget=starting_budget),
        Player("face_value", face_value_bidder, budget=starting_budget),
        Player("vowel_hunter", vowel_hunter_bidder, budget=starting_budget),
        Player("conservative", conservative_bidder, budget=starting_budget),
    ]

    bag = build_bag(rng)
    for auction_index, offered in enumerate(bag[:auctions]):
        bids: list[int] = []
        for index, player in enumerate(players):
            opponents = tuple(other.rack for j, other in enumerate(players) if j != index)
            state = GameState(
                rack=player.rack,
                offered_letter=offered,
                budget_remaining=player.budget,
                starting_budget=starting_budget,
                auction_index=auction_index,
                total_auctions=auctions,
                opponent_racks=opponents if player.name == "auction_bot" else (),
            )
            bids.append(max(0, min(player.budget, player.bidder(state, rng))))

        high_bid = max(bids)
        if high_bid <= 0:
            continue
        tied = [index for index, bid in enumerate(bids) if bid == high_bid]
        winner = rng.choice(tied)
        players[winner].budget -= high_bid
        players[winner].rack += offered

    for player in players:
        player.score = DEFAULT_MODEL.best_word_score(canonical_signature(player.rack))

    max_score = max(player.score for player in players)
    winners = [index for index, player in enumerate(players) if player.score == max_score]
    return rng.choice(winners)


def run_tournament(
    games: int,
    seed: int,
    auctions: int,
    starting_budget: int,
    our_config: BotConfig = DEFAULT_CONFIG,
) -> dict[str, float]:
    rng = random.Random(seed)
    wins = 0
    for _ in range(games):
        winner = run_game(
            rng,
            auctions=auctions,
            starting_budget=starting_budget,
            our_config=our_config,
        )
        if winner == 0:
            wins += 1
    return {"games": games, "wins": wins, "win_rate": wins / games if games else 0.0}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run mock Scrabble letter auctions.")
    parser.add_argument("--games", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--auctions", type=int, default=30)
    parser.add_argument("--budget", type=int, default=100)
    args = parser.parse_args()

    result = run_tournament(args.games, args.seed, args.auctions, args.budget)
    print(
        f"auction_bot wins {result['wins']:.0f}/{result['games']:.0f} "
        f"({result['win_rate']:.1%})"
    )


if __name__ == "__main__":
    main()
