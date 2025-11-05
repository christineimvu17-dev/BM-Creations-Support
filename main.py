import discord
from discord.ext import commands
import os
from datetime import datetime

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
    channel = bot.get_channel(ORDER_CHANNEL_ID)
    if not channel:
        await ctx.send("❌ Order channel not found. Please check the channel ID.")
        return

    embed = discord.Embed(
        title="✅ Order Completed",
        description="Thank you for shopping with **BM Creations Market! 🎉**\nYour order has been successfully delivered.",
        color=0x57F287
    )

    embed.add_field(name="🌐 Discord Server", value="[Join Server](https://discord.gg/NR4Z9zeBW2)", inline=False)
    embed.add_field(name="📸 Instagram", value="[Instagram Link](https://www.instagram.com/imvu_trustedshop)", inline=False)
    embed.add_field(name="🆔 Order ID", value="ORD-XXXXXXX-XXXXXX", inline=False)
    embed.add_field(name="👤 Customer", value="Privacy Protected", inline=False)
    embed.add_field(name="📌 Ticket Channel", value="#No Access", inline=False)
    embed.add_field(name="📦 Order Details", value=details, inline=False)
    
    # Get current timestamp
    timestamp = datetime.now().strftime("%B %d, %Y at %I:%M %p")
    embed.add_field(name="🕒 Completed At", value=timestamp, inline=False)
    embed.add_field(name="💚 Status", value="✅ DELIVERED", inline=False)

    embed.set_footer(text="BM Creations Support • Trusted Since 2020")

    await channel.send(embed=embed)
    await ctx.send("✅ Order message sent to #『☎️』order-status!")

# Run the bot
bot.run(os.getenv("TOKEN"))
