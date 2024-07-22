from discord.ext.commands import GroupCog
from discord.app_commands import command as acmd
from discord import Interaction
from discord.ext.commands import Bot
from asyncpg import Pool
import discord
from discord.ui import DynamicItem
import re
import json

# TODO: maybe ill fix it later :/
# class Ticket:
#     def __init__(self, thread_id: int, guild: discord.Guild, db):
#         self.db = db
#         self.guild = guild
#         self.thread_id = thread_id
    
#     async def close(self):
#         async with self.db.acquire() as con:
#             await con.execute('UPDATE tickets SET status = $1 WHERE thread_id = $2', 'closed', self.thread_id)
#             thread = self.guild.get_thread(self.thread_id)
#             await thread.edit(archived=True)
    
#     @classmethod
#     async def create(cls, guild: discord.Guild, interaction: Interaction, channel: discord.TextChannel, channel_log: discord.TextChannel, topic: str = None):
#         bot = interaction.client
#         db = bot.db
#         async with self.db.acquire() as con:
#             fetch = await con.fetchval('SELECT thread_id FROM tickets WHERE guild_id = $1 AND opener_id = $2 AND status = $3', interaction.guild_id, interaction.user.id, 'active')
#             if fetch:
#                 return await interaction.response.send_message(f'You already have a ticket: <#{fetch}>.', ephemeral=True)

#             fetch = await con.fetchval('SELECT channel_id FROM settings WHERE guild_id = $1', interaction.guild.id)
#             if not fetch:
#                 return await interaction.response.send_message('Staff didn\'t configure a channel for the bot.', ephemeral=True)
            
#             chn = self.bot.get_channel(fetch)
#             if not chn:
#                 return await interaction.response.send_message('The configured channel was deleted.', ephemeral=True)
            
#             await interaction.response.send_message('Opening a ticket, please wait...', ephemeral=True)
#             thread = await chn.create_thread(name=f'Ticket for {interaction.user.display_name[:10]}', type=discord.ChannelType.private_thread, invitable=False)
#             await thread.join()
#             await con.execute('INSERT INTO tickets(guild_id, thread_id, opener_id, date, status) VALUES ($1, $2, $3, $4, $5)', interaction.guild.id, thread.id, interaction.user.id, discord.utils.utcnow(), 'active')
#             await thread.add_user(interaction.user)
#             await thread.send(content=f"Ticket topic: {self.values[0]}", view=discord.ui.View().add_item(CloseTicketButton(self.bot, self.db, thread.id)))
#             await interaction.edit_original_response(content=f'Created ticket: <#{thread.id}>')
#             await self.original_response.edit(view=discord.ui.View(timeout=0).add_item(self))
#             return cls(thread.id)

class ConfirmCloseButton(DynamicItem[discord.ui.Button], template=r'confirm_close_button:(?P<user_id>[0-9]+):(?P<thread_id>[0-9]+)'):
    def __init__(self, bot, db, user_id: int, thread_id: int):
        super().__init__(
            discord.ui.Button(
                label='Confirm ticket closing',
                style=discord.ButtonStyle.primary,
                emoji='\U00002705',
                custom_id=f'confirm_close_button:{user_id}:{thread_id}',
            )
        )
        self.bot = bot
        self.db = db
        self.user_id = user_id
        self.thread_id = thread_id

    @classmethod
    async def from_custom_id(cls, interaction: discord.Interaction, item: discord.ui.Button, match: re.Match[str], /):
        bot = interaction.client
        db = bot.db
        user_id = int(match['user_id'])
        thread_id = int(match['thread_id'])
        return cls(bot, db, user_id, thread_id)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True)
        async with self.db.acquire() as con:
            await con.execute('UPDATE tickets SET status = $1 WHERE thread_id = $2', 'closed', self.thread_id)
            thread = interaction.guild.get_thread(self.thread_id)
            await thread.edit(archived=True)
            await interaction.edit_original_response(content=f'Archived ticket. Closed by <@{self.user_id}>')


class CloseTicketButton(DynamicItem[discord.ui.Button], template=r'close_ticket_button:(?P<thread_id>[0-9]+)'):
    def __init__(self, bot, db, thread_id: int):
        super().__init__(
            discord.ui.Button(
                label='Close',
                style=discord.ButtonStyle.danger,
                emoji='\U0001f6d1',
                custom_id=f'close_ticket_button:{thread_id}',
            )
        )
        self.bot = bot
        self.db = db
        self.thread_id = thread_id

    @classmethod
    async def from_custom_id(cls, interaction: discord.Interaction, item: discord.ui.Button, match: re.Match[str], /):
        bot = interaction.client
        db = bot.db
        thread_id = int(match['thread_id'])
        return cls(bot, db, thread_id)

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(view=discord.ui.View().add_item(
            ConfirmCloseButton(self.bot, self.db, interaction.user.id, self.thread_id)))
        
