import discord
from discord.ext import commands
from datetime import datetime

from src.services.database import db_service
from src.models.database import OrderStatus
from src.utils.helpers import create_embed, is_staff, get_eastern_time, format_timestamp, get_status_emoji
from src.utils.translations import get_text
from src.config import Config

class OrdersCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    @commands.command(name="order")
    async def create_order(self, ctx: commands.Context, *, details: str):
        await ctx.message.delete()
        
        user = await db_service.get_or_create_user(
            ctx.author.id, ctx.guild.id, str(ctx.author), ctx.author.display_name
        )
        
        ticket = await db_service.get_ticket(channel_id=ctx.channel.id)
        
        items = [{"name": details, "quantity": 1, "price": 0.0}]
        
        order = await db_service.create_order(
            guild_id=ctx.guild.id,
            user_id=user.id,
            ticket_id=ticket.id if ticket else None,
            items=items,
            notes=details
        )
        
        lang = user.language
        
        embed = create_embed(
            title=f"{get_status_emoji('pending')} {get_text('order_created', lang)}",
            description=f"Your order has been created successfully!",
            color=Config.EMBED_COLOR
        )
        
        embed.add_field(name="Order ID", value=order.order_id, inline=True)
        embed.add_field(name="Customer", value=ctx.author.mention, inline=True)
        embed.add_field(name="Status", value=f"{get_status_emoji('pending')} Pending", inline=True)
        embed.add_field(name="Order Details", value=details, inline=False)
        embed.add_field(name="Created At", value=format_timestamp(get_eastern_time()), inline=False)
        
        embed.set_footer(text=f"Track your order with: !trackorder {order.order_id}")
        
        await ctx.send(embed=embed)
    
    @commands.command(name="trackorder")
    async def track_order(self, ctx: commands.Context, order_id: str):
        order = await db_service.get_order(order_id)
        
        if not order:
            await ctx.send("Order not found. Please check the order ID.", delete_after=5)
            return
        
        if order.user.discord_id != ctx.author.id and not is_staff(ctx.author):
            await ctx.send("You don't have permission to view this order.", delete_after=5)
            return
        
        status_timeline = [
            ("pending", "Order Placed"),
            ("confirmed", "Order Confirmed"),
            ("processing", "Processing"),
            ("shipped", "Shipped"),
            ("delivered", "Delivered")
        ]
        
        current_status_idx = next(
            (i for i, (s, _) in enumerate(status_timeline) if s == order.status.value),
            0
        )
        
        timeline_display = ""
        for i, (status, label) in enumerate(status_timeline):
            if i < current_status_idx:
                timeline_display += f"~~{get_status_emoji(status)} {label}~~\n"
            elif i == current_status_idx:
                timeline_display += f"**{get_status_emoji(status)} {label}** (Current)\n"
            else:
                timeline_display += f"- {label}\n"
        
        embed = create_embed(
            title=f"Order Tracking: {order.order_id}",
            description=f"Current Status: **{order.status.value.title()}**",
            color=Config.EMBED_COLOR
        )
        
        embed.add_field(name="Customer", value=f"<@{order.user.discord_id}>", inline=True)
        embed.add_field(name="Total Amount", value=f"${order.total_amount:.2f}", inline=True)
        embed.add_field(name="Created At", value=format_timestamp(order.created_at), inline=True)
        
        if order.tracking_number:
            embed.add_field(name="Tracking Number", value=order.tracking_number, inline=True)
        
        embed.add_field(name="Order Timeline", value=timeline_display, inline=False)
        
        if order.items:
            items_text = "\n".join([f"- {item.product_name} x{item.quantity}" for item in order.items])
            embed.add_field(name="Items", value=items_text[:1024], inline=False)
        
        if order.events:
            events_text = "\n".join([
                f"- {e.description} ({format_timestamp(e.created_at, '%m/%d %H:%M')})" 
                for e in order.events[-5:]
            ])
            embed.add_field(name="Recent Updates", value=events_text[:1024], inline=False)
        
        await ctx.send(embed=embed)
    
    @commands.command(name="myorders")
    async def my_orders(self, ctx: commands.Context):
        orders = await db_service.get_user_orders(ctx.author.id, ctx.guild.id)
        
        if not orders:
            await ctx.send("You have no orders yet.", delete_after=5)
            return
        
        embed = create_embed(
            title=f"Your Orders ({len(orders)} total)",
            description="Here are your recent orders:",
            color=Config.EMBED_COLOR
        )
        
        for order in orders[:10]:
            status_emoji = get_status_emoji(order.status.value)
            order_info = f"**Status:** {status_emoji} {order.status.value.title()}\n"
            order_info += f"**Total:** ${order.total_amount:.2f}\n"
            order_info += f"**Date:** {format_timestamp(order.created_at, '%m/%d/%Y')}"
            
            embed.add_field(name=f"Order: {order.order_id}", value=order_info, inline=False)
        
        embed.set_footer(text="Use !trackorder <order_id> to track a specific order")
        await ctx.send(embed=embed)
    
    @commands.command(name="updateorder")
    async def update_order(self, ctx: commands.Context, order_id: str, status: str, *, notes: str = None):
        await ctx.message.delete()
        
        if not is_staff(ctx.author):
            await ctx.send("You don't have permission to use this command.", delete_after=5)
            return
        
        status_map = {
            "pending": OrderStatus.PENDING,
            "confirmed": OrderStatus.CONFIRMED,
            "processing": OrderStatus.PROCESSING,
            "shipped": OrderStatus.SHIPPED,
            "delivered": OrderStatus.DELIVERED,
            "cancelled": OrderStatus.CANCELLED,
            "refunded": OrderStatus.REFUNDED
        }
        
        if status.lower() not in status_map:
            await ctx.send(f"Invalid status. Options: {', '.join(status_map.keys())}", delete_after=5)
            return
        
        order = await db_service.update_order_status(
            order_id, 
            status_map[status.lower()],
            staff_id=ctx.author.id
        )
        
        if not order:
            await ctx.send("Order not found.", delete_after=5)
            return
        
        embed = create_embed(
            title="Order Updated",
            description=f"Order **{order_id}** has been updated.",
            color=Config.SUCCESS_COLOR
        )
        
        embed.add_field(name="New Status", value=f"{get_status_emoji(status.lower())} {status.title()}", inline=True)
        embed.add_field(name="Updated By", value=ctx.author.mention, inline=True)
        
        if notes:
            embed.add_field(name="Notes", value=notes, inline=False)
        
        await ctx.send(embed=embed)
        
        try:
            user = self.bot.get_user(order.user.discord_id)
            if user:
                dm_embed = create_embed(
                    title=f"Order Update: {order_id}",
                    description=f"Your order status has been updated to: **{status.title()}**",
                    color=Config.EMBED_COLOR
                )
                if notes:
                    dm_embed.add_field(name="Notes", value=notes, inline=False)
                await user.send(embed=dm_embed)
        except:
            pass
    
    @commands.command(name="completeorder")
    async def complete_order(self, ctx: commands.Context, order_id: str):
        await ctx.message.delete()
        
        if not is_staff(ctx.author):
            await ctx.send("You don't have permission to use this command.", delete_after=5)
            return
        
        order = await db_service.update_order_status(
            order_id, 
            OrderStatus.DELIVERED,
            staff_id=ctx.author.id
        )
        
        if not order:
            await ctx.send("Order not found.", delete_after=5)
            return
        
        settings = await db_service.get_or_create_guild_settings(ctx.guild.id)
        
        embed = create_embed(
            title="Order Completed",
            description="Thank you for shopping with **BM Creations Market!**\nYour order has been successfully delivered.",
            color=Config.SUCCESS_COLOR
        )
        
        embed.add_field(name="Discord Server", value="[Join Server](https://discord.gg/NR4Z9zeBW2)", inline=False)
        embed.add_field(name="Instagram", value="[Instagram Link](https://www.instagram.com/imvu_trustedshop)", inline=False)
        embed.add_field(name="Order ID", value=order_id, inline=False)
        embed.add_field(name="Customer", value=f"<@{order.user.discord_id}>", inline=False)
        embed.add_field(name="Completed At", value=format_timestamp(get_eastern_time()), inline=False)
        embed.add_field(name="Status", value=f"{get_status_emoji('delivered')} DELIVERED", inline=False)
        
        embed.set_footer(text="BM Creations Support | Trusted Since 2020")
        
        if settings.order_channel_id:
            order_channel = self.bot.get_channel(settings.order_channel_id)
            if order_channel:
                await order_channel.send(embed=embed)
        
        await ctx.send(embed=embed)
        
        try:
            user = self.bot.get_user(order.user.discord_id)
            if user:
                await user.send(embed=embed)
        except:
            pass
    
    @commands.command(name="settracking")
    async def set_tracking(self, ctx: commands.Context, order_id: str, tracking_number: str):
        await ctx.message.delete()
        
        if not is_staff(ctx.author):
            await ctx.send("You don't have permission to use this command.", delete_after=5)
            return
        
        order = await db_service.update_order_status(
            order_id,
            OrderStatus.SHIPPED,
            tracking_number=tracking_number,
            staff_id=ctx.author.id
        )
        
        if not order:
            await ctx.send("Order not found.", delete_after=5)
            return
        
        embed = create_embed(
            title="Tracking Number Added",
            description=f"Order **{order_id}** has been shipped!",
            color=Config.SUCCESS_COLOR
        )
        
        embed.add_field(name="Tracking Number", value=tracking_number, inline=False)
        embed.add_field(name="Status", value=f"{get_status_emoji('shipped')} Shipped", inline=True)
        
        await ctx.send(embed=embed)
        
        try:
            user = self.bot.get_user(order.user.discord_id)
            if user:
                dm_embed = create_embed(
                    title=f"Your Order Has Shipped!",
                    description=f"Order **{order_id}** is on its way!",
                    color=Config.SUCCESS_COLOR
                )
                dm_embed.add_field(name="Tracking Number", value=tracking_number, inline=False)
                await user.send(embed=dm_embed)
        except:
            pass

async def setup(bot: commands.Bot):
    await bot.add_cog(OrdersCog(bot))
