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
    
    try:
        await db_service.initialize()
        print("Database initialized successfully!")
    except Exception as e:
        print(f"Database initialization error: {e}")
    
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash commands globally!")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
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
