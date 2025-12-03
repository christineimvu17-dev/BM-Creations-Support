import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime

from src.services.database import db_service
from src.models.database import OrderStatus
from src.utils.helpers import create_embed, is_staff, get_eastern_time, format_timestamp, get_status_emoji
from src.utils.translations import get_text
from src.config import Config

class ManualOrderCompletionView(discord.ui.View):
    def __init__(self, order_id: str, bot: commands.Bot, timeout: float = None):
        super().__init__(timeout=timeout)
        self.order_id = order_id
        self.bot = bot
    
    @discord.ui.button(label="Mark Completed", style=discord.ButtonStyle.success, emoji="✅", custom_id="manual_complete_order")
    async def complete_order(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        
        order = await db_service.update_order_status(
            self.order_id,
            OrderStatus.DELIVERED,
            staff_id=interaction.user.id
        )
        
        if not order:
            await interaction.followup.send("Order not found!", ephemeral=True)
            return
        
        for item in self.children:
            item.disabled = True
        
        try:
            await interaction.message.edit(view=self)
        except:
            pass
        
        completed_embed = create_embed(
            title="✅ Order Completed!",
            description="Thank you for shopping with **BM Creations Market!**\n\nYour order has been successfully delivered.",
            color=Config.SUCCESS_COLOR
        )
        
        completed_embed.add_field(name="🆔 Order ID", value=f"**{self.order_id}**", inline=True)
        completed_embed.add_field(name="📦 Status", value="✅ **COMPLETED**", inline=True)
        completed_embed.add_field(name="⏰ Completed At", value=format_timestamp(get_eastern_time()), inline=True)
        completed_embed.add_field(
            name="🌐 Connect With Us",
            value="**Website:** [Visit Us](https://imvublackmarket.xyz/)\n**Instagram:** [Follow Us](https://www.instagram.com/imvublackmarket_official?igsh=MXhsaXo4dzByeTg4ZA==)",
            inline=False
        )
        completed_embed.set_footer(text="BM Creations Market | Trusted Since 2020")
        
        await interaction.followup.send(embed=completed_embed)
        
        settings = await db_service.get_or_create_guild_settings(interaction.guild.id)
        if settings.order_channel_id:
            order_channel = self.bot.get_channel(settings.order_channel_id)
            if order_channel:
                status_embed = create_embed(
                    title="✅ Order Completed",
                    description=f"Order **{self.order_id}** has been marked as completed!",
                    color=Config.SUCCESS_COLOR
                )
                status_embed.add_field(name="Completed By", value=interaction.user.mention, inline=True)
                status_embed.add_field(name="Time", value=format_timestamp(get_eastern_time()), inline=True)
                await order_channel.send(embed=status_embed)
        
        try:
            user = self.bot.get_user(order.user.discord_id)
            if user:
                dm_embed = create_embed(
                    title="🎉 Your Order is Complete!",
                    description=f"Your order **{self.order_id}** has been delivered!\n\nThank you for choosing BM Creations Market!",
                    color=Config.SUCCESS_COLOR
                )
                await user.send(embed=dm_embed)
        except:
            pass
        
        self.stop()

class OrdersCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    @app_commands.command(name="newwork", description="Manually create a new order with BM ID (Owner only)")
    @app_commands.describe(
        customer="The customer to create the order for",
        product="Product name",
        notes="Optional notes about the order"
    )
    @app_commands.default_permissions(administrator=True)
    async def new_work(self, interaction: discord.Interaction, customer: discord.Member, product: str, notes: str = None):
        await interaction.response.defer()
        
        order_id = await db_service.generate_unique_bm_order_id()
        
        user = await db_service.get_or_create_user(
            discord_id=customer.id,
            guild_id=interaction.guild.id,
            username=str(customer),
            display_name=customer.display_name
        )
        
        order = await db_service.create_order(
            guild_id=interaction.guild.id,
            user_id=user.id,
            order_id=order_id,
            channel_id=interaction.channel.id,
            items=[{"name": product, "quantity": 1, "price": 0.0}],
            notes=notes or f"Product: {product}"
        )
        
        order_embed = create_embed(
            title="🎫 New Order Created",
            description=f"A new order has been created for {customer.mention}",
            color=Config.EMBED_COLOR
        )
        
        order_embed.add_field(name="🆔 Order ID", value=f"**{order_id}**", inline=True)
        order_embed.add_field(name="👤 Customer", value=customer.mention, inline=True)
        order_embed.add_field(name="📍 Channel", value=f"<#{interaction.channel.id}>", inline=True)
        order_embed.add_field(name="🛍️ Product", value=product, inline=True)
        order_embed.add_field(name="🕐 Created At", value=format_timestamp(get_eastern_time()), inline=True)
        order_embed.add_field(name="📦 Status", value="🟡 **IN PROGRESS**", inline=True)
        
        if notes:
            order_embed.add_field(name="📝 Notes", value=notes, inline=False)
        
        order_embed.set_footer(text="Click 'Mark Completed' when order is delivered")
        
        view = ManualOrderCompletionView(order_id, self.bot)
        await interaction.followup.send(embed=order_embed, view=view)
        
        settings = await db_service.get_or_create_guild_settings(interaction.guild.id)
        if settings.order_channel_id:
            order_channel = self.bot.get_channel(settings.order_channel_id)
            if order_channel:
                status_embed = create_embed(
                    title="🎫 New Order Received",
                    description=f"Order **{order_id}** has been created!",
                    color=Config.EMBED_COLOR
                )
                status_embed.add_field(name="🆔 Order ID", value=f"**{order_id}**", inline=True)
                status_embed.add_field(name="👤 Customer", value=str(customer), inline=True)
                status_embed.add_field(name="🛍️ Product", value=product, inline=True)
                status_embed.add_field(name="🕐 Time", value=format_timestamp(get_eastern_time()), inline=True)
                status_embed.add_field(name="📦 Status", value="🟡 **IN PROGRESS**", inline=True)
                status_embed.set_footer(text="Manual order created by owner")
                await order_channel.send(embed=status_embed)
    
    @app_commands.command(name="order", description="Create a new order")
    @app_commands.describe(details="Order details/description")
    async def create_order(self, interaction: discord.Interaction, details: str):
        await interaction.response.defer()
        
        user = await db_service.get_or_create_user(
            interaction.user.id, interaction.guild.id, str(interaction.user), interaction.user.display_name
        )
        
        ticket = await db_service.get_ticket(channel_id=interaction.channel.id)
        
        items = [{"name": details, "quantity": 1, "price": 0.0}]
        
        order = await db_service.create_order(
            guild_id=interaction.guild.id,
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
        embed.add_field(name="Customer", value=interaction.user.mention, inline=True)
        embed.add_field(name="Status", value=f"{get_status_emoji('pending')} Pending", inline=True)
        embed.add_field(name="Order Details", value=details, inline=False)
        embed.add_field(name="Created At", value=format_timestamp(get_eastern_time()), inline=False)
        
        embed.set_footer(text=f"Track your order with: /trackorder {order.order_id}")
        
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="trackorder", description="Track an order by ID")
    @app_commands.describe(order_id="The order ID to track")
    async def track_order(self, interaction: discord.Interaction, order_id: str):
        order = await db_service.get_order(order_id)
        
        if not order:
            await interaction.response.send_message("Order not found. Please check the order ID.", ephemeral=True)
            return
        
        if order.user.discord_id != interaction.user.id and not is_staff(interaction.user):
            await interaction.response.send_message("You don't have permission to view this order.", ephemeral=True)
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
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="myorders", description="View your orders")
    async def my_orders(self, interaction: discord.Interaction):
        orders = await db_service.get_user_orders(interaction.user.id, interaction.guild.id)
        
        if not orders:
            await interaction.response.send_message("You have no orders yet.", ephemeral=True)
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
        
        embed.set_footer(text="Use /trackorder <order_id> to track a specific order")
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="updateorder", description="Update an order status (Staff only)")
    @app_commands.describe(
        order_id="The order ID to update",
        status="New status for the order",
        notes="Optional notes about the update"
    )
    @app_commands.choices(status=[
        app_commands.Choice(name="Pending", value="pending"),
        app_commands.Choice(name="Confirmed", value="confirmed"),
        app_commands.Choice(name="Processing", value="processing"),
        app_commands.Choice(name="Shipped", value="shipped"),
        app_commands.Choice(name="Delivered", value="delivered"),
        app_commands.Choice(name="Cancelled", value="cancelled"),
        app_commands.Choice(name="Refunded", value="refunded"),
    ])
    @app_commands.default_permissions(manage_messages=True)
    async def update_order(self, interaction: discord.Interaction, order_id: str, status: str, notes: str = None):
        if not is_staff(interaction.user):
            await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
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
        
        await interaction.response.defer()
        
        order = await db_service.update_order_status(
            order_id, 
            status_map[status.lower()],
            staff_id=interaction.user.id
        )
        
        if not order:
            await interaction.followup.send("Order not found.", ephemeral=True)
            return
        
        embed = create_embed(
            title="Order Updated",
            description=f"Order **{order_id}** has been updated.",
            color=Config.SUCCESS_COLOR
        )
        
        embed.add_field(name="New Status", value=f"{get_status_emoji(status.lower())} {status.title()}", inline=True)
        embed.add_field(name="Updated By", value=interaction.user.mention, inline=True)
        
        if notes:
            embed.add_field(name="Notes", value=notes, inline=False)
        
        await interaction.followup.send(embed=embed)
        
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
    
    @app_commands.command(name="completeorder", description="Mark an order as complete/delivered (Staff only)")
    @app_commands.describe(order_id="The order ID to complete")
    @app_commands.default_permissions(manage_messages=True)
    async def complete_order(self, interaction: discord.Interaction, order_id: str):
        if not is_staff(interaction.user):
            await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        order = await db_service.update_order_status(
            order_id, 
            OrderStatus.DELIVERED,
            staff_id=interaction.user.id
        )
        
        if not order:
            await interaction.followup.send("Order not found.", ephemeral=True)
            return
        
        settings = await db_service.get_or_create_guild_settings(interaction.guild.id)
        
        embed = create_embed(
            title="Order Completed",
            description="Thank you for shopping with **BM Creations Market!**\nYour order has been successfully delivered.",
            color=Config.SUCCESS_COLOR
        )
        
        embed.add_field(name="Official Website", value="[Visit Us](https://imvublackmarket.xyz/)", inline=False)
        embed.add_field(name="Instagram", value="[Follow Us](https://www.instagram.com/imvublackmarket_official?igsh=MXhsaXo4dzByeTg4ZA==)", inline=False)
        embed.add_field(name="Order ID", value=order_id, inline=False)
        embed.add_field(name="Customer", value=f"<@{order.user.discord_id}>", inline=False)
        embed.add_field(name="Completed At", value=format_timestamp(get_eastern_time()), inline=False)
        embed.add_field(name="Status", value=f"{get_status_emoji('delivered')} DELIVERED", inline=False)
        
        embed.set_footer(text="BM Creations Support | Trusted Since 2020")
        
        if settings.order_channel_id:
            order_channel = self.bot.get_channel(settings.order_channel_id)
            if order_channel:
                await order_channel.send(embed=embed)
        
        await interaction.followup.send(embed=embed)
        
        try:
            user = self.bot.get_user(order.user.discord_id)
            if user:
                await user.send(embed=embed)
        except:
            pass
    
    @app_commands.command(name="settracking", description="Add tracking number to an order (Staff only)")
    @app_commands.describe(
        order_id="The order ID",
        tracking_number="The tracking number"
    )
    @app_commands.default_permissions(manage_messages=True)
    async def set_tracking(self, interaction: discord.Interaction, order_id: str, tracking_number: str):
        if not is_staff(interaction.user):
            await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        order = await db_service.update_order_status(
            order_id,
            OrderStatus.SHIPPED,
            tracking_number=tracking_number,
            staff_id=interaction.user.id
        )
        
        if not order:
            await interaction.followup.send("Order not found.", ephemeral=True)
            return
        
        embed = create_embed(
            title="Tracking Number Added",
            description=f"Order **{order_id}** has been shipped!",
            color=Config.SUCCESS_COLOR
        )
        
        embed.add_field(name="Tracking Number", value=tracking_number, inline=False)
        embed.add_field(name="Status", value=f"{get_status_emoji('shipped')} Shipped", inline=True)
        
        await interaction.followup.send(embed=embed)
        
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
