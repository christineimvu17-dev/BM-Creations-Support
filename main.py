import discord
from discord.ext import commands
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
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("You don't have permission to use this command.", delete_after=5)
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"Missing required argument: {error.param.name}", delete_after=5)
    elif isinstance(error, commands.CommandNotFound):
        pass
    elif isinstance(error, commands.BadArgument):
        await ctx.send(f"Invalid argument provided.", delete_after=5)
    else:
        print(f"Error in command {ctx.command}: {error}")

async def main():
    async with bot:
        await load_cogs()
        await bot.start(Config.TOKEN)

if __name__ == "__main__":
    keep_alive()
    asyncio.run(main())
