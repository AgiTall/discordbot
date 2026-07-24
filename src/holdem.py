"""Pure Texas Hold'em rules used by the Discord poker table.

The module deliberately has no Discord or Pillow imports so the betting,
showdown, and side-pot rules can be tested independently from the UI.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
import random
from typing import Iterable, Sequence


Card = tuple[str, str]
Money = Decimal
MONEY_CENT = Decimal("0.01")
ZERO = Decimal("0.00")


def as_money(value: int | float | str | Decimal) -> Money:
    """Normalize a dollar amount without introducing binary float noise."""
    return Decimal(str(value)).quantize(MONEY_CENT, rounding=ROUND_HALF_UP)


def format_money(value: int | float | str | Decimal) -> str:
    amount = as_money(value)
    return f"${amount:.2f}" if amount != amount.to_integral() else f"${amount:.0f}"

SUITS = ("♠", "♥", "♦", "♣")
RANKS = ("2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A")
RANK_VALUE = {rank: value for value, rank in enumerate(RANKS, start=2)}
HAND_NAMES = {
    8: "Стрит-флеш",
    7: "Каре",
    6: "Фулл-хаус",
    5: "Флеш",
    4: "Стрит",
    3: "Сет",
    2: "Две пары",
    1: "Пара",
    0: "Старшая карта",
}

WAITING = "waiting"
PREFLOP = "preflop"
FLOP = "flop"
TURN = "turn"
RIVER = "river"
FINISHED = "finished"
BETTING_STAGES = (PREFLOP, FLOP, TURN, RIVER)


class HoldemError(ValueError):
    """A user-facing invalid game action."""


@dataclass
class HoldemPlayer:
    user_id: int
    name: str
    stack: Money
    seat: int
    hole: list[Card] = field(default_factory=list)
    folded: bool = False
    all_in: bool = False
    acted: bool = False
    round_bet: Money = ZERO
    total_bet: Money = ZERO
    payout: Money = ZERO
    last_action: str = ""

    def __post_init__(self) -> None:
        self.stack = as_money(self.stack)
        self.round_bet = as_money(self.round_bet)
        self.total_bet = as_money(self.total_bet)
        self.payout = as_money(self.payout)

    @property
    def in_hand(self) -> bool:
        return bool(self.hole) and not self.folded


def build_deck() -> list[Card]:
    return [(rank, suit) for suit in SUITS for rank in RANKS]


def evaluate_five(cards: Sequence[Card]) -> tuple[int, tuple[int, ...]]:
    """Return a fully comparable score for exactly five cards."""
    if len(cards) != 5:
        raise ValueError("evaluate_five requires exactly five cards")

    values = sorted((RANK_VALUE[rank] for rank, _ in cards), reverse=True)
    suits = [suit for _, suit in cards]
    counts = {value: values.count(value) for value in set(values)}
    groups = sorted(
        ((count, value) for value, count in counts.items()),
        reverse=True,
    )
    unique = sorted(set(values), reverse=True)
    wheel = set(values) == {14, 5, 4, 3, 2}
    straight = len(unique) == 5 and (wheel or unique[0] - unique[-1] == 4)
    straight_high = 5 if wheel else unique[0]
    flush = len(set(suits)) == 1

    if straight and flush:
        return 8, (straight_high,)
    if groups[0][0] == 4:
        four = groups[0][1]
        kicker = max(value for value in values if value != four)
        return 7, (four, kicker)
    if groups[0][0] == 3 and groups[1][0] == 2:
        return 6, (groups[0][1], groups[1][1])
    if flush:
        return 5, tuple(values)
    if straight:
        return 4, (straight_high,)
    if groups[0][0] == 3:
        trips = groups[0][1]
        kickers = tuple(value for value in values if value != trips)
        return 3, (trips, *kickers)

    pairs = sorted((value for count, value in groups if count == 2), reverse=True)
    if len(pairs) == 2:
        kicker = max(value for value in values if value not in pairs)
        return 2, (pairs[0], pairs[1], kicker)
    if len(pairs) == 1:
        pair = pairs[0]
        kickers = tuple(value for value in values if value != pair)
        return 1, (pair, *kickers)
    return 0, tuple(values)


def best_hand(cards: Sequence[Card]) -> tuple[tuple[int, tuple[int, ...]], str, tuple[Card, ...]]:
    """Choose the best five-card hand from five to seven cards."""
    from itertools import combinations

    if not 5 <= len(cards) <= 7:
        raise ValueError("best_hand requires five to seven cards")

    scored = ((evaluate_five(combo), combo) for combo in combinations(cards, 5))
    score, chosen = max(scored, key=lambda item: item[0])
    return score, HAND_NAMES[score[0]], tuple(chosen)


def describe_hole_cards(cards: Sequence[Card]) -> str:
    """Describe a pre-flop hand without pretending it is a five-card hand."""
    if len(cards) != 2:
        return "Карты ещё не розданы"
    if cards[0][0] == cards[1][0]:
        return "Карманная пара"
    high = max((RANK_VALUE[rank], rank) for rank, _ in cards)[1]
    return f"Старшая карта {high}"


class HoldemGame:
    """A single table that can play consecutive no-limit Hold'em hands."""

    def __init__(
        self,
        players: Iterable[HoldemPlayer],
        *,
        small_blind: Money | int | float = 10,
        big_blind: Money | int | float = 20,
        max_bet: Money | int | float | None = None,
        dealer_index: int = -1,
        rng: random.Random | None = None,
    ):
        self.players = sorted(list(players), key=lambda player: player.seat)
        if len(self.players) > 6:
            raise HoldemError("За столом может быть не больше 6 игроков.")
        if small_blind <= 0 or big_blind < small_blind:
            raise ValueError("Invalid blind structure")
        if max_bet is not None and max_bet < big_blind:
            raise ValueError("Maximum bet cannot be lower than the big blind")

        self.small_blind = as_money(small_blind)
        self.big_blind = as_money(big_blind)
        self.max_bet = as_money(max_bet) if max_bet is not None else None
        self.dealer_index = dealer_index
        self.small_blind_index: int | None = None
        self.big_blind_index: int | None = None
        self.current_index: int | None = None
        self.current_bet = ZERO
        self.min_raise = self.big_blind
        self.stage = WAITING
        self.board: list[Card] = []
        self.deck: list[Card] = []
        self.burned: list[Card] = []
        self.hand_number = 0
        self.last_result = ""
        self.showdown_results: dict[int, tuple[tuple[int, tuple[int, ...]], str, tuple[Card, ...]]] = {}
        self.pot_awards: list[tuple[Money, tuple[int, ...]]] = []
        self.rng = rng or random.Random()

    @property
    def pot(self) -> Money:
        return sum(player.total_bet for player in self.players)

    @property
    def current_player(self) -> HoldemPlayer | None:
        if self.current_index is None:
            return None
        return self.players[self.current_index]

    def player_by_id(self, user_id: int) -> HoldemPlayer | None:
        return next((player for player in self.players if player.user_id == user_id), None)

    def _next_index(self, start: int, predicate) -> int:
        if not self.players:
            raise HoldemError("За столом нет игроков.")
        for offset in range(1, len(self.players) + 1):
            index = (start + offset) % len(self.players)
            if predicate(self.players[index]):
                return index
        raise HoldemError("Не найден подходящий игрок.")

    def _hand_indices(self) -> list[int]:
        return [index for index, player in enumerate(self.players) if player.hole]

    def _next_hand_index(self, start: int) -> int:
        return self._next_index(start, lambda player: bool(player.hole))

    def _next_action_index(self, start: int) -> int | None:
        for offset in range(1, len(self.players) + 1):
            index = (start + offset) % len(self.players)
            player = self.players[index]
            if (
                player.hole
                and not player.folded
                and not player.all_in
                and (not player.acted or player.round_bet < self.current_bet)
            ):
                return index
        return None

    def start_hand(self, deck: Sequence[Card] | None = None) -> None:
        eligible = [player for player in self.players if player.stack > 0]
        if len(eligible) < 2:
            raise HoldemError("Для начала раздачи нужны минимум 2 игрока с деньгами.")

        for player in self.players:
            player.hole.clear()
            player.folded = False
            player.all_in = False
            player.acted = False
            player.round_bet = ZERO
            player.total_bet = ZERO
            player.payout = ZERO
            player.last_action = ""

        self.board.clear()
        self.burned.clear()
        self.showdown_results.clear()
        self.pot_awards.clear()
        self.last_result = ""
        self.current_bet = ZERO
        self.min_raise = self.big_blind
        self.stage = PREFLOP
        self.hand_number += 1

        self.deck = list(deck) if deck is not None else build_deck()
        if len(self.deck) != 52 or len(set(self.deck)) != 52:
            raise ValueError("A Hold'em deck must contain 52 unique cards")
        if deck is None:
            self.rng.shuffle(self.deck)

        self.dealer_index = self._next_index(
            self.dealer_index,
            lambda player: player.stack > 0,
        )
        deal_order: list[int] = []
        cursor = self.dealer_index
        for _ in range(len(eligible)):
            cursor = self._next_index(cursor, lambda player: player.stack > 0)
            deal_order.append(cursor)

        for _ in range(2):
            for index in deal_order:
                self.players[index].hole.append(self.deck.pop())

        if len(eligible) == 2:
            self.small_blind_index = self.dealer_index
            self.big_blind_index = self._next_hand_index(self.dealer_index)
        else:
            self.small_blind_index = self._next_hand_index(self.dealer_index)
            self.big_blind_index = self._next_hand_index(self.small_blind_index)

        self._post_blind(self.small_blind_index, self.small_blind, "Малый блайнд")
        self._post_blind(self.big_blind_index, self.big_blind, "Большой блайнд")
        self.current_bet = max(player.round_bet for player in self.players)
        self.current_index = self._next_action_index(self.big_blind_index)
        self._runout_if_no_betting_possible()

    def _commit(self, player: HoldemPlayer, amount: Money | int | float) -> Money:
        amount = max(ZERO, min(as_money(amount), player.stack))
        player.stack -= amount
        player.round_bet += amount
        player.total_bet += amount
        if player.stack == 0:
            player.all_in = True
        return amount

    def _post_blind(self, index: int, amount: Money, label: str) -> None:
        player = self.players[index]
        paid = self._commit(player, amount)
        player.last_action = f"{label} {format_money(paid)}"

    def amount_to_call(self, player: HoldemPlayer | None = None) -> Money:
        player = player or self.current_player
        if player is None:
            return ZERO
        return max(ZERO, self.current_bet - player.round_bet)

    def legal_actions(self, user_id: int) -> set[str]:
        player = self.current_player
        if self.stage not in BETTING_STAGES or player is None or player.user_id != user_id:
            return set()
        actions = {"fold"}
        if self.amount_to_call(player) == 0:
            actions.add("check")
        else:
            actions.add("call")
        maximum = player.round_bet + player.stack
        if self.max_bet is None or maximum <= self.max_bet:
            actions.add("all_in")
        if (
            maximum > self.current_bet
            and (self.max_bet is None or self.current_bet < self.max_bet)
        ):
            actions.add("raise")
        return actions

    def act(
        self,
        user_id: int,
        action: str,
        amount: Money | int | float | None = None,
    ) -> None:
        if self.stage not in BETTING_STAGES or self.current_player is None:
            raise HoldemError("Сейчас нельзя сделать ход.")
        player = self.current_player
        if player.user_id != user_id:
            raise HoldemError("Сейчас ход другого игрока.")

        if action == "fold":
            player.folded = True
            player.acted = True
            player.last_action = "Фолд"
        elif action == "check":
            if self.amount_to_call(player):
                raise HoldemError("Нельзя сделать чек: ставку нужно уравнять.")
            player.acted = True
            player.last_action = "Чек"
        elif action == "call":
            to_call = self.amount_to_call(player)
            if to_call <= 0:
                raise HoldemError("Уравнивать нечего — доступен чек.")
            paid = self._commit(player, to_call)
            player.acted = True
            player.last_action = (
                f"Колл {format_money(paid)}"
                if paid == to_call
                else f"Олл-ин {format_money(paid)}"
            )
        elif action == "raise":
            if amount is None:
                raise HoldemError("Укажите итоговую ставку.")
            self._raise_to(player, as_money(amount))
        elif action == "all_in":
            target = player.round_bet + player.stack
            if self.max_bet is not None and target > self.max_bet:
                raise HoldemError(
                    f"Максимальная ставка за круг: {format_money(self.max_bet)}. "
                    "Используйте рейз."
                )
            if target <= self.current_bet:
                paid = self._commit(player, self.amount_to_call(player))
                player.acted = True
                player.last_action = f"Олл-ин {format_money(paid)}"
            else:
                self._raise_to(player, target)
        else:
            raise HoldemError("Неизвестное действие.")

        if self._finish_if_only_one_left():
            return
        if self._betting_complete():
            self._advance_street()
            return

        next_index = self._next_action_index(self.current_index)
        if next_index is None:
            self._advance_street()
        else:
            self.current_index = next_index

    def _raise_to(self, player: HoldemPlayer, target: Money) -> None:
        maximum = player.round_bet + player.stack
        if self.max_bet is not None and target > self.max_bet:
            raise HoldemError(
                f"Максимальная ставка за круг: {format_money(self.max_bet)}."
            )
        if target <= self.current_bet:
            raise HoldemError("Рейз должен быть выше текущей ставки.")
        if target > maximum:
            raise HoldemError(
                f"Недостаточно денег. Максимальная ставка: {format_money(maximum)}."
            )

        raise_size = target - self.current_bet
        is_all_in = target == maximum
        reaches_cap = self.max_bet is not None and target == self.max_bet
        if raise_size < self.min_raise and not is_all_in and not reaches_cap:
            minimum = self.current_bet + self.min_raise
            raise HoldemError(
                f"Минимальная итоговая ставка: {format_money(minimum)}."
            )

        if raise_size >= self.min_raise:
            self.min_raise = raise_size
            for other in self.players:
                if other is not player and other.in_hand and not other.all_in:
                    other.acted = False

        paid = self._commit(player, target - player.round_bet)
        self.current_bet = target
        player.acted = True
        player.last_action = (
            f"Олл-ин до {format_money(target)}"
            if player.all_in
            else f"Рейз до {format_money(target)}"
        )
        if paid <= 0:
            raise HoldemError("Недостаточно фишек для рейза.")

    def _contenders(self) -> list[HoldemPlayer]:
        return [player for player in self.players if player.in_hand]

    def _betting_complete(self) -> bool:
        actionable = [
            player
            for player in self._contenders()
            if not player.all_in
        ]
        return all(
            player.acted and player.round_bet == self.current_bet
            for player in actionable
        )

    def _finish_if_only_one_left(self) -> bool:
        contenders = self._contenders()
        if len(contenders) != 1:
            return False
        winner = contenders[0]
        amount = self.pot
        winner.stack += amount
        winner.payout += amount
        self.pot_awards = [(amount, (winner.user_id,))]
        self.last_result = (
            f"{winner.name} получает {format_money(amount)} из банка — "
            "остальные сбросили карты."
        )
        self.stage = FINISHED
        self.current_index = None
        return True

    def _burn(self) -> None:
        self.burned.append(self.deck.pop())

    def _advance_street(self) -> None:
        for player in self.players:
            player.round_bet = ZERO
            player.acted = False
        self.current_bet = ZERO
        self.min_raise = self.big_blind

        if self.stage == PREFLOP:
            self._burn()
            self.board.extend((self.deck.pop(), self.deck.pop(), self.deck.pop()))
            self.stage = FLOP
        elif self.stage == FLOP:
            self._burn()
            self.board.append(self.deck.pop())
            self.stage = TURN
        elif self.stage == TURN:
            self._burn()
            self.board.append(self.deck.pop())
            self.stage = RIVER
        elif self.stage == RIVER:
            self._showdown()
            return

        self.current_index = self._next_action_index(self.dealer_index)
        self._runout_if_no_betting_possible()

    def _runout_if_no_betting_possible(self) -> None:
        while self.stage in BETTING_STAGES:
            actionable = [player for player in self._contenders() if not player.all_in]
            if len(actionable) > 1:
                if self.current_index is None:
                    self.current_index = self._next_action_index(self.dealer_index)
                return
            if len(actionable) == 1 and self.amount_to_call(actionable[0]) > 0:
                self.current_index = self.players.index(actionable[0])
                return
            self._advance_street()

    def _showdown(self) -> None:
        contenders = self._contenders()
        for player in contenders:
            self.showdown_results[player.user_id] = best_hand([*player.hole, *self.board])

        levels = sorted(
            {
                as_money(player.total_bet)
                for player in self.players
                if player.total_bet > 0
            }
        )
        previous = ZERO
        awards: list[tuple[Money, tuple[int, ...]]] = []
        result_parts: list[str] = []

        for level in levels:
            contributors = [player for player in self.players if player.total_bet >= level]
            amount = (level - previous) * len(contributors)
            eligible = [
                player
                for player in contributors
                if not player.folded and player.user_id in self.showdown_results
            ]
            previous = level
            if amount <= 0 or not eligible:
                continue

            winning_score = max(self.showdown_results[player.user_id][0] for player in eligible)
            winners = [
                player
                for player in eligible
                if self.showdown_results[player.user_id][0] == winning_score
            ]
            dealer_seat = self.players[self.dealer_index].seat
            ordered_winners = sorted(
                winners,
                key=lambda player: (player.seat - dealer_seat) % 6 or 6,
            )
            share = (amount / len(ordered_winners)).quantize(
                MONEY_CENT,
                rounding=ROUND_DOWN,
            )
            remainder = int(
                ((amount - share * len(ordered_winners)) / MONEY_CENT)
                .to_integral_value(rounding=ROUND_DOWN)
            )
            for offset, winner in enumerate(ordered_winners):
                payout = share + (MONEY_CENT if offset < remainder else ZERO)
                winner.stack += payout
                winner.payout += payout
            winner_ids = tuple(winner.user_id for winner in ordered_winners)
            awards.append((amount, winner_ids))
            names = ", ".join(winner.name for winner in ordered_winners)
            hand_name = self.showdown_results[ordered_winners[0].user_id][1]
            result_parts.append(f"{names}: {format_money(amount)} ({hand_name})")

        self.pot_awards = awards
        self.last_result = " · ".join(result_parts) if result_parts else "Раздача завершена."
        self.stage = FINISHED
        self.current_index = None

    def combination_for(self, user_id: int) -> str:
        player = self.player_by_id(user_id)
        if player is None or not player.hole:
            return "Карты ещё не розданы"
        cards = [*player.hole, *self.board]
        if len(cards) < 5:
            return describe_hole_cards(player.hole)
        return best_hand(cards)[1]
