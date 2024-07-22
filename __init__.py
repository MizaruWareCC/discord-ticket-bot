import discord
from discord.ext import commands
import os
import discord.ext.commands
import traceback
import asyncpg

import discord.ext

  


async def load_cogs():
    try:
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                try:
                    await bot.load_extension(f'cogs.{filename[:-3]}')
                except commands.errors.ExtensionFailed as e:
                    print(f'Failed to load {filename[:-3]}.\n')
                    traceback.print_exc()
        await bot.load_extension('jishaku')
    except FileNotFoundError:
        print('No cogs folder, skipping...')


class bot_(commands.Bot):   
    async def setup_hook(self):
        self.remove_command('help')
        await load_cogs()
        self.db = await asyncpg.create_pool(dsn="postgres://postgres:1234@localhost:5432/tickets")
        async with self.db.acquire() as conn:
            await conn.execute('''
            CREATE TABLE IF NOT EXISTS tickets(
                               id SERIAL,
                               guild_id BIGINT,
                               thread_id BIGINT,
                               opener_id BIGINT,
                               date TIMESTAMP WITH TIME ZONE,
                               status CHAR(6))
            ''')
            '''
            Example:
            id guild_id   channel_id opener_id  date                                                                          status
            1  1234567890 1234567890 1234567890 datetime.datetime(year=0, month=0, week=0, day=0, hour=0, minute=0, second=0) active/closed
            '''
            await conn.execute('''
            CREATE TABLE IF NOT EXISTS gui_messages(
                               guild_id BIGINT,
                               channel_id BIGINT,
                               message_id BIGINT,
                               creator_id BIGINT)
            ''')
            await conn.execute('''
            CREATE TABLE IF NOT EXISTS settings(
                               guild_id BIGINT PRIMARY KEY,
                               channel_id BIGINT,
                               channel_log_id BIGINT,
                               options JSON)
            ''')

intents = discord.Intents.default()
intents.message_content = True

PREFIX_LIST = ['!']

bot = bot_(command_prefix=PREFIX_LIST, intents=intents)
bot.strip_after_prefix = True

@bot.command()
@discord.ext.commands.is_owner()
async def sync(ctx: discord.ext.commands.Context, guild: str | None = None):
    if guild:
        result = await bot.tree.sync(guild=ctx.guild.id)
    else:
        result = await bot.tree.sync()
    
    await ctx.send(len(result))

bot.run('')