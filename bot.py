"""Deterministic Scrabble-style letter auction bidding engine.

The hot path is `decide_bid(state)`. It avoids I/O and dictionary scans during
the bid decision. Expensive dictionary work is compiled into a signature table
at startup or by `precompute.py`.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import json
import os
from pathlib import Path
from typing import Iterable


ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
VOWELS = frozenset("AEIOU")
BLANK = "?"

SCRABBLE_VALUES: dict[str, int] = {
    BLANK: 0,
    "A": 1,
    "B": 3,
    "C": 3,
    "D": 2,
    "E": 1,
    "F": 4,
    "G": 2,
    "H": 4,
    "I": 1,
    "J": 8,
    "K": 5,
    "L": 1,
    "M": 3,
    "N": 1,
    "O": 1,
    "P": 3,
    "Q": 10,
    "R": 1,
    "S": 1,
    "T": 1,
    "U": 1,
    "V": 4,
    "W": 4,
    "X": 8,
    "Y": 4,
    "Z": 10,
}

TILE_DISTRIBUTION: dict[str, int] = {
    "A": 9,
    "B": 2,
    "C": 2,
    "D": 4,
    "E": 12,
    "F": 2,
    "G": 3,
    "H": 2,
    "I": 9,
    "J": 1,
    "K": 1,
    "L": 4,
    "M": 2,
    "N": 6,
    "O": 8,
    "P": 2,
    "Q": 1,
    "R": 6,
    "S": 4,
    "T": 6,
    "U": 4,
    "V": 2,
    "W": 2,
    "X": 1,
    "Y": 2,
    "Z": 1,
    BLANK: 2,
}

# Private auction value, not face value. Q is intentionally low because it is
# high-risk without U or blank support.
LETTER_BASE: dict[str, float] = {
    BLANK: 14.0,
    "S": 12.0,
    "E": 7.0,
    "A": 7.0,
    "I": 6.0,
    "O": 6.0,
    "R": 6.0,
    "T": 6.0,
    "N": 6.0,
    "L": 5.0,
    "D": 5.0,
    "U": 5.0,
    "G": 4.0,
    "C": 4.0,
    "M": 4.0,
    "P": 4.0,
    "H": 4.0,
    "Y": 4.0,
    "F": 3.0,
    "W": 3.0,
    "B": 3.0,
    "V": 2.0,
    "K": 2.0,
    "X": 5.0,
    "Z": 5.0,
    "J": 3.0,
    "Q": 1.0,
}

_AVERAGE_TILE_COUNT = sum(TILE_DISTRIBUTION.values()) / len(TILE_DISTRIBUTION)
SCARCITY_BONUS: dict[str, float] = {
    letter: min(3.5, _AVERAGE_TILE_COUNT / count)
    for letter, count in TILE_DISTRIBUTION.items()
}

# Fallback words are deliberately small but cover common rack patterns and
# power-tile short words. Replace with an official tournament lexicon if given.
MINI_DICTIONARY: tuple[str, ...] = (
    "AA",
    "AB",
    "AD",
    "AE",
    "AG",
    "AH",
    "AI",
    "AL",
    "AM",
    "AN",
    "AR",
    "AS",
    "AT",
    "AW",
    "AX",
    "AY",
    "BA",
    "BE",
    "BI",
    "BO",
    "BY",
    "DA",
    "DE",
    "DO",
    "ED",
    "EF",
    "EH",
    "EL",
    "EM",
    "EN",
    "ER",
    "ES",
    "ET",
    "EW",
    "EX",
    "FA",
    "FE",
    "GO",
    "HA",
    "HE",
    "HI",
    "HM",
    "HO",
    "ID",
    "IF",
    "IN",
    "IS",
    "IT",
    "JO",
    "KA",
    "KI",
    "KO",
    "LA",
    "LI",
    "LO",
    "MA",
    "ME",
    "MI",
    "MM",
    "MO",
    "MU",
    "MY",
    "NA",
    "NE",
    "NO",
    "NU",
    "OD",
    "OE",
    "OF",
    "OH",
    "OI",
    "OM",
    "ON",
    "OP",
    "OR",
    "OS",
    "OW",
    "OX",
    "OY",
    "PA",
    "PE",
    "PI",
    "PO",
    "QI",
    "RE",
    "SH",
    "SI",
    "SO",
    "TA",
    "TE",
    "TI",
    "TO",
    "UH",
    "UM",
    "UN",
    "UP",
    "US",
    "UT",
    "WE",
    "WO",
    "XI",
    "XU",
    "YA",
    "YE",
    "YO",
    "ZA",
    "ACE",
    "ACT",
    "AGE",
    "AIR",
    "ALE",
    "ANT",
    "APE",
    "ARE",
    "ART",
    "ATE",
    "AXE",
    "BAD",
    "BAG",
    "BAR",
    "BAT",
    "BED",
    "BET",
    "BOA",
    "BOY",
    "CAB",
    "CAD",
    "CAN",
    "CAR",
    "CAT",
    "COG",
    "COT",
    "COW",
    "DOG",
    "EAR",
    "EAT",
    "ERA",
    "FAR",
    "FAT",
    "FED",
    "FIG",
    "FOX",
    "GIN",
    "HAT",
    "HEN",
    "HER",
    "HIT",
    "ICE",
    "INK",
    "JAR",
    "JET",
    "JOT",
    "JOY",
    "KEY",
    "LAD",
    "LAG",
    "LIE",
    "LOG",
    "MAN",
    "MAT",
    "MIX",
    "NET",
    "NEW",
    "NOW",
    "OAR",
    "OAT",
    "PAN",
    "PAT",
    "PEN",
    "PIE",
    "QAT",
    "RAN",
    "RAT",
    "ROD",
    "ROW",
    "SEA",
    "SET",
    "SIN",
    "SIT",
    "SUN",
    "TAN",
    "TAR",
    "TEA",
    "TEN",
    "TIN",
    "TON",
    "VAN",
    "WAR",
    "WIN",
    "WIT",
    "YAK",
    "YAM",
    "ZEN",
    "ZIT",
    "ABLE",
    "ACED",
    "ACES",
    "ACRE",
    "AGED",
    "ANTE",
    "AXES",
    "BARE",
    "BATS",
    "BEAR",
    "CATS",
    "DEAL",
    "DEAR",
    "EARN",
    "EAST",
    "EATS",
    "GEAR",
    "HATS",
    "LATE",
    "LEAD",
    "LEAN",
    "MEAN",
    "MEAT",
    "NEAR",
    "NOTE",
    "RATS",
    "READ",
    "REAL",
    "ROSE",
    "SALT",
    "SAND",
    "SEAT",
    "STAR",
    "TARS",
    "TEAM",
    "TEAR",
    "TONE",
    "TRAIN",
    "STARE",
    "TEARS",
    "RATES",
    "ASTER",
    "SNARE",
    "STORE",
    "STONE",
    "TONES",
    "DATES",
    "QUAIL",
    "QUIZ",
    "ZONES",
    "AXIOM",
    "TRAIN",
    "TRAINS",
    "STARED",
    "SALTER",
    "RETAIN",
    "SATIRE",
    "TASTER",
    "ZONERS",
    "QUIZES",
    "QUIZZES",
)


@dataclass(frozen=True)
class GameState:
    """Runtime state supplied to the bidding engine.

    TODO: adjust these fields to match the tournament API exactly once it is
    published. This version assumes first-price auctions, no board placement,
    a final rack/word cap of 7, and plain Scrabble letter scoring.
    """

    rack: str = ""
    offered_letter: str = ""
    budget_remaining: int = 100
    starting_budget: int = 100
    auction_index: int = 0
    total_auctions: int = 30
    opponent_racks: tuple[str, ...] = ()
    score_to_beat: int | None = None


@dataclass(frozen=True)
class BotConfig:
    max_word_length: int = 7
    face_score_weight: float = 0.55
    base_letter_weight: float = 0.42
    scarcity_weight: float = 0.85
    word_delta_weight: float = 2.35
    leave_delta_weight: float = 0.50
    balance_delta_weight: float = 1.15
    opponent_denial_weight: float = 0.35
    max_denial_bonus: float = 7.0
    duplicate_penalty_weight: float = 1.0
    q_without_u_penalty: float = 8.0
    minimum_private_value: float = 1.25
    winning_delta_threshold: int = 8
    winning_score_margin: int = 2
    early_aggression: float = 0.45
    mid_aggression: float = 0.60
    late_aggression: float = 0.80
    winning_aggression: float = 0.95
    early_cap_fraction: float = 0.15
    mid_cap_fraction: float = 0.25
    late_cap_fraction: float = 0.45
    winning_cap_fraction: float = 0.70
    pacing_beta: float = 3.0
    tiny_bid: int = 1


DEFAULT_CONFIG = BotConfig()


def normalize_letter(letter: object) -> str:
    """Normalize a tournament letter token to A-Z or '?'."""

    if letter is None:
        return ""
    text = str(letter).strip().upper()
    if not text:
        return ""
    if text in {"?", "*", "_", "BLANK", "WILD"}:
        return BLANK
    first = text[0]
    if first in ALPHABET:
        return first
    return ""


def clean_letters(letters: object) -> str:
    if letters is None:
        return ""
    if isinstance(letters, str):
        raw = letters
        cleaned = []
        for char in raw:
            if char.upper() in ALPHABET:
                cleaned.append(char.upper())
            elif char in {"?", "*", "_"}:
                cleaned.append(BLANK)
        return "".join(cleaned)
    try:
        iterator = iter(letters)  # type: ignore[arg-type]
    except TypeError:
        normalized = normalize_letter(letters)
        return normalized
    else:
        return "".join(
            normalized for item in iterator if (normalized := normalize_letter(item))
        )


def canonical_signature(letters: object) -> str:
    return "".join(sorted(clean_letters(letters)))


def add_letter_to_signature(signature: str, letter: object) -> str:
    normalized = normalize_letter(letter)
    if not normalized:
        return canonical_signature(signature)
    return canonical_signature(f"{signature}{normalized}")


def word_score(word: str) -> int:
    return sum(SCRABBLE_VALUES.get(normalize_letter(char), 0) for char in word)


def letter_count_tuple(signature: str) -> tuple[int, ...]:
    counts = [0] * len(ALPHABET)
    for char in canonical_signature(signature).replace(BLANK, ""):
        counts[ord(char) - ord("A")] += 1
    return tuple(counts)


@lru_cache(maxsize=200_000)
def subset_signatures(signature: str, max_len: int = 7) -> tuple[str, ...]:
    """Return unique sorted subset signatures up to max_len."""

    signature = canonical_signature(signature)
    items: list[tuple[str, int]] = []
    for char in signature:
        if items and items[-1][0] == char:
            items[-1] = (char, items[-1][1] + 1)
        else:
            items.append((char, 1))

    out: list[str] = []
    built: list[str] = []

    def walk(index: int) -> None:
        if index == len(items):
            out.append("".join(built))
            return
        char, count = items[index]
        max_take = min(count, max_len - len(built))
        for take in range(max_take + 1):
            if take:
                built.extend(char for _ in range(take))
            walk(index + 1)
            if take:
                del built[-take:]

    walk(0)
    return tuple(out)


@lru_cache(maxsize=8)
def blank_fill_combos(count: int) -> tuple[tuple[str, int], ...]:
    """All sorted blank substitutions of exactly `count` letters."""

    if count <= 0:
        return (("", 0),)
    combos: list[tuple[str, int]] = []

    def walk(start: int, remaining: int, built: list[str]) -> None:
        if remaining == 0:
            fill = "".join(built)
            combos.append((fill, sum(SCRABBLE_VALUES[char] for char in fill)))
            return
        for index in range(start, len(ALPHABET)):
            built.append(ALPHABET[index])
            walk(index, remaining - 1, built)
            built.pop()

    walk(0, count, [])
    return tuple(combos)


class ValuationModel:
    """Signature-indexed word and leave valuation model."""

    def __init__(
        self,
        best_exact_score_by_signature: dict[str, int],
        max_word_length: int = 7,
    ) -> None:
        self.best_exact_score_by_signature = best_exact_score_by_signature
        self.max_word_length = max_word_length
        self._word_entries = tuple(
            sorted(
                (
                    (signature, score, letter_count_tuple(signature))
                    for signature, score in best_exact_score_by_signature.items()
                ),
                key=lambda item: item[1],
                reverse=True,
            )
        )

    @classmethod
    def from_words(
        cls,
        words: Iterable[str],
        max_word_length: int = 7,
    ) -> "ValuationModel":
        best: dict[str, int] = {}
        for raw_word in words:
            word = clean_letters(raw_word)
            if not word or BLANK in word or len(word) > max_word_length:
                continue
            signature = canonical_signature(word)
            score = word_score(word)
            if score > best.get(signature, 0):
                best[signature] = score
        return cls(best, max_word_length=max_word_length)

    @classmethod
    def from_json(cls, path: str | Path) -> "ValuationModel":
        with Path(path).open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        table = {
            canonical_signature(signature): int(score)
            for signature, score in payload["best_exact_score_by_signature"].items()
        }
        return cls(table, max_word_length=int(payload.get("max_word_length", 7)))

    @lru_cache(maxsize=250_000)
    def best_word_score(self, signature: str) -> int:
        signature = canonical_signature(signature)
        if not signature:
            return 0

        blank_count = signature.count(BLANK)
        if len(signature) > self.max_word_length:
            return self._best_word_score_by_scan(signature, blank_count)

        if blank_count == 0:
            return max(
                self.best_exact_score_by_signature.get(subset, 0)
                for subset in subset_signatures(signature, self.max_word_length)
            )

        nonblank = signature.replace(BLANK, "")
        best = 0
        for subset in subset_signatures(nonblank, self.max_word_length):
            best = max(best, self.best_exact_score_by_signature.get(subset, 0))
            remaining = self.max_word_length - len(subset)
            for blanks_used in range(1, min(blank_count, remaining) + 1):
                for fill, penalty in blank_fill_combos(blanks_used):
                    word_sig = canonical_signature(f"{subset}{fill}")
                    exact_score = self.best_exact_score_by_signature.get(word_sig, 0)
                    if exact_score:
                        best = max(best, exact_score - penalty)
        return best

    def _best_word_score_by_scan(self, signature: str, blank_count: int) -> int:
        rack_counts = letter_count_tuple(signature)
        best = 0
        for _word_sig, score, word_counts in self._word_entries:
            if score <= best:
                break
            blanks_needed = 0
            blank_penalty = 0
            for index, needed in enumerate(word_counts):
                if needed <= rack_counts[index]:
                    continue
                deficit = needed - rack_counts[index]
                blanks_needed += deficit
                if blanks_needed > blank_count:
                    break
                blank_penalty += deficit * SCRABBLE_VALUES[ALPHABET[index]]
            else:
                best = max(best, score - blank_penalty)
        return best

    @lru_cache(maxsize=250_000)
    def leave_value(self, signature: str) -> float:
        signature = canonical_signature(signature)
        if not signature:
            return 0.0

        value = sum(LETTER_BASE.get(char, 0.0) for char in signature)
        nonblank = signature.replace(BLANK, "")
        tile_count = len(nonblank)
        vowel_count = sum(1 for char in nonblank if char in VOWELS)
        consonant_count = tile_count - vowel_count

        if tile_count:
            ratio = vowel_count / tile_count
            value += max(0.0, 4.0 - abs(ratio - 0.42) * 16.0)
        if tile_count >= 3 and vowel_count == 0:
            value -= 6.0
        if tile_count >= 3 and consonant_count == 0:
            value -= 5.0

        for char in set(nonblank):
            duplicates = nonblank.count(char) - 1
            if duplicates <= 0:
                continue
            penalty = duplicates * 1.25
            if char not in "AEINORSTL":
                penalty *= 1.6
            value -= penalty

        if "Q" in nonblank and "U" not in nonblank and BLANK not in signature:
            value -= 8.0
        if "Q" in nonblank and ("U" in nonblank or BLANK in signature):
            value += 4.0
        if any(char in nonblank for char in "XZJ"):
            value += 2.0 if vowel_count else -3.0
        if BLANK in signature:
            value += 8.0 * signature.count(BLANK)
        return value

    @lru_cache(maxsize=250_000)
    def marginal_word_score(self, rack_signature: str, letter: str) -> int:
        rack_signature = canonical_signature(rack_signature)
        with_letter = add_letter_to_signature(rack_signature, letter)
        return self.best_word_score(with_letter) - self.best_word_score(rack_signature)


def load_default_model() -> ValuationModel:
    env_path = os.environ.get("SCRABBLE_BOT_PRECOMPUTED")
    candidates = []
    if env_path:
        candidates.append(Path(env_path))
    candidates.append(Path(__file__).with_name("data") / "precomputed.json")

    for path in candidates:
        if path.exists():
            return ValuationModel.from_json(path)
    return ValuationModel.from_words(MINI_DICTIONARY, max_word_length=DEFAULT_CONFIG.max_word_length)


DEFAULT_MODEL = load_default_model()


def stage_progress(state: GameState) -> float:
    total = max(1, int(state.total_auctions))
    if total <= 1:
        return 1.0
    return min(1.0, max(0.0, int(state.auction_index) / (total - 1)))


def stage_policy(
    progress: float,
    config: BotConfig,
    win_now: bool,
) -> tuple[float, float]:
    if win_now:
        return config.winning_aggression, config.winning_cap_fraction
    if progress < 0.34:
        return config.early_aggression, config.early_cap_fraction
    if progress < 0.70:
        return config.mid_aggression, config.mid_cap_fraction
    return config.late_aggression, config.late_cap_fraction


def balance_score(signature: str) -> float:
    nonblank = canonical_signature(signature).replace(BLANK, "")
    if not nonblank:
        return 0.0
    vowels = sum(1 for char in nonblank if char in VOWELS)
    ratio = vowels / len(nonblank)
    return 4.0 - abs(ratio - 0.42) * 12.0


def duplicate_penalty(rack_signature: str, letter: str, word_delta: int) -> float:
    count = rack_signature.count(letter)
    if count <= 0 or letter == BLANK:
        return 0.0
    penalty = (count ** 1.35) * 1.55
    if letter in "AEINORSTL":
        penalty *= 0.55
    if word_delta >= 5:
        penalty *= 0.25
    return penalty


def power_tile_adjustment(rack_signature: str, letter: str) -> float:
    if letter == BLANK:
        return 10.0
    if letter == "S":
        return 5.5
    if letter == "U" and "Q" in rack_signature:
        return 8.0
    if letter == "Q":
        return 2.5 if ("U" in rack_signature or BLANK in rack_signature) else -8.0
    if letter in {"X", "Z"}:
        has_vowel = any(char in VOWELS for char in rack_signature)
        return 3.0 if has_vowel else -2.5
    if letter == "J":
        has_vowel = any(char in VOWELS for char in rack_signature)
        return 1.5 if has_vowel else -2.0
    return 0.0


def opponent_denial_bonus(
    state: GameState,
    letter: str,
    model: ValuationModel,
    config: BotConfig,
) -> float:
    if not state.opponent_racks:
        return 0.0
    best_delta = 0
    for rack in state.opponent_racks:
        opp_sig = canonical_signature(rack)
        best_delta = max(best_delta, model.marginal_word_score(opp_sig, letter))
    return min(config.max_denial_bonus, best_delta * config.opponent_denial_weight)


def score_components(
    state: GameState,
    config: BotConfig = DEFAULT_CONFIG,
    model: ValuationModel = DEFAULT_MODEL,
) -> dict[str, float | int | bool | str]:
    letter = normalize_letter(state.offered_letter)
    budget = max(0, int(state.budget_remaining))
    if not letter or budget <= 0:
        return {"private_value": 0.0, "letter": letter, "budget": budget, "win_now": False}

    rack_sig = canonical_signature(state.rack)
    with_sig = add_letter_to_signature(rack_sig, letter)
    current_best = model.best_word_score(rack_sig)
    with_best = model.best_word_score(with_sig)
    word_delta = with_best - current_best
    leave_delta = model.leave_value(with_sig) - model.leave_value(rack_sig)
    bal_delta = balance_score(with_sig) - balance_score(rack_sig)

    value = 0.0
    value += SCRABBLE_VALUES[letter] * config.face_score_weight
    value += LETTER_BASE[letter] * config.base_letter_weight
    value += SCARCITY_BONUS[letter] * config.scarcity_weight
    value += word_delta * config.word_delta_weight
    value += leave_delta * config.leave_delta_weight
    value += bal_delta * config.balance_delta_weight
    value += power_tile_adjustment(rack_sig, letter)
    value += opponent_denial_bonus(state, letter, model, config)
    value -= duplicate_penalty(rack_sig, letter, word_delta) * config.duplicate_penalty_weight

    # Extra protection against buying the Q trap early.
    if letter == "Q" and "U" not in rack_sig and BLANK not in rack_sig:
        value -= config.q_without_u_penalty

    win_now = word_delta >= config.winning_delta_threshold
    if state.score_to_beat is not None:
        target = int(state.score_to_beat) + config.winning_score_margin
        if current_best < target <= with_best:
            win_now = True

    return {
        "private_value": max(0.0, value),
        "letter": letter,
        "rack_signature": rack_sig,
        "with_signature": with_sig,
        "current_best": current_best,
        "with_best": with_best,
        "word_delta": word_delta,
        "leave_delta": leave_delta,
        "balance_delta": bal_delta,
        "budget": budget,
        "win_now": win_now,
    }


def decide_bid(
    state: GameState,
    config: BotConfig = DEFAULT_CONFIG,
    model: ValuationModel = DEFAULT_MODEL,
) -> int:
    """Return a deterministic bid within the current budget."""

    components = score_components(state, config=config, model=model)
    budget = int(components.get("budget", 0))
    private_value = float(components.get("private_value", 0.0))
    if budget <= 0 or private_value < config.minimum_private_value:
        return 0

    progress = stage_progress(state)
    win_now = bool(components.get("win_now", False))
    aggression, cap_fraction = stage_policy(progress, config, win_now)

    starting_budget = max(1, int(state.starting_budget), budget)
    target_budget_left = starting_budget * (1.0 - progress)
    overspend_vs_plan = max(0.0, target_budget_left - budget)
    pacing_lambda = config.pacing_beta * overspend_vs_plan / starting_budget

    shaded = private_value * aggression / (1.0 + pacing_lambda)
    cap = max(config.tiny_bid, int(budget * cap_fraction))
    bid = int(round(shaded))
    bid = min(budget, cap, bid)

    if bid <= 0 and private_value >= config.minimum_private_value * 2.0:
        return min(budget, config.tiny_bid)
    return max(0, bid)


if __name__ == "__main__":
    example = GameState(rack="TRAIN", offered_letter="S", budget_remaining=100, auction_index=18)
    print(decide_bid(example))
    print(score_components(example))