class JoinTicketButton(DynamicItem[discord.ui.Button], template=r'join_ticket_button:(?P<thread_id>[0-9]+)'):
    def __init__(self, thread_id: int):
        super().__init__(
            discord.ui.Button(
                label='Join ticket',
                style=discord.ButtonStyle.green,
                emoji='\U0001f39f',
                custom_id=f'join_ticket_button:{thread_id}',
            )
        )
        self.thread_id = thread_id

    @classmethod
    async def from_custom_id(cls, interaction: discord.Interaction, item: discord.ui.Button, match: re.Match[str], /):
        thread_id = int(match['thread_id'])
        return cls(thread_id)

    async def callback(self, interaction: discord.Interaction) -> None:
       await interaction.response.defer()
       thread = interaction.guild.get_thread(self.thread_id)
       if not thread:
           self.item.disabled = True
           return await interaction.edit_original_response(content='Ticket got closed', view=discord.ui.View().add_item(self.item))
       await thread.add_user(interaction.user)

class CreateTicketSelect(discord.ui.Select):
    def __init__(self, bot, db, options, original_response):
        options = [
            discord.SelectOption(label=label, value=label) 
            for label in (json.loads(options) if isinstance(options, str) else options)
        ]
        super().__init__(
            placeholder='Select ticket reason',
            options=options,
            custom_id='create_ticket_select'
        )
        self.bot = bot
        self.db = db
        self.original_response = original_response
    
    async def callback(self, interaction: discord.Interaction):
        async with self.db.acquire() as con:
            fetch = await con.fetchval('SELECT thread_id FROM tickets WHERE guild_id = $1 AND opener_id = $2 AND status = $3', interaction.guild_id, interaction.user.id, 'active')
            if fetch:
                return await interaction.response.send_message(f'You already have a ticket: <#{fetch}>.', ephemeral=True)

            fetch = await con.fetchval('SELECT channel_id FROM settings WHERE guild_id = $1', interaction.guild.id)
            if not fetch:
                return await interaction.response.send_message('Staff didn\'t configure a channel for the bot.', ephemeral=True)
            
            chn = self.bot.get_channel(fetch)
            if not chn:
                return await interaction.response.send_message('The configured channel was deleted.', ephemeral=True)
            
            fetch = await con.fetchval('SELECT channel_log_id FROM settings WHERE guild_id = $1', interaction.guild.id)
            if not fetch:
                return await interaction.response.send_message('Staff didn\'t configure a channel for the bot.', ephemeral=True)
            
            chnlog = self.bot.get_channel(fetch)
            if not chnlog:
                return await interaction.response.send_message('The configured channel was deleted.', ephemeral=True)
            
            await interaction.response.send_message('Opening a ticket, please wait...', ephemeral=True)
            thread = await chn.create_thread(name=f'Ticket for {interaction.user.display_name[:10]}', type=discord.ChannelType.private_thread, invitable=False)
            await thread.join()
            await con.execute('INSERT INTO tickets(guild_id, thread_id, opener_id, date, status) VALUES ($1, $2, $3, $4, $5)', interaction.guild.id, thread.id, interaction.user.id, discord.utils.utcnow(), 'active')
            await thread.add_user(interaction.user)
            await thread.send(content=f"Ticket topic: {self.values[0]}", view=discord.ui.View().add_item(CloseTicketButton(self.bot, self.db, thread.id)))
            await interaction.edit_original_response(content=f'Created ticket: <#{thread.id}>')
            self.disabled = True
            await self.original_response.edit(view=discord.ui.View(timeout=0).add_item(self))
            await chnlog.send(content=f"Opened by {interaction.user.mention}, topic: {self.values[0]}", view=discord.ui.View().add_item(JoinTicketButton(thread.id)))

            
        

