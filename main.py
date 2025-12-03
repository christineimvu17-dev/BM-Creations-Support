import discord
from discord.ext import commands
from discord import app_commands
import os
import asyncio
from flask import Flask
from threading import Thread

from src.config import Config
from src.services.database import db_service

app = Flask('')

@app.route('/')
def home():
    return "BM Creations Bot is alive and running!"

def run_flask():
    app.run(host='0.0.0.0', port=5000)

def keep_alive():
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix=Config.BOT_PREFIX, intents=intents, help_command=None)

COGS = [
    "src.cogs.core",
    "src.cogs.tickets",
    "src.cogs.orders",
    "src.cogs.commerce",
    "src.cogs.faq",
    "src.cogs.moderation",
    "src.cogs.announcements",
    "src.cogs.feedback",
    "src.cogs.reminders",
    "src.cogs.analytics",
    "src.cogs.recommendations",
    "src.cogs.sync",
    "src.cogs.external_api",
    "src.cogs.support_interaction",
]

async def load_cogs():
    for cog in COGS:
        try:
            await bot.load_extension(cog)
            print(f"Loaded cog: {cog}")
        except Exception as e:
            print(f"Failed to load cog {cog}: {e}")

@bot.event
async def on_ready():
    print(f"{bot.user.name} is now online and ready!")
    print(f"Bot ID: {bot.user.id}")
    print(f"Connected to {len(bot.guilds)} guilds")
    
    try:
        await db_service.initialize()
        print("Database initialized successfully!")
    except Exception as e:
        print(f"Database initialization error: {e}")
    
    all_commands = bot.tree.get_commands()
    print(f"\nCommands in tree before sync: {len(all_commands)}")
    for cmd in all_commands[:10]:
        print(f"  - /{cmd.name}: {cmd.description}")
    if len(all_commands) > 10:
        print(f"  ... and {len(all_commands) - 10} more")
    
    for guild in bot.guilds:
        try:
            bot.tree.copy_global_to(guild=guild)
            synced = await bot.tree.sync(guild=guild)
            print(f"Synced {len(synced)} slash commands to guild: {guild.name}")
        except Exception as e:
            print(f"Failed to sync to guild {guild.name}: {e}")
    
    try:
        global_synced = await bot.tree.sync()
        print(f"Also synced {len(global_synced)} slash commands globally")
    except Exception as e:
        print(f"Failed to sync globally: {e}")
    
    print("\n=== BOT INVITE LINK ===")
    print(f"If slash commands don't work, re-invite the bot with this link:")
    print(f"https://discord.com/api/oauth2/authorize?client_id={bot.user.id}&permissions=8&scope=bot%20applications.commands")
    print("========================\n")

OWNER_USERNAMES = ["sizuka42"]

def is_owner(user: discord.User) -> bool:
    username_lower = user.name.lower()
    for owner_name in OWNER_USERNAMES:
        if username_lower == owner_name.lower():
            return True
    return False

def is_server_admin(interaction: discord.Interaction) -> bool:
    if not interaction.guild:
        return False
    
    member = interaction.guild.get_member(interaction.user.id)
    if not member:
        return False
    
    return member.guild_permissions.administrator

@bot.tree.interaction_check
async def global_command_check(interaction: discord.Interaction) -> bool:
    if is_owner(interaction.user):
        return True
    
    if is_server_admin(interaction):
        return True
    
    await interaction.response.send_message(
        "Only the owner can use bot commands. If you need help, please create a thread or message in the support channel!",
        ephemeral=True
    )
    return False

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CheckFailure):
        return
    elif isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
    elif isinstance(error, app_commands.CommandOnCooldown):
        await interaction.response.send_message(f"Command on cooldown. Try again in {error.retry_after:.1f}s", ephemeral=True)
    else:
        print(f"Error in slash command: {error}")
        import traceback
        traceback.print_exception(type(error), error, error.__traceback__)
        try:
            if interaction.response.is_done():
                await interaction.followup.send("An error occurred while processing this command.", ephemeral=True)
            else:
                await interaction.response.send_message("An error occurred while processing this command.", ephemeral=True)
        except:
            pass

async def main():
    async with bot:
        await load_cogs()
        await bot.start(Config.TOKEN)

if __name__ == "__main__":
    keep_alive()
    asyncio.run(main())
