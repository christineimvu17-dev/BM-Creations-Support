import discord
from discord.ext import commands
import os
from datetime import datetime
import pytz
import random
import string

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Replace this with your real channel ID later
ORDER_CHANNEL_ID = 1435161427878084618  

@bot.event
async def on_ready():
    print(f"{bot.user} is now online and ready!")

@bot.command()
async def order(ctx, *, details="Not specified"):
    """Send an order completion message in the order-status channel."""
    # Delete the command message instantly
    await ctx.message.delete()
    
    channel = bot.get_channel(ORDER_CHANNEL_ID)
    if not channel:
        await ctx.send("❌ Order channel not found. Please check the channel ID.")
        return

    # Generate random order ID
    random_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=7))
    random_suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    order_id = f"ORD-{random_id}-{random_suffix}"

    embed = discord.Embed(
        title="✅ Order Completed",
        description="Thank you for shopping with **BM Creations Market! 🎉**\nYour order has been successfully delivered.",
        color=0x57F287
    )

    embed.add_field(name="🌐 Discord Server", value="[Join Server](https://discord.gg/NR4Z9zeBW2)", inline=False)
    embed.add_field(name="📸 Instagram", value="[Instagram Link](https://www.instagram.com/imvu_trustedshop)", inline=False)
    embed.add_field(name="🆔 Order ID", value=order_id, inline=False)
    embed.add_field(name="👤 Customer", value="Privacy Protected", inline=False)
    embed.add_field(name="📌 Ticket Channel", value="#No Access", inline=False)
    embed.add_field(name="📦 Order Details", value=details, inline=False)
    
    # Get current timestamp in US Eastern Time
    us_eastern = pytz.timezone('America/New_York')
    timestamp = datetime.now(us_eastern).strftime("%B %d, %Y at %I:%M %p EST")
    embed.add_field(name="🕒 Completed At", value=timestamp, inline=False)
    embed.add_field(name="💚 Status", value="✅ DELIVERED", inline=False)

    embed.set_footer(text="BM Creations Support • Trusted Since 2020")

    await channel.send(embed=embed)

# Run the bot
bot.run(os.getenv("TOKEN"))