class CreateTicketButton(DynamicItem[discord.ui.Button], template=r'create_ticket_button'):
    def __init__(self, bot, db):
        super().__init__(
            discord.ui.Button(
                label='Create ticket',
                style=discord.ButtonStyle.primary,
                emoji='\U00002705',
                custom_id='create_ticket_button',
            )
        )
        self.bot = bot
        self.db = db

    @classmethod
    async def from_custom_id(cls, interaction: discord.Interaction, item: discord.ui.Button, match: re.Match[str], /):
        bot = interaction.client
        db = bot.db
        return cls(bot, db)

    async def callback(self, interaction: discord.Interaction) -> None:
        async with self.db.acquire() as con:
            await interaction.response.defer(thinking=True, ephemeral=True)
            fetch = await con.fetchval('SELECT options FROM settings WHERE guild_id = $1', interaction.guild.id)
            if fetch and not fetch == 'null':
                original_response = await interaction.original_response()
                await interaction.followup.send(view=discord.ui.View(timeout=20).add_item(CreateTicketSelect(self.bot, self.db, fetch, original_response)))
            else:
                fetch = await con.fetchval('SELECT thread_id FROM tickets WHERE guild_id = $1 AND opener_id = $2 AND status = $3',
                interaction.guild_id, interaction.user.id, 'active')
                if fetch:
                    return await interaction.followup.send(f'You already have a ticket: <#{fetch}>.')

                
                fetch = await con.fetchval('SELECT channel_id FROM settings WHERE guild_id = $1', interaction.guild.id)
                if not fetch:
                    return await interaction.followup.send('Staff didn\'t configure a channel for the bot.')
                
                chn = self.bot.get_channel(fetch)
                if not chn:
                    return await interaction.followup.send('The configured channel was deleted.')
            
                fetch = await con.fetchval('SELECT channel_log_id FROM settings WHERE guild_id = $1', interaction.guild.id)
                if not fetch:
                    return await interaction.followup.send('Staff didn\'t configure a channel for the bot.', ephemeral=True)
                
                chnlog = self.bot.get_channel(fetch)
                if not chnlog:
                    return await interaction.followup.send('The configured channel was deleted.', ephemeral=True)
            
                
                await interaction.followup.send('Opening a ticket, please wait...')
                thread = await chn.create_thread(name=f'Ticket for {interaction.user.display_name[:10]}', type=discord.ChannelType.private_thread, invitable=False)
                await thread.join()
                await con.execute('INSERT INTO tickets(guild_id, thread_id, opener_id, date, status) VALUES ($1, $2, $3, $4, $5)', interaction.guild.id, thread.id, interaction.user.id, discord.utils.utcnow(), 'active')
                await thread.add_user(interaction.user)
                await thread.send(content="", view=discord.ui.View().add_item(CloseTicketButton(self.bot, self.db, thread.id)))
                await interaction.edit_original_response(content=f'Created ticket: <#{thread.id}>')
                await chnlog.send(content=f"Opened by {interaction.user.mention}", view=discord.ui.View().add_item(JoinTicketButton(thread.id)))


            

class tickets(GroupCog, name='ticket', description='Commands for administrators to manage bot'):
    def __init__(self, bot: Bot):
        self.bot: Bot = bot
        bot.add_dynamic_items(ConfirmCloseButton, JoinTicketButton, CloseTicketButton, CreateTicketButton)
    
    @acmd(name='create_message')
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def create_message(self, interaction: Interaction):
        async with self.bot.db.acquire() as con:
            con: Pool = con
            fetch = await con.fetchrow('SELECT channel_id, message_id FROM gui_messages WHERE guild_id = $1', interaction.guild.id)
            if fetch:
                chn = self.bot.get_channel(fetch[0])
                if chn:
                    try:
                        msg = await chn.fetch_message(fetch[1])
                        if msg:
                            return await interaction.response.send_message('This guild already have ticket ui message, delete message to create new.', ephemeral=True)
                    except:
                        await con.execute('DELETE FROM gui_messages WHERE guild_id = $1', interaction.guild.id)
            
            await interaction.response.send_message('Sending...', ephemeral=True)
            await interaction.channel.send(view=discord.ui.View().add_item(CreateTicketButton(self.bot, self.bot.db)))
            orp = await interaction.original_response()
            await con.execute('INSERT INTO gui_messages VALUES ($1, $2, $3, $4)', interaction.guild.id, interaction.channel.id, orp.id, interaction.user.id)
            await interaction.edit_original_response(content='Finished')

    @acmd(name='confiruge')
    @discord.app_commands.describe(options='Options to appear when creating ticket like select menu. Format: option 1~option 2. To remove, type DELOPT')
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def set_channel(self, interaction: Interaction, channel: discord.TextChannel=None, channel_log: discord.TextChannel=None, options: str = None): 
        async with self.bot.db.acquire() as con:
            con: Pool = con
            if options:
                options = options.split("~")
                if len(options) > 25:
                    return await interaction.response.send_message('You cant provide more than 25 options, discord limits :(', ephemeral=True)
                for option in options:
                    if len(option) > 100:
                        return await interaction.response.send_message('Discord allows only 100 characters for label :(', ephemeral=False)
            
            old_opt = await con.fetchval('SELECT options FROM settings WHERE guild_id = $1', interaction.guild.id)
            if options:
                if options[0].lower() == 'delopt':
                    old_opt = None
                    options = None
            old_chn = await con.fetchval('SELECT channel_id FROM settings WHERE guild_id = $1', interaction.guild.id)
            old_log_chn = await con.fetchval('SELECT channel_id FROM settings WHERE guild_id = $1', interaction.guild.id)
            await con.execute('INSERT INTO settings VALUES ($1, $2, $3, $4) ON CONFLICT (guild_id) DO UPDATE SET channel_id = $2, channel_log_id = $3, options = $4', interaction.guild.id, channel.id if channel else old_chn, channel_log.id if channel_log else old_log_chn, json.dumps(options) if options else old_opt)
            
        await interaction.response.send_message('Completed.', ephemeral=True)
        
    

async def setup(bot: Bot):
    await bot.add_cog(tickets(bot))