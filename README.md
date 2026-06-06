# Scrabble Auction Bot

Deterministic Python bidding engine for a Scrabble-style letter auction with a 15 ms response deadline.

The runtime decision path is intentionally small: normalize the offered tile, look up the rack signature value, compute the marginal word improvement, apply rack-balance and power-tile heuristics, then shade the bid with budget pacing.

## Assumptions

- First-price sealed bid: the winner pays their own bid.
- Final scoring is plain Scrabble tile score for the best word made from your letters.
- No board placement, multipliers, hooks, or cross-checks.
- Rack/final-word cap is 7 letters.
- Blanks are represented as `?`.

If the tournament API differs, update `GameState` and the TODO comment in `bot.py`.

## Files

- `bot.py`: `GameState`, `BotConfig`, `decide_bid`, signature scoring, and rack heuristics.
- `precompute.py`: builds `data/precomputed.json` from a local word list.
- `simulate.py`: mock sealed-bid auctions against simple opponent bots.
- `benchmark.py`: micro-benchmark for the bid deadline.
- `tune.py`: small grid search for a few bidding weights.
- `tests/test_bot.py`: unit tests for scoring, bidding, budget caps, and deadline behavior.

## Run

```bash
python3 -m unittest discover -s tests
python3 benchmark.py
python3 simulate.py --games 1000 --seed 7
```

Build a larger dictionary table:

```bash
python3 precompute.py --word-list data/words.txt --output data/precomputed.json
```

You can also point the bot at a generated table without copying it:

```bash
SCRABBLE_BOT_PRECOMPUTED=/path/to/precomputed.json python3 benchmark.py
```

## Strategy

The bot values a letter using:

```text
private_value =
  face_score
  + scarcity
  + base_letter_value
  + best_word_score_delta
  + leave_value_delta
  + vowel/consonant_balance_delta
  + power_tile_adjustments
  + visible_opponent_denial
  - duplicate_penalty
  - Q_without_U_penalty
```

Then it shades the value by auction stage and budget pacing:

- Early game: conservative, max 15% of remaining budget.
- Mid game: balanced, max 25%.
- Late game: more aggressive, max 45%.
- Win-now letter: max 70%.

`S` and blank receive strong premiums. `Q` is intentionally underbid without `U` or blank support. `X` and `Z` need vowel support or short-word access.

## Integration

Import and call:

```python
from bot import GameState, decide_bid

bid = decide_bid(
    GameState(
        rack="TRAIN",
        offered_letter="S",
        budget_remaining=100,
        starting_budget=100,
        auction_index=18,
        total_auctions=30,
    )
)
```

No live LLM call is used during bidding.
