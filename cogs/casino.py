import discord
import random
import asyncio
from discord.ext import commands
from discord import app_commands

CARD_SUITS = ["♠", "♥", "♦", "♣"]
CARD_RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]

def format_card(card):
    return f"{card[0]}{card[1]}"

def format_cards(cards):
    return " ".join(format_card(card) for card in cards)

def build_card_deck():
    return [(rank, suit) for suit in CARD_SUITS for rank in CARD_RANKS]



def blackjack_card_value(card):
    rank, _ = card
    if rank == "A":
        return 11
    if rank in {"K", "Q", "J"}:
        return 10
    return int(rank)



def blackjack_hand_value(cards):
    total = sum(blackjack_card_value(card) for card in cards)
    aces = sum(1 for rank, _ in cards if rank == "A")
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total



class BlackjackView(discord.ui.View):
    def __init__(self, bot, user_id, bet, deck, player_hand, dealer_hand):
        super().__init__(timeout=180)
        self.bot = bot
        self.user_id = user_id
        self.deck = deck
        self.dealer_hand = dealer_hand
        self.hands = [{"cards": player_hand, "bet": bet, "result_text": "", "finished": False}]
        self.active_hand_idx = 0
        self.message = None
        self.initial_bet = bet

        self._update_buttons()

    def _update_buttons(self):
        if self.is_all_finished():
            self.disable_all_buttons()
            return

        active_hand = self.hands[self.active_hand_idx]
        cards = active_hand["cards"]

        for child in self.children:
            if child.custom_id == "hit":
                child.disabled = False
            elif child.custom_id == "stand":
                child.disabled = False
            elif child.custom_id == "double":
                child.disabled = len(cards) != 2
            elif child.custom_id == "split":
                can_split = len(self.hands) == 1 and len(cards) == 2 and cards[0][0] == cards[1][0]
                child.disabled = not can_split

    async def interaction_check(self, interaction):
        self.bot.set_economy_guild_id(interaction.guild_id)
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "Это не ваша партия blackjack.", ephemeral=True
            )
            return False
        return True

    def build_embed(self, reveal_dealer=False):
        dealer_cards = format_cards(self.dealer_hand)
        if not reveal_dealer and len(self.dealer_hand) >= 2:
            dealer_cards = f"{format_card(self.dealer_hand[0])} ??"

        dealer_value = blackjack_hand_value(self.dealer_hand)
        embed = discord.Embed(title="Blackjack", color=discord.Color.dark_green())
        
        dealer_sum = dealer_value if reveal_dealer else blackjack_card_value(self.dealer_hand[0])
        embed.add_field(
            name="Карты дилера",
            value=f"{dealer_cards}\nСумма: **{dealer_sum}**",
            inline=False,
        )

        for i, hand in enumerate(self.hands):
            name = f"Ваши карты (Рука {i+1})" if len(self.hands) > 1 else "Ваши карты"
            if i == self.active_hand_idx and not self.is_all_finished():
                name = "👉 " + name
            
            val_text = f"{format_cards(hand['cards'])}\nСумма: **{blackjack_hand_value(hand['cards'])}**\nСтавка: **{self.bot.format_money(hand['bet'])}**"
            if hand["result_text"]:
                val_text += f"\n*Итог: {hand['result_text']}*"
            
            embed.add_field(name=name, value=val_text, inline=False)
            
        return embed

    def disable_all_buttons(self):
        for item in self.children:
            item.disabled = True

    def is_all_finished(self):
        return all(h["finished"] for h in self.hands)

    async def process_next_hand(self, interaction):
        self.hands[self.active_hand_idx]["finished"] = True
        self.active_hand_idx += 1
        
        if self.active_hand_idx >= len(self.hands):
            await self.finish_game(interaction)
        else:
            self._update_buttons()
            await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def settle_immediate_blackjack(self, outcome):
        self.disable_all_buttons()
        hand = self.hands[0]
        hand["finished"] = True
        
        if outcome == "blackjack":
            payout = round(hand["bet"] * 2.5, 2)
            hand["result_text"] = f"Blackjack! Выплата: **{self.bot.format_money(payout)}**"
        elif outcome == "push":
            payout = hand["bet"]
            hand["result_text"] = f"Ничья. Ставка возвращена: **{self.bot.format_money(payout)}**"
        else:
            payout = 0.0
            hand["result_text"] = "Вы проиграли. Блэкджек у дилера."
            
        if payout > 0:
            async with self.bot.economy_lock:
                account = self.bot.get_account(self.user_id)
                account["cash"] += payout
                self.bot.save_economy()

    async def finish_game(self, interaction=None):
        self.disable_all_buttons()
        
        needs_dealer = any(blackjack_hand_value(h["cards"]) <= 21 for h in self.hands)
        if needs_dealer:
            while blackjack_hand_value(self.dealer_hand) < 17 and self.deck:
                self.dealer_hand.append(self.deck.pop())

        dealer_value = blackjack_hand_value(self.dealer_hand)
        total_payout = 0.0
        
        async with self.bot.economy_lock:
            account = self.bot.get_account(self.user_id)
            for hand in self.hands:
                player_value = blackjack_hand_value(hand["cards"])
                bet = hand["bet"]
                
                if player_value > 21:
                    outcome = "loss"
                elif dealer_value > 21 or player_value > dealer_value:
                    outcome = "win"
                elif player_value == dealer_value:
                    outcome = "push"
                else:
                    outcome = "loss"
                    
                if outcome == "win":
                    payout = round(bet * 2, 2)
                    hand["result_text"] = f"Вы выиграли. Выплата: **{self.bot.format_money(payout)}**"
                    account["cash"] += payout
                    total_payout += payout
                elif outcome == "push":
                    payout = bet
                    hand["result_text"] = f"Ничья. Ставка возвращена: **{self.bot.format_money(payout)}**"
                    account["cash"] += payout
                    total_payout += payout
                else:
                    hand["result_text"] = "Вы проиграли. Ставка остаётся у дилера."
            self.bot.save_economy()

        embed = self.build_embed(reveal_dealer=True)
        if interaction:
            await interaction.response.edit_message(embed=embed, view=self)
            if total_payout >= self.initial_bet * 2 and self.initial_bet >= 100:
                await interaction.channel.send(
                    f"🎉 {interaction.user.mention} только что выиграл в блэкджек! Выплата: **{self.bot.format_money(total_payout)}**!"
                )
        elif self.message:
            try:
                await self.message.edit(embed=embed, view=self)
            except discord.HTTPException:
                pass

    @discord.ui.button(label="Взять", style=discord.ButtonStyle.primary, custom_id="hit")
    async def hit_button(self, interaction, button):
        hand = self.hands[self.active_hand_idx]
        hand["cards"].append(self.deck.pop())
        
        if blackjack_hand_value(hand["cards"]) > 21:
            hand["result_text"] = "Перебор!"
            await self.process_next_hand(interaction)
        else:
            self._update_buttons()
            await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="Стоп", style=discord.ButtonStyle.secondary, custom_id="stand")
    async def stand_button(self, interaction, button):
        await self.process_next_hand(interaction)

    @discord.ui.button(label="Дабл", style=discord.ButtonStyle.success, custom_id="double")
    async def double_button(self, interaction, button):
        hand = self.hands[self.active_hand_idx]
        bet = hand["bet"]
        
        async with self.bot.economy_lock:
            account = self.bot.get_account(self.user_id)
            if account["cash"] + 0.0001 < bet:
                self.bot.save_economy()
                await interaction.response.send_message(
                    f"Недостаточно денег для дабла. Нужно еще **{self.bot.format_money(bet)}**.", 
                    ephemeral=True
                )
                return
            account["cash"] -= bet
            self.bot.save_economy()
            
        hand["bet"] *= 2
        hand["cards"].append(self.deck.pop())
        
        if blackjack_hand_value(hand["cards"]) > 21:
            hand["result_text"] = "Перебор!"
            
        await self.process_next_hand(interaction)

    @discord.ui.button(label="Сплит", style=discord.ButtonStyle.primary, custom_id="split")
    async def split_button(self, interaction, button):
        hand = self.hands[self.active_hand_idx]
        bet = hand["bet"]
        
        async with self.bot.economy_lock:
            account = self.bot.get_account(self.user_id)
            if account["cash"] + 0.0001 < bet:
                self.bot.save_economy()
                await interaction.response.send_message(
                    f"Недостаточно денег для сплита. Нужно еще **{self.bot.format_money(bet)}**.", 
                    ephemeral=True
                )
                return
            account["cash"] -= bet
            self.bot.save_economy()
            
        card1 = hand["cards"][0]
        card2 = hand["cards"][1]
        
        hand["cards"] = [card1, self.deck.pop()]
        
        new_hand = {"cards": [card2, self.deck.pop()], "bet": bet, "result_text": "", "finished": False}
        self.hands.append(new_hand)
        
        self._update_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def on_timeout(self):
        if self.is_all_finished():
            return
            
        self.disable_all_buttons()
        
        async with self.bot.economy_lock:
            account = self.bot.get_account(self.user_id)
            for hand in self.hands:
                if not hand["finished"]:
                    account["cash"] += hand["bet"]
                    hand["result_text"] = f"Таймаут. Возврат: **{self.bot.format_money(hand['bet'])}**"
                    hand["finished"] = True
            self.bot.save_economy()
            
        if self.message:
            try:
                await self.message.edit(embed=self.build_embed(reveal_dealer=True), view=self)
            except discord.HTTPException:
                pass



class CasinoCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="blackjack", description="Сыграть blackjack с дилером")
    @app_commands.describe(bet="Ставка деньгами. 0 — без ставки")
    async def blackjack_command(self, interaction: discord.Interaction, bet: float = 0.0):
        bet, error = self.bot.validate_bet(bet)
        if error:
            await interaction.response.send_message(error, ephemeral=True)
            return
    
        async with self.bot.economy_lock:
            account = self.bot.get_account(interaction.user.id)
            self.bot.accrue_deposit_interest(account)
            if account["cash"] + 0.0001 < bet:
                self.bot.save_economy()
                await interaction.response.send_message(
                    f"Недостаточно денег для ставки **{self.bot.format_money(bet)}**. "
                    f"У вас **{self.bot.format_money(account['cash'])}**.",
                    ephemeral=True,
                )
                return
    
            account["cash"] -= bet
            self.bot.save_economy()
    
        deck = build_card_deck()
        random.shuffle(deck)
        player_hand = [deck.pop(), deck.pop()]
        dealer_hand = [deck.pop(), deck.pop()]
        view = BlackjackView(self.bot, interaction.user.id, bet, deck, player_hand, dealer_hand)
    
        await interaction.response.defer(ephemeral=True)
        player_blackjack = blackjack_hand_value(player_hand) == 21
        dealer_blackjack = blackjack_hand_value(dealer_hand) == 21
    
        if player_blackjack or dealer_blackjack:
            if player_blackjack and dealer_blackjack:
                outcome = "push"
            elif player_blackjack:
                outcome = "blackjack"
            else:
                outcome = "loss"
    
            await view.settle_immediate_blackjack(outcome)
            view.message = await interaction.followup.send(
                embed=view.build_embed(reveal_dealer=True), view=view, ephemeral=True
            )
            if outcome in ("blackjack", "win") and bet >= 100:
                await interaction.channel.send(
                    f"🎉 {interaction.user.mention} только что сорвал куш в блэкджек! Выигрыш: **{self.bot.format_money(bet * (2.5 if outcome == 'blackjack' else 2))}**!"
                )
            return
    
        view.message = await interaction.followup.send(
            embed=view.build_embed(), view=view, wait=True, ephemeral=True
        )
        
    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        import traceback
        print(f"Casino Cog error: {error}")
        traceback.print_exception(type(error), error, error.__traceback__)
        if not interaction.response.is_done():
            await interaction.response.send_message(f"Произошла ошибка: {error}", ephemeral=True)
    
    

async def setup(bot):
    await bot.add_cog(CasinoCog(bot))
