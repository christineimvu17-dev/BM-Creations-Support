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

# Configuration
ORDER_CHANNEL_ID = 1435161427878084618
STAFF_ROLE_NAME = "Staff"  # Change this to your staff role name

# Store active tickets/orders
active_tickets = {}

def is_staff(ctx):
    """Check if user has staff role."""
    if ctx.guild is None:
        return False
    staff_role = discord.utils.get(ctx.guild.roles, name=STAFF_ROLE_NAME)
    if staff_role is None:
        # If role doesn't exist, allow anyone (for testing)
        return True
    return staff_role in ctx.author.roles  

def generate_order_id():
    """Generate a random order ID."""
    random_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=7))
    random_suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"ORD-{random_id}-{random_suffix}"

@bot.event
async def on_ready():
    print(f"{bot.user} is now online and ready!")

@bot.command()
async def newticket(ctx, customer_name: str, *, order_details: str):
    """Create a new ticket for a customer order."""
    # Delete the command message
    await ctx.message.delete()
    
    # Check if user has staff permissions
    if not is_staff(ctx):
        error_msg = await ctx.send("❌ You don't have permission to use this command. Staff only!")
        await error_msg.delete(delay=5)
        return
    
    # Generate unique order ID
    order_id = generate_order_id()
    
    # Get current timestamp
    us_eastern = pytz.timezone('America/New_York')
    created_at = datetime.now(us_eastern).strftime("%B %d, %Y at %I:%M %p EST")
    
    # Store ticket information
    active_tickets[order_id] = {
        'customer_name': customer_name,
        'order_details': order_details,
        'ticket_channel': ctx.channel.mention,
        'ticket_channel_id': ctx.channel.id,
        'created_at': created_at,
        'created_timestamp': datetime.now(us_eastern)
    }
    
    # Create ticket embed
    embed = discord.Embed(
        title="🎫 New Ticket Created",
        description=f"A new order ticket has been created for **{customer_name}**",
        color=0x5865F2
    )
    
    embed.add_field(name="🆔 Order ID", value=order_id, inline=False)
    embed.add_field(name="👤 Customer", value=customer_name, inline=True)
    embed.add_field(name="📌 Ticket Channel", value=ctx.channel.mention, inline=True)
    embed.add_field(name="📦 Order Details", value=order_details, inline=False)
    embed.add_field(name="🕒 Created At", value=created_at, inline=False)
    embed.add_field(name="💼 Status", value="🟡 IN PROGRESS", inline=False)
    
    embed.set_footer(text="Use !completeorder <order_id> to mark this order as complete")
    
    await ctx.send(embed=embed)
    print(f"New ticket created: {order_id} for {customer_name}")

@bot.command()
async def completeorder(ctx, order_id: str):
    """Complete a ticket and post to order status channel."""
    # Delete the command message
    await ctx.message.delete()
    
    # Check if user has staff permissions
    if not is_staff(ctx):
        error_msg = await ctx.send("❌ You don't have permission to use this command. Staff only!")
        await error_msg.delete(delay=5)
        return
    
    # Check if order exists
    if order_id not in active_tickets:
        error_msg = await ctx.send(f"❌ Order ID `{order_id}` not found in active tickets.")
        await error_msg.delete(delay=5)
        return
    
    # Get ticket information
    ticket = active_tickets[order_id]
    
    # Get order status channel
    status_channel = bot.get_channel(ORDER_CHANNEL_ID)
    if not status_channel:
        await ctx.send("❌ Order status channel not found. Please check the channel ID.")
        return
    
    # Get current timestamp for completion
    us_eastern = pytz.timezone('America/New_York')
    completed_at = datetime.now(us_eastern).strftime("%B %d, %Y at %I:%M %p EST")
    
    # Create completion embed
    embed = discord.Embed(
        title="✅ Order Completed",
        description="Thank you for shopping with **BM Creations Market! 🎉**\nYour order has been successfully delivered.",
        color=0x57F287
    )
    
    embed.add_field(name="🌐 Discord Server", value="[Join Server](https://discord.gg/NR4Z9zeBW2)", inline=False)
    embed.add_field(name="📸 Instagram", value="[Instagram Link](https://www.instagram.com/imvu_trustedshop)", inline=False)
    embed.add_field(name="🆔 Order ID", value=order_id, inline=False)
    embed.add_field(name="👤 Customer", value=ticket['customer_name'], inline=False)
    embed.add_field(name="📌 Ticket Channel", value=ticket['ticket_channel'], inline=False)
    embed.add_field(name="📦 Order Details", value=ticket['order_details'], inline=False)
    embed.add_field(name="🕒 Completed At", value=completed_at, inline=False)
    embed.add_field(name="💚 Status", value="✅ DELIVERED", inline=False)
    
    embed.set_footer(text="BM Creations Support • Trusted Since 2020")
    
    # Send to order status channel
    await status_channel.send(embed=embed)
    
    # Send to ticket channel (for buyer to see)
    ticket_channel = bot.get_channel(ticket['ticket_channel_id'])
    if ticket_channel:
        await ticket_channel.send(embed=embed)
    
    # Confirm in current channel (only if different from ticket channel)
    if ctx.channel.id != ticket['ticket_channel_id']:
        confirm_msg = await ctx.send(f"✅ Order `{order_id}` has been marked as complete and posted!")
        await confirm_msg.delete(delay=5)
    
    # Remove from active tickets
    del active_tickets[order_id]
    print(f"Order completed: {order_id}")

@bot.command()
async def viewtickets(ctx):
    """View all active tickets."""
    await ctx.message.delete()
    
    # Check if user has staff permissions
    if not is_staff(ctx):
        error_msg = await ctx.send("❌ You don't have permission to use this command. Staff only!")
        await error_msg.delete(delay=5)
        return
    
    if not active_tickets:
        msg = await ctx.send("📋 No active tickets at the moment.")
        await msg.delete(delay=5)
        return
    
    embed = discord.Embed(
        title="📋 Active Tickets",
        description=f"Currently tracking {len(active_tickets)} active order(s)",
        color=0xFEE75C
    )
    
    for order_id, ticket in active_tickets.items():
        ticket_info = f"👤 **Customer:** {ticket['customer_name']}\n"
        ticket_info += f"📦 **Details:** {ticket['order_details'][:50]}{'...' if len(ticket['order_details']) > 50 else ''}\n"
        ticket_info += f"🕒 **Created:** {ticket['created_at']}\n"
        ticket_info += f"📌 **Channel:** {ticket['ticket_channel']}"
        
        embed.add_field(name=f"🆔 {order_id}", value=ticket_info, inline=False)
    
    embed.set_footer(text="Use !completeorder <order_id> to complete an order")
    
    await ctx.send(embed=embed)

# Run the bot
bot.run(os.getenv("TOKEN"))
