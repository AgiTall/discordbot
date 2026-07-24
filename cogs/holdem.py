"""Multiplayer six-seat Texas Hold'em for the Discord casino."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
import re
import time

import discord
from discord.ext import commands

from emoji_config import (
    CASINO_BIG_BLIND_EMOJI,
    CASINO_DEALER_EMOJI,
    CASINO_SMALL_BLIND_EMOJI,
)
from src.holdem import (
    BETTING_STAGES,
    FINISHED,
    WAITING,
    HoldemError,
    HoldemGame,
    HoldemPlayer,
)


LOGGER = logging.getLogger(__name__)

MAX_PLAYERS = 6
DEFAULT_MAX_BET = 200
DEFAULT_BUY_IN = 1000
DEFAULT_SMALL_BLIND = 10
DEFAULT_BIG_BLIND = 20
TURN_TIMEOUT_SECONDS = 60
TABLE_JOIN_TIMEOUT_SECONDS = 150
TABLE_AUTO_START_SECONDS = 300
MAX_CONFIGURED_BET = 1_000_000


def blind_structure(max_bet: int) -> tuple[int, int]:
    """Scale blinds with the configured table limit."""
    big_blind = max(1, max_bet // 10)
    small_blind = max(1, big_blind // 2)
    return small_blind, big_blind


def poker_channel_name(display_name: str, user_id: int) -> str:
    clean = re.sub(r"[^\w-]+", "-", display_name.casefold(), flags=re.UNICODE)
    clean = clean.strip("-_") or "host"
    return f"poker-{clean}-{str(user_id)[-4:]}"[:90]


def discord_error_details(error: discord.HTTPException) -> str:
    """Return safe Discord API diagnostics suitable for an ephemeral response."""
    details = [f"HTTP {error.status}"]
    if error.code:
        details.append(f"код Discord {error.code}")
    if error.text:
        details.append(error.text[:300])
    return " · ".join(details)


def _render_table(*args, **kwargs):
    from src.poker_renderer import render_table

    return render_table(*args, **kwargs)


def _render_private_hand(*args, **kwargs):
    from src.poker_renderer import render_private_hand

    return render_private_hand(*args, **kwargs)


@dataclass
class TableNotice:
    ok: bool
    text: str


class DiscordPokerTable:
    def __init__(
        self,
        cog: "HoldemCog",
        *,
        guild_id: int,
        channel_id: int,
        host_id: int,
        max_bet: int = DEFAULT_MAX_BET,
    ):
        self.cog = cog
        self.bot = cog.bot
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.host_id = host_id
        self.max_bet = int(max_bet)
        self.buy_in = self.max_bet * 5
        self.small_blind, self.big_blind = blind_structure(self.max_bet)
        self.players: list[HoldemPlayer] = []
        self.avatars: dict[int, bytes] = {}
        self.game: HoldemGame | None = None
        self.dealer_seat = -1
        self.hand_number = 0
        self.message: discord.Message | None = None
        self.lock = asyncio.Lock()
        self.timeout_task: asyncio.Task | None = None
        self.join_timeout_task: asyncio.Task | None = None
        self.auto_start_task: asyncio.Task | None = None
        self.join_deadline: int | None = None
        self.auto_start_deadline: int | None = None
        self.closed = False

    @property
    def key(self) -> tuple[int, int]:
        return self.guild_id, self.channel_id

    @property
    def hand_active(self) -> bool:
        return self.game is not None and self.game.stage in BETTING_STAGES

    def player_by_id(self, user_id: int) -> HoldemPlayer | None:
        return next((player for player in self.players if player.user_id == user_id), None)

    def _return_to_waiting(self) -> None:
        self.game = None
        for player in self.players:
            player.hole.clear()
            player.folded = False
            player.all_in = False
            player.acted = False
            player.round_bet = 0
            player.total_bet = 0
            player.payout = 0
            player.last_action = ""

    def render_game(self) -> HoldemGame:
        if self.game is not None:
            return self.game
        dealer_index = next(
            (
                index
                for index, player in enumerate(self.players)
                if player.seat == self.dealer_seat
            ),
            -1,
        )
        return HoldemGame(
            self.players,
            small_blind=self.small_blind,
            big_blind=self.big_blind,
            max_bet=self.max_bet,
            dealer_index=dealer_index,
        )

    def _dealer_start_index(self) -> int:
        """Map the previous dealer seat onto the current, possibly changed lineup."""
        if not self.players or self.dealer_seat < 0:
            return -1
        for index, player in enumerate(self.players):
            if player.seat == self.dealer_seat:
                return index
        predecessors = [
            index
            for index, player in enumerate(self.players)
            if player.seat < self.dealer_seat
        ]
        return predecessors[-1] if predecessors else len(self.players) - 1

    async def _change_cash(self, user_id: int, amount: int) -> bool:
        token = self.bot.set_economy_guild_id(self.guild_id)
        try:
            async with self.bot.economy_lock:
                account = self.bot.get_account(user_id)
                if amount < 0 and account["cash"] + 0.0001 < -amount:
                    return False
                account["cash"] = round(account["cash"] + amount, 2)
                self.bot.save_economy()
                return True
        finally:
            self.bot.reset_economy_guild_id(token)

    def channel(self) -> discord.TextChannel | None:
        getter = getattr(self.bot, "get_channel", None)
        channel = getter(self.channel_id) if getter else None
        return channel if isinstance(channel, discord.TextChannel) else None

    async def grant_channel_access(
        self,
        member: discord.Member | discord.User,
    ) -> bool:
        channel = self.channel()
        if channel is None:
            return False
        try:
            await channel.set_permissions(
                member,
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                reason="Игрок присоединился к покерному столу",
            )
            return True
        except (discord.Forbidden, discord.HTTPException):
            LOGGER.exception("Failed to grant access to Hold'em channel")
            return False

    async def revoke_channel_access(self, user_id: int) -> None:
        channel = self.channel()
        if channel is None:
            return
        member = channel.guild.get_member(user_id)
        if member is None:
            return
        try:
            await channel.set_permissions(
                member,
                overwrite=None,
                reason="Игрок вышел из-за покерного стола",
            )
        except (discord.Forbidden, discord.HTTPException):
            LOGGER.exception("Failed to revoke access to Hold'em channel")

    async def delete_channel(self, reason: str) -> None:
        channel = self.channel()
        if channel is None:
            return
        try:
            await channel.delete(reason=reason)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            LOGGER.exception("Failed to delete temporary Hold'em channel")

    @staticmethod
    def _cancel_task(task: asyncio.Task | None) -> None:
        if task and task is not asyncio.current_task():
            task.cancel()

    def cancel_lobby_tasks(self) -> None:
        self._cancel_task(self.join_timeout_task)
        self._cancel_task(self.auto_start_task)
        self.join_timeout_task = None
        self.auto_start_task = None
        self.join_deadline = None
        self.auto_start_deadline = None

    def schedule_join_timeout(self) -> None:
        if self.closed or self.hand_number > 0 or self.hand_active:
            return
        self._cancel_task(self.auto_start_task)
        self._cancel_task(self.join_timeout_task)
        self.auto_start_task = None
        self.auto_start_deadline = None
        self.join_deadline = int(time.time()) + TABLE_JOIN_TIMEOUT_SECONDS
        self.join_timeout_task = asyncio.create_task(self._expire_unjoined_table())

    def schedule_auto_start(self) -> None:
        if (
            self.closed
            or self.hand_number > 0
            or self.hand_active
            or len(self.players) < 2
        ):
            return
        self._cancel_task(self.join_timeout_task)
        self.join_timeout_task = None
        self.join_deadline = None
        if self.auto_start_task and not self.auto_start_task.done():
            return
        self.auto_start_deadline = int(time.time()) + TABLE_AUTO_START_SECONDS
        self.auto_start_task = asyncio.create_task(self._auto_start_first_hand())

    async def _expire_unjoined_table(self) -> None:
        try:
            await asyncio.sleep(TABLE_JOIN_TIMEOUT_SECONDS)
            async with self.lock:
                if self.closed or self.hand_active or len(self.players) >= 2:
                    return
                notice = await self.close(self.host_id)
                if notice.ok:
                    await self.delete_channel(
                        "За 2,5 минуты к покерному столу никто не присоединился"
                    )
        except asyncio.CancelledError:
            return
        except Exception:
            LOGGER.exception("Failed to expire an unjoined Hold'em table")

    async def _auto_start_first_hand(self) -> None:
        try:
            await asyncio.sleep(TABLE_AUTO_START_SECONDS)
            async with self.lock:
                if self.closed or self.hand_active or self.hand_number > 0:
                    return
                if len([player for player in self.players if player.stack > 0]) < 2:
                    self.schedule_join_timeout()
                    await self.update_message()
                    return
                notice = self.start_hand(self.host_id)
                if notice.ok:
                    await self.update_message()
        except asyncio.CancelledError:
            return
        except Exception:
            LOGGER.exception("Failed to auto-start a Hold'em table")

    async def seat_member(self, member: discord.Member | discord.User) -> TableNotice:
        if self.closed:
            return TableNotice(False, "Этот стол уже закрыт.")
        if self.hand_active:
            return TableNotice(False, "Присоединиться можно после завершения текущей раздачи.")
        if self.player_by_id(member.id):
            return TableNotice(False, "Вы уже сидите за этим столом.")
        for other in self.cog.tables.values():
            if other is not self and not other.closed and other.player_by_id(member.id):
                return TableNotice(False, "Вы уже участвуете в другом покерном столе.")
        if len(self.players) >= MAX_PLAYERS:
            return TableNotice(False, "Все 6 мест уже заняты.")
        if not await self._change_cash(member.id, -self.buy_in):
            return TableNotice(
                False,
                f"Для посадки нужно {self.buy_in} наличными.",
            )

        if self.game is not None and self.game.stage == FINISHED:
            self._return_to_waiting()
        if not self.players:
            self.host_id = member.id
        occupied = {player.seat for player in self.players}
        seat = next(index for index in range(MAX_PLAYERS) if index not in occupied)
        player = HoldemPlayer(
            user_id=member.id,
            name=member.display_name,
            stack=self.buy_in,
            seat=seat,
        )
        self.players.append(player)
        self.players.sort(key=lambda item: item.seat)
        try:
            self.avatars[member.id] = await member.display_avatar.read()
        except (discord.HTTPException, OSError):
            self.avatars.pop(member.id, None)
        if len(self.players) >= 2 and self.hand_number == 0:
            self.schedule_auto_start()
        return TableNotice(True, f"Вы сели за стол с {self.buy_in} фишками.")

    async def leave(self, user_id: int) -> TableNotice:
        if self.hand_active:
            return TableNotice(False, "Во время раздачи выйти нельзя. Сначала сделайте фолд.")
        player = self.player_by_id(user_id)
        if player is None:
            return TableNotice(False, "Вы не сидите за этим столом.")

        amount = player.stack
        if amount and not await self._change_cash(user_id, amount):
            return TableNotice(False, "Не удалось вернуть фишки на баланс.")
        self.players.remove(player)
        self.avatars.pop(user_id, None)
        await self.revoke_channel_access(user_id)
        self._return_to_waiting()
        if self.host_id == user_id and self.players:
            self.host_id = self.players[0].user_id
        if self.hand_number == 0 and len(self.players) < 2:
            self.schedule_join_timeout()
        return TableNotice(True, f"Вы вышли из-за стола. Возвращено: {amount}.")

    async def rebuy(self, user_id: int) -> TableNotice:
        if self.hand_active:
            return TableNotice(False, "Пополнить стек можно только между раздачами.")
        player = self.player_by_id(user_id)
        if player is None:
            return TableNotice(False, "Сначала сядьте за стол.")
        if player.stack > 0:
            return TableNotice(False, "Повторный взнос доступен после потери всех фишек.")
        if not await self._change_cash(user_id, -self.buy_in):
            return TableNotice(False, f"Для повторного взноса нужно {self.buy_in} наличными.")
        player.stack += self.buy_in
        return TableNotice(True, f"Внесено ещё {self.buy_in} фишек.")

    def start_hand(self, user_id: int) -> TableNotice:
        if self.closed:
            return TableNotice(False, "Этот стол закрыт.")
        if user_id != self.host_id:
            return TableNotice(False, "Начать раздачу может только хозяин стола.")
        if self.hand_active:
            return TableNotice(False, "Раздача уже идёт.")
        if sum(player.stack > 0 for player in self.players) < 2:
            return TableNotice(False, "Нужны минимум 2 игрока с фишками.")

        try:
            self.game = HoldemGame(
                self.players,
                small_blind=self.small_blind,
                big_blind=self.big_blind,
                max_bet=self.max_bet,
                dealer_index=self._dealer_start_index(),
            )
            self.game.start_hand()
            self.cancel_lobby_tasks()
            self.hand_number += 1
            self.game.hand_number = self.hand_number
            self.dealer_seat = self.game.players[self.game.dealer_index].seat
        except HoldemError as error:
            return TableNotice(False, str(error))
        return TableNotice(True, f"Раздача #{self.game.hand_number} началась.")

    def perform_action(self, user_id: int, action: str, amount: int | None = None) -> TableNotice:
        if self.game is None:
            return TableNotice(False, "Раздача ещё не началась.")
        try:
            self.game.act(user_id, action, amount)
        except HoldemError as error:
            return TableNotice(False, str(error))
        return TableNotice(True, "Ход принят.")

    def build_embed(self) -> discord.Embed:
        game = self.render_game()
        if self.closed:
            description = "Стол закрыт. Все оставшиеся фишки возвращены игрокам."
        elif game.stage == WAITING:
            lines = [
                f"Максимальная ставка за круг: **{self.max_bet}** · "
                f"Бай-ин: **{self.buy_in}**",
                f"{CASINO_SMALL_BLIND_EMOJI} **{self.small_blind}** · "
                f"{CASINO_BIG_BLIND_EMOJI} **{self.big_blind}**",
                f"Игроков: **{len(self.players)}/{MAX_PLAYERS}** · "
                f"Хозяин: <@{self.host_id}>",
            ]
            if len(self.players) < 2 and self.join_deadline:
                lines.append(
                    f"\nЕсли никто не присоединится, стол удалится "
                    f"<t:{self.join_deadline}:R>."
                )
            elif len(self.players) >= 2 and self.auto_start_deadline:
                lines.append(
                    f"\nХозяин может начать сейчас. Автозапуск "
                    f"<t:{self.auto_start_deadline}:R>."
                )
            else:
                lines.append(
                    "\nСядьте за стол. Хозяин запускает раздачу, "
                    "когда готовы минимум два игрока."
                )
            description = "\n".join(lines)
        elif game.stage == FINISHED:
            lines = [f"**{game.last_result}**"]
            for player in game.players:
                result = game.showdown_results.get(player.user_id)
                if result:
                    lines.append(f"<@{player.user_id}> — **{result[1]}**, стек: **{player.stack}**")
                if player.stack == 0:
                    lines.append(
                        f"<@{player.user_id}> потерял все фишки: можно выйти "
                        f"или повторно внести **{self.buy_in}**."
                    )
            lines.append("\nХозяин может начать следующую раздачу.")
            description = "\n".join(lines)
        else:
            current = game.current_player
            to_call = game.amount_to_call(current)
            dealer = game.players[game.dealer_index]
            small_blind = game.players[game.small_blind_index]
            big_blind = game.players[game.big_blind_index]
            description = (
                f"Раздача **#{game.hand_number}** · Банк: **{game.pot}** · "
                f"лимит: **{self.max_bet}**\n"
                f"{CASINO_DEALER_EMOJI} <@{dealer.user_id}> · "
                f"{CASINO_SMALL_BLIND_EMOJI} <@{small_blind.user_id}> · "
                f"{CASINO_BIG_BLIND_EMOJI} <@{big_blind.user_id}>\n"
                f"Ход: <@{current.user_id}> · "
                f"{'уравнять ' + str(to_call) if to_call else 'можно чек'}\n"
                f"На решение: **{TURN_TIMEOUT_SECONDS} секунд**. "
                "Свои карты и комбинацию смотрите кнопкой «Мои карты»."
            )

        embed = discord.Embed(
            title="♠ Texas Hold’em · 6 мест",
            description=description,
            color=discord.Color.dark_green(),
        )
        embed.set_image(url="attachment://poker_table.jpg")
        embed.set_footer(
            text=(
                f"Бай-ин {self.buy_in} = максимальная ставка {self.max_bet} × 5. "
                "Фишки возвращаются при выходе."
            )
        )
        return embed

    def build_view(self) -> "PokerTableView":
        return PokerTableView(self)

    async def send_initial(self, channel: discord.abc.Messageable) -> None:
        image = await asyncio.to_thread(_render_table, self.render_game(), dict(self.avatars))
        file = discord.File(image, filename="poker_table.jpg")
        self.message = await channel.send(
            embed=self.build_embed(),
            file=file,
            view=self.build_view(),
        )

    async def update_message(self) -> None:
        if self.message is None:
            return
        image = await asyncio.to_thread(_render_table, self.render_game(), dict(self.avatars))
        file = discord.File(image, filename="poker_table.jpg")
        try:
            await self.message.edit(
                embed=self.build_embed(),
                attachments=[file],
                view=None if self.closed else self.build_view(),
            )
        except discord.HTTPException:
            LOGGER.exception("Failed to update Hold'em table message")
        self._schedule_timeout()

    def _schedule_timeout(self) -> None:
        current_task = asyncio.current_task()
        if self.timeout_task and self.timeout_task is not current_task:
            self.timeout_task.cancel()
        self.timeout_task = None

        if not self.hand_active or self.game is None or self.game.current_player is None:
            return
        marker = (
            self.game.hand_number,
            self.game.stage,
            self.game.current_player.user_id,
            self.game.current_player.round_bet,
            self.game.current_bet,
        )
        self.timeout_task = asyncio.create_task(self._turn_timeout(marker))

    async def _turn_timeout(self, marker: tuple) -> None:
        try:
            await asyncio.sleep(TURN_TIMEOUT_SECONDS)
            async with self.lock:
                if not self.hand_active or self.game is None or self.game.current_player is None:
                    return
                current_marker = (
                    self.game.hand_number,
                    self.game.stage,
                    self.game.current_player.user_id,
                    self.game.current_player.round_bet,
                    self.game.current_bet,
                )
                if current_marker != marker:
                    return
                player = self.game.current_player
                action = "check" if self.game.amount_to_call(player) == 0 else "fold"
                self.game.act(player.user_id, action)
                player.last_action = "Авточек" if action == "check" else "Автофолд"
                await self.update_message()
        except asyncio.CancelledError:
            return
        except Exception:
            LOGGER.exception("Hold'em turn timeout failed")

    async def close(self, user_id: int) -> TableNotice:
        if user_id != self.host_id:
            return TableNotice(False, "Закрыть стол может только его хозяин.")
        if self.hand_active:
            return TableNotice(False, "Нельзя закрыть стол во время раздачи.")

        refunds = [(player.user_id, player.stack) for player in self.players if player.stack]
        for player_id, amount in refunds:
            await self._change_cash(player_id, amount)
        self.players.clear()
        self.avatars.clear()
        self.game = None
        self.closed = True
        self.cancel_lobby_tasks()
        if self.timeout_task:
            self.timeout_task.cancel()
        self.cog.tables.pop(self.key, None)
        return TableNotice(True, "Стол закрыт, фишки возвращены игрокам.")


class RaiseModal(discord.ui.Modal, title="Поднять ставку"):
    total = discord.ui.TextInput(
        label="Итоговая ставка в этом круге",
        placeholder="Например: 100",
        min_length=1,
        max_length=12,
    )

    def __init__(self, table: DiscordPokerTable):
        super().__init__()
        self.table = table
        self.total.placeholder = f"Итоговая ставка, не больше {table.max_bet}"

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            amount = int(str(self.total.value).strip())
        except ValueError:
            await interaction.response.send_message("Введите целое число.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        async with self.table.lock:
            notice = self.table.perform_action(interaction.user.id, "raise", amount)
            if notice.ok:
                await self.table.update_message()
        await interaction.edit_original_response(content=notice.text)


class PokerTableView(discord.ui.View):
    def __init__(self, table: DiscordPokerTable):
        super().__init__(timeout=None)
        self.table = table
        game = table.game
        active = table.hand_active

        self.start_button.disabled = active or sum(player.stack > 0 for player in table.players) < 2
        self.rebuy_button.disabled = active
        self.leave_button.disabled = active
        self.close_button.disabled = active
        self.rebuy_button.label = f"Повторный взнос +{table.buy_in}"
        self.raise_button.label = f"Рейз · макс. {table.max_bet}"

        for button in (
            self.call_button,
            self.raise_button,
            self.all_in_button,
            self.fold_button,
        ):
            button.disabled = not active
        self.cards_button.disabled = not active and not (
            game is not None and game.stage == FINISHED
        )

        if active and game and game.current_player:
            to_call = game.amount_to_call()
            self.call_button.label = f"Колл {to_call}" if to_call else "Чек"
            legal = game.legal_actions(game.current_player.user_id)
            self.raise_button.disabled = "raise" not in legal
            self.all_in_button.disabled = "all_in" not in legal
        else:
            self.call_button.label = "Чек / Колл"

    async def _defer(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)

    async def _notice(self, interaction: discord.Interaction, notice: TableNotice) -> None:
        await interaction.edit_original_response(content=notice.text)

    async def _act(self, interaction: discord.Interaction, action: str) -> None:
        await self._defer(interaction)
        async with self.table.lock:
            notice = self.table.perform_action(interaction.user.id, action)
            if notice.ok:
                await self.table.update_message()
        await self._notice(interaction, notice)

    @discord.ui.button(label="Выйти", style=discord.ButtonStyle.secondary, row=0)
    async def leave_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._defer(interaction)
        async with self.table.lock:
            notice = await self.table.leave(interaction.user.id)
            if notice.ok:
                await self.table.update_message()
        await self._notice(interaction, notice)

    @discord.ui.button(label="Повторный взнос", style=discord.ButtonStyle.secondary, row=0)
    async def rebuy_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._defer(interaction)
        async with self.table.lock:
            notice = await self.table.rebuy(interaction.user.id)
            if notice.ok:
                await self.table.update_message()
        await self._notice(interaction, notice)

    @discord.ui.button(label="Начать раздачу", style=discord.ButtonStyle.primary, row=0)
    async def start_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._defer(interaction)
        async with self.table.lock:
            notice = self.table.start_hand(interaction.user.id)
            if notice.ok:
                await self.table.update_message()
        await self._notice(interaction, notice)

    @discord.ui.button(label="Мои карты", emoji="🃏", style=discord.ButtonStyle.secondary, row=1)
    async def cards_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._defer(interaction)
        game = self.table.game
        player = game.player_by_id(interaction.user.id) if game else None
        if player is None or not player.hole:
            await interaction.followup.send("У вас нет карт в этой раздаче.", ephemeral=True)
            return
        image = await asyncio.to_thread(_render_private_hand, game, interaction.user.id)
        await interaction.followup.send(
            content=f"Ваша комбинация: **{game.combination_for(interaction.user.id)}**",
            file=discord.File(image, filename="my_poker_hand.jpg"),
            ephemeral=True,
        )

    @discord.ui.button(label="Чек / Колл", style=discord.ButtonStyle.success, row=1)
    async def call_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        game = self.table.game
        action = "check" if game and game.amount_to_call() == 0 else "call"
        await self._act(interaction, action)

    @discord.ui.button(label="Рейз", style=discord.ButtonStyle.primary, row=1)
    async def raise_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.send_modal(RaiseModal(self.table))

    @discord.ui.button(label="Олл-ин", style=discord.ButtonStyle.danger, row=1)
    async def all_in_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._act(interaction, "all_in")

    @discord.ui.button(label="Фолд", style=discord.ButtonStyle.danger, row=1)
    async def fold_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._act(interaction, "fold")

    @discord.ui.button(label="Закрыть стол", style=discord.ButtonStyle.secondary, row=2)
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._defer(interaction)
        async with self.table.lock:
            notice = await self.table.close(interaction.user.id)
        await self._notice(interaction, notice)
        if notice.ok:
            await self.table.delete_channel("Хозяин закрыл покерный стол")


class CreatePokerTableModal(discord.ui.Modal, title="Создать покерный стол"):
    max_bet = discord.ui.TextInput(
        label="Максимальная ставка за круг",
        placeholder="Например: 5 (бай-ин будет 25)",
        min_length=1,
        max_length=9,
    )

    def __init__(self, cog: "HoldemCog"):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            max_bet = int(str(self.max_bet.value).strip())
        except ValueError:
            await interaction.response.send_message(
                "Максимальная ставка должна быть целым числом.",
                ephemeral=True,
            )
            return
        if not 1 <= max_bet <= MAX_CONFIGURED_BET:
            await interaction.response.send_message(
                f"Укажите ставку от 1 до {MAX_CONFIGURED_BET}.",
                ephemeral=True,
            )
            return
        await self.cog.create_table(interaction, max_bet)


class PokerMenuView(discord.ui.View):
    def __init__(self, cog: "HoldemCog", user_id: int):
        super().__init__(timeout=300)
        self.cog = cog
        self.user_id = user_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.user_id:
            return True
        await interaction.response.send_message(
            "Откройте собственное меню через `/casino`.",
            ephemeral=True,
        )
        return False

    @discord.ui.button(
        label="Создать стол",
        emoji="🃏",
        style=discord.ButtonStyle.success,
    )
    async def create_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        await interaction.response.send_modal(CreatePokerTableModal(self.cog))

    @discord.ui.button(
        label="Присоединиться к существующему",
        emoji="♠️",
        style=discord.ButtonStyle.primary,
    )
    async def join_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        await self.cog.show_joinable_tables(interaction)


class JoinPokerTableSelect(discord.ui.Select):
    def __init__(self, cog: "HoldemCog", tables: list[DiscordPokerTable]):
        self.cog = cog
        options = []
        for table in tables[:25]:
            channel = cog.bot.get_channel(table.channel_id)
            channel_name = getattr(channel, "name", str(table.channel_id))
            options.append(
                discord.SelectOption(
                    label=f"#{channel_name} · ставка {table.max_bet}",
                    description=(
                        f"Бай-ин {table.buy_in} · "
                        f"{len(table.players)}/{MAX_PLAYERS} игроков"
                    ),
                    value=str(table.channel_id),
                )
            )
        super().__init__(
            placeholder="Выберите открытый стол",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        key = (interaction.guild_id, int(self.values[0]))
        table = self.cog.tables.get(key)
        if table is None or table.closed:
            await interaction.response.send_message(
                "Этот стол уже закрыт.",
                ephemeral=True,
            )
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        await interaction.edit_original_response(
            content="⏳ Подключаю вас к столу и открываю временный канал…",
            view=None,
        )
        async with table.lock:
            notice = await table.seat_member(interaction.user)
            if notice.ok:
                granted = await table.grant_channel_access(interaction.user)
                if not granted:
                    await table.leave(interaction.user.id)
                    notice = TableNotice(
                        False,
                        "Не удалось открыть доступ к временному каналу. "
                        "Проверьте право бота «Управлять каналами».",
                    )
                else:
                    await table.update_message()
        text = notice.text
        if notice.ok and table.message:
            text += f"\nПерейти к столу: {table.message.jump_url}"
        await interaction.edit_original_response(content=text, view=None)


class JoinPokerTableView(discord.ui.View):
    def __init__(
        self,
        cog: "HoldemCog",
        user_id: int,
        tables: list[DiscordPokerTable],
    ):
        super().__init__(timeout=180)
        self.user_id = user_id
        self.add_item(JoinPokerTableSelect(cog, tables))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.user_id:
            return True
        await interaction.response.send_message(
            "Откройте собственный список столов через `/casino`.",
            ephemeral=True,
        )
        return False


class HoldemCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.tables: dict[tuple[int, int], DiscordPokerTable] = {}
        self.creation_lock = asyncio.Lock()

    async def open_poker_menu(self, interaction: discord.Interaction) -> None:
        if interaction.guild_id is None or interaction.channel is None:
            await interaction.response.send_message(
                "Покерный стол доступен только на сервере.",
                ephemeral=True,
            )
            return
        embed = discord.Embed(
            title="♠ Texas Hold’em",
            description=(
                "Создайте новый стол с собственной максимальной ставкой "
                "или присоединитесь к уже открытому.\n\n"
                "Бай-ин всегда равен **максимальной ставке × 5**."
            ),
            color=discord.Color.dark_green(),
        )
        await interaction.response.send_message(
            embed=embed,
            view=PokerMenuView(self, interaction.user.id),
            ephemeral=True,
        )

    async def create_table(
        self,
        interaction: discord.Interaction,
        max_bet: int,
    ) -> None:
        if interaction.guild_id is None or interaction.channel is None:
            await interaction.response.send_message(
                "Покерный стол доступен только на сервере.",
                ephemeral=True,
            )
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        await interaction.edit_original_response(
            content="⏳ Проверяю настройки и права для временного канала…"
        )
        guild = interaction.guild
        bot_member = guild.me
        if bot_member is None or not bot_member.guild_permissions.manage_channels:
            await interaction.edit_original_response(
                content=(
                    "Не могу создать стол: боту требуется право "
                    "**«Управлять каналами»**."
                )
            )
            return

        current_table = next(
            (
                table
                for table in self.tables.values()
                if not table.closed
                and table.guild_id == interaction.guild_id
                and table.player_by_id(interaction.user.id)
            ),
            None,
        )
        if current_table and current_table.message:
            await interaction.edit_original_response(
                content=f"Вы уже участвуете в столе: {current_table.message.jump_url}"
            )
            return

        temporary_channel: discord.TextChannel | None = None
        table: DiscordPokerTable | None = None
        notice: TableNotice | None = None
        creation_step = "создание приватного канала"
        async with self.creation_lock:
            await interaction.edit_original_response(
                content="⏳ Создаю закрытый канал для покерного стола…"
            )
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                interaction.user: discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    attach_files=True,
                    embed_links=True,
                ),
                bot_member: discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    manage_channels=True,
                    manage_messages=True,
                    attach_files=True,
                    embed_links=True,
                ),
            }
            category = (
                interaction.channel.category
                if isinstance(interaction.channel, discord.TextChannel)
                else None
            )
            try:
                temporary_channel = await guild.create_text_channel(
                    poker_channel_name(
                        interaction.user.display_name,
                        interaction.user.id,
                    ),
                    overwrites=overwrites,
                    category=category,
                    topic=(
                        f"Временный Texas Hold'em · хост {interaction.user} · "
                        f"макс. ставка {max_bet} · бай-ин {max_bet * 5}"
                    ),
                    reason="Создан временный покерный стол",
                )
                creation_step = "подготовка покерного стола"
                await interaction.edit_original_response(
                    content="⏳ Канал готов. Загружаю фон, карты и создаю стол…"
                )
                table = DiscordPokerTable(
                    self,
                    guild_id=interaction.guild_id,
                    channel_id=temporary_channel.id,
                    host_id=interaction.user.id,
                    max_bet=max_bet,
                )
                notice = await table.seat_member(interaction.user)
                if not notice.ok:
                    await temporary_channel.delete(
                        reason="Хост не смог внести бай-ин"
                    )
                    await interaction.edit_original_response(content=notice.text)
                    return
                self.tables[table.key] = table
                table.schedule_join_timeout()
                creation_step = "рендер и отправка изображения стола"
                await table.send_initial(temporary_channel)
            except (discord.Forbidden, discord.HTTPException) as error:
                LOGGER.exception(
                    "Failed during Hold'em table creation step: %s",
                    creation_step,
                )
                if table:
                    self.tables.pop(table.key, None)
                    table.cancel_lobby_tasks()
                    if table.player_by_id(interaction.user.id):
                        await table._change_cash(interaction.user.id, table.buy_in)
                if temporary_channel:
                    try:
                        await temporary_channel.delete(
                            reason="Ошибка создания покерного стола"
                        )
                    except discord.HTTPException:
                        pass
                await interaction.edit_original_response(
                    content=(
                        f"Не удалось выполнить этап **«{creation_step}»**.\n"
                        f"`{discord_error_details(error)}`\n\n"
                        "Если у роли бота включён «Администратор», причина не в "
                        "настройках OAuth2. Проверьте лимит каналов/каналов в "
                        "категории и пришлите указанный выше код Discord."
                    )
                )
                return
            except Exception as error:
                LOGGER.exception(
                    "Unexpected failure during Hold'em table creation step: %s",
                    creation_step,
                )
                if table:
                    self.tables.pop(table.key, None)
                    table.cancel_lobby_tasks()
                    if table.player_by_id(interaction.user.id):
                        await table._change_cash(interaction.user.id, table.buy_in)
                if temporary_channel:
                    try:
                        await temporary_channel.delete(
                            reason="Ошибка создания покерного стола"
                        )
                    except discord.HTTPException:
                        pass
                await interaction.edit_original_response(
                    content=(
                        f"Ошибка на этапе **«{creation_step}»**: "
                        f"`{type(error).__name__}: {str(error)[:300]}`\n\n"
                        "Деньги не списаны или уже возвращены. Это не ошибка "
                        "прав Discord; подробности также записаны в лог бота."
                    )
                )
                return

        text = (
            f"{notice.text}\n"
            f"Максимальная ставка: **{table.max_bet}**, бай-ин: **{table.buy_in}**.\n"
            f"Приватный стол создан: {table.message.jump_url}\n"
            "Другие игроки входят через «Присоединиться к существующему»."
        )
        await interaction.edit_original_response(content=text)

    async def show_joinable_tables(self, interaction: discord.Interaction) -> None:
        existing_membership = next(
            (
                table
                for table in self.tables.values()
                if not table.closed
                and table.guild_id == interaction.guild_id
                and table.player_by_id(interaction.user.id)
            ),
            None,
        )
        if existing_membership and existing_membership.message:
            await interaction.response.send_message(
                f"Вы уже за столом: {existing_membership.message.jump_url}",
                ephemeral=True,
            )
            return

        tables = [
            table
            for table in self.tables.values()
            if (
                table.guild_id == interaction.guild_id
                and not table.closed
                and not table.hand_active
                and len(table.players) < MAX_PLAYERS
            )
        ]
        if not tables:
            await interaction.response.send_message(
                "Сейчас нет открытых столов. Создайте новый.",
                ephemeral=True,
            )
            return
        await interaction.response.send_message(
            "Выберите стол для присоединения:",
            view=JoinPokerTableView(self, interaction.user.id, tables),
            ephemeral=True,
        )

    async def cog_unload(self) -> None:
        # Best-effort refund during an orderly extension reload/shutdown.
        for table in list(self.tables.values()):
            if table.timeout_task:
                table.timeout_task.cancel()
            try:
                if table.hand_active and table.game:
                    # Cancel the unfinished hand: each player gets back the
                    # chips still in their stack plus their own contributions.
                    for player in table.players:
                        refund = player.stack + player.total_bet
                        if refund:
                            await table._change_cash(player.user_id, refund)
                    table.players.clear()
                    table.closed = True
                    table.cancel_lobby_tasks()
                    self.tables.pop(table.key, None)
                else:
                    await table.close(table.host_id)
                await table.delete_channel(
                    "Покерный стол закрыт при перезагрузке бота"
                )
            except Exception:
                LOGGER.exception("Failed to refund a closing Hold'em table")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(HoldemCog(bot))
