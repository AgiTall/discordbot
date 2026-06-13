import asyncio
import random
from unittest.mock import Mock
import bot

async def test():
    bot.ECONOMY_FILE = 'test_economy.json'
    bot.economy_data = bot.EconomyStore({'version': 2, 'guilds': {'123': bot.default_economy()}})
    
    bot.set_economy_guild_id(123)
    account = bot.get_account(456)
    account['cash'] = 1309.96
    account['gold'] = 4.56
    account['treasure_maps'] = 2
    bot.save_economy()
    
    account = bot.get_account(456)
    account['treasure_maps'] -= 1
    remaining_maps = account['treasure_maps']
    bot.save_economy()
    
    view = bot.TreasureHuntView(456, 0, remaining_maps, guild_id=123)
    
    bot.set_economy_guild_id(123)
    
    interaction = Mock()
    interaction.user.id = 456
    interaction.guild_id = 123
    
    res = await view.grant_reward(interaction)
    
    acc2 = bot.get_account(456)
    print(f'Cash: {acc2["cash"]}, Gold: {acc2["gold"]}, Maps: {acc2["treasure_maps"]}')

asyncio.run(test())
