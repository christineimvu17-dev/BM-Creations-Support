import discord
from discord.ext import commands
from discord import app_commands, ui
from typing import Optional, Dict, Set
import asyncio
from datetime import datetime

from src.services.database import db_service
from src.models.database import TicketStatus, OrderStatus
from src.utils.helpers import create_embed, is_staff, format_timestamp, get_eastern_time, get_status_emoji
from src.config import Config

suppressed_channels: Set[int] = set()
processed_threads: Set[int] = set()
OWNER_USERNAMES = ["sizuka42"]

IGNORED_CATEGORIES = ["chat zone", "more fun", "chatzone", "morefun"]
PURCHASE_KEYWORDS = [
    "buy", "purchase", "want to buy", "wanna buy", "buying", "i want",
    "how much", "price", "cost", "order", "get this", "interested",
    "can i get", "looking for", "need", "want this", "trigger", "room", "pose"
]

def is_owner_user(user: discord.User) -> bool:
    username_lower = user.name.lower()
    for owner_name in OWNER_USERNAMES:
        if username_lower == owner_name.lower():
            return True
    return False

def blur_name(name: str) -> str:
    if len(name) <= 2:
        return name[0] + "*" * (len(name) - 1)
    return name[0] + "*" * (len(name) - 2) + name[-1]

class OrderTimelineView(ui.View):
    def __init__(self, order_id: str, bot: commands.Bot, customer_name: str = None, product_name: str = None, product_price: float = None, ticket_channel_id: int = None, timeout: float = None):
        super().__init__(timeout=timeout)
        self.order_id = order_id
        self.bot = bot
        self.customer_name = customer_name
        self.product_name = product_name
        self.product_price = product_price
        self.ticket_channel_id = ticket_channel_id
        self.current_stage = 1
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not is_owner_user(interaction.user):
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message(
                    "Only the owner can update order status!", 
                    ephemeral=True
                )
                return False
        return True
    
    def get_timeline_display(self, stage: int) -> str:
        stages = [
            ("Order Confirmed", "✅" if stage >= 1 else "⏳"),
            ("Payment Received", "✅" if stage >= 2 else "⏳"),
            ("Order Processing", "✅" if stage >= 3 else "⏳"),
            ("Completed", "✅" if stage >= 4 else "⏳"),
        ]
        
        lines = []
        for i, (name, status) in enumerate(stages, 1):
            if i < stage:
                lines.append(f"{status} ~~{name}~~")
            elif i == stage:
                lines.append(f"**{status} {name}** ← Current")
            else:
                lines.append(f"{status} {name}")
        
        return "\n".join(lines)
    
    @ui.button(label="Payment Received", style=discord.ButtonStyle.primary, emoji="💰", custom_id="payment_received", row=0)
    async def payment_received(self, interaction: discord.Interaction, button: ui.Button):
        self.current_stage = 2
        button.disabled = True
        try:
            await interaction.message.edit(view=self)
        except:
            pass
        
        embed = discord.Embed(
            title="💰 Payment Received",
            description=f"**Order:** {self.order_id}\n\n**Timeline:**\n{self.get_timeline_display(2)}",
            color=0x00ff00
        )
        embed.set_footer(text="BM Creations Support • Trusted since 2020")
        await interaction.response.send_message(embed=embed)
    
    @ui.button(label="Order Processing", style=discord.ButtonStyle.primary, emoji="⚙️", custom_id="order_processing", row=0)
    async def order_processing(self, interaction: discord.Interaction, button: ui.Button):
        self.current_stage = 3
        button.disabled = True
        for item in self.children:
            if hasattr(item, 'custom_id') and item.custom_id == 'payment_received':
                item.disabled = True
        try:
            await interaction.message.edit(view=self)
        except:
            pass
        
        embed = discord.Embed(
            title="⚙️ Order Processing",
            description=f"**Order:** {self.order_id}\n\n**Timeline:**\n{self.get_timeline_display(3)}",
            color=0xffa500
        )
        embed.set_footer(text="BM Creations Support • Trusted since 2020")
        await interaction.response.send_message(embed=embed)
    
    @ui.button(label="Mark Complete", style=discord.ButtonStyle.success, emoji="✅", custom_id="mark_complete", row=0)
    async def mark_complete(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()
        
        order = await db_service.update_order_status(
            self.order_id,
            OrderStatus.DELIVERED,
            staff_id=interaction.user.id
        )
        
        if not order:
            await interaction.followup.send("Order not found!", ephemeral=True)
            return
        
        self.current_stage = 4
        for item in self.children:
            if hasattr(item, 'disabled'):
                item.disabled = True
        
        try:
            await interaction.message.edit(view=self)
        except:
            pass
        
        completed_time = format_timestamp(get_eastern_time())
        blurred_customer = blur_name(self.customer_name) if self.customer_name else "Customer"
        hidden_order_id = f"||{self.order_id}||"
        hidden_ticket = f"||<#{self.ticket_channel_id}>||" if self.ticket_channel_id else "||Private||"
        
        ticket_embed = discord.Embed(
            title="🎉 𝐎𝐫𝐝𝐞𝐫 𝐂𝐨𝐦𝐩𝐥𝐞𝐭𝐞𝐝!",
            description=f"Thank you for shopping with **BM Creations Market!**\n\nYour order has been **successfully delivered**! 🚀",
            color=0x00ff00
        )
        ticket_embed.add_field(name="🆔 Order ID", value=hidden_order_id, inline=True)
        ticket_embed.add_field(name="👤 Customer", value=blurred_customer, inline=True)
        ticket_embed.add_field(name="📦 Status", value="✅ **COMPLETED**", inline=True)
        if self.product_name:
            ticket_embed.add_field(name="🛒 Product", value=self.product_name, inline=True)
        if self.product_price:
            ticket_embed.add_field(name="💰 Price", value=f"${self.product_price}", inline=True)
        ticket_embed.add_field(name="⏰ Completed At", value=completed_time, inline=True)
        ticket_embed.add_field(
            name="🌐 Connect With Us",
            value="🔗 **Website:** [imvublackmarket.xyz](https://imvublackmarket.xyz/)\n📸 **Instagram:** [@imvublackmarket_official](https://www.instagram.com/imvublackmarket_official)",
            inline=False
        )
        ticket_embed.add_field(name="📋 Ticket", value=hidden_ticket, inline=True)
        ticket_embed.set_footer(text="BM Creations Support • Trusted since 2020")
        
        await interaction.followup.send(embed=ticket_embed)
        
        settings = await db_service.get_or_create_guild_settings(interaction.guild.id)
        if settings.order_channel_id:
            order_channel = self.bot.get_channel(settings.order_channel_id)
            if order_channel:
                status_embed = discord.Embed(
                    title="✅ 𝐎𝐫𝐝𝐞𝐫 𝐃𝐞𝐥𝐢𝐯𝐞𝐫𝐞𝐝",
                    description=f"Order has been **successfully delivered!** 🎉",
                    color=0x00ff00
                )
                status_embed.add_field(name="🆔 Order ID", value=hidden_order_id, inline=True)
                status_embed.add_field(name="👤 Customer", value=blurred_customer, inline=True)
                status_embed.add_field(name="📦 Status", value="✅ **COMPLETED**", inline=True)
                if self.product_name:
                    status_embed.add_field(name="🛒 Product", value=self.product_name, inline=True)
                if self.product_price:
                    status_embed.add_field(name="💰 Price", value=f"${self.product_price}", inline=True)
                status_embed.add_field(name="⏰ Completed At", value=completed_time, inline=True)
                status_embed.add_field(name="✍️ Completed By", value=interaction.user.mention, inline=True)
                status_embed.add_field(name="📋 Ticket", value=hidden_ticket, inline=True)
                status_embed.add_field(
                    name="🌐 Connect With Us",
                    value="🔗 **Website:** [imvublackmarket.xyz](https://imvublackmarket.xyz/)\n📸 **Instagram:** [@imvublackmarket_official](https://www.instagram.com/imvublackmarket_official)",
                    inline=False
                )
                status_embed.set_footer(text="BM Creations Support • Trusted since 2020")
                await order_channel.send(embed=status_embed)
        
        try:
            user = self.bot.get_user(order.user.discord_id)
            if user:
                dm_embed = discord.Embed(
                    title="🎉 Your Order is Complete!",
                    description=f"Your order **{self.order_id}** has been **successfully delivered!** 🚀\n\nThank you for choosing **BM Creations Market!**",
                    color=0x00ff00
                )
                dm_embed.add_field(
                    name="🌐 Connect With Us",
                    value="🔗 **Website:** [imvublackmarket.xyz](https://imvublackmarket.xyz/)\n📸 **Instagram:** [@imvublackmarket_official](https://www.instagram.com/imvublackmarket_official)",
                    inline=False
                )
                dm_embed.set_footer(text="BM Creations Support • Trusted since 2020")
                await user.send(embed=dm_embed)
        except:
            pass
        
        try:
            if interaction.channel:
                current_name = interaction.channel.name
                if "-pending" in current_name:
                    new_name = current_name.replace("-pending", "-complete")
                    await interaction.channel.edit(name=new_name)
                elif "pending" in current_name:
                    new_name = current_name.replace("pending", "complete")
                    await interaction.channel.edit(name=new_name)
        except:
            pass
        
        self.stop()

class OrderCompletionView(ui.View):
    def __init__(self, order_id: str, bot: commands.Bot, customer_name: str = None, product_name: str = None, product_price: float = None, ticket_channel_id: int = None, timeout: float = None):
        super().__init__(timeout=timeout)
        self.order_id = order_id
        self.bot = bot
        self.customer_name = customer_name
        self.product_name = product_name
        self.product_price = product_price
        self.ticket_channel_id = ticket_channel_id
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not is_owner_user(interaction.user):
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message(
                    "Only the owner can complete orders!", 
                    ephemeral=True
                )
                return False
        return True
    
    @ui.button(label="Mark Completed", style=discord.ButtonStyle.success, emoji="✅", custom_id="complete_order")
    async def complete_order(self, interaction: discord.Interaction, button: ui.Button):
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
        
        completed_time = format_timestamp(get_eastern_time())
        blurred_customer = blur_name(self.customer_name) if self.customer_name else "Customer"
        hidden_order_id = f"||{self.order_id}||"
        hidden_ticket = f"||<#{self.ticket_channel_id}>||" if self.ticket_channel_id else "||Private||"
        
        ticket_embed = discord.Embed(
            title="🎉 𝐎𝐫𝐝𝐞𝐫 𝐂𝐨𝐦𝐩𝐥𝐞𝐭𝐞𝐝!",
            description=f"Thank you for shopping with **BM Creations Market!**\n\nYour order has been **successfully delivered**! 🚀",
            color=0x00ff00
        )
        ticket_embed.add_field(name="🆔 Order ID", value=hidden_order_id, inline=True)
        ticket_embed.add_field(name="👤 Customer", value=blurred_customer, inline=True)
        ticket_embed.add_field(name="📦 Status", value="✅ **COMPLETED**", inline=True)
        if self.product_name:
            ticket_embed.add_field(name="🛒 Product", value=self.product_name, inline=True)
        if self.product_price:
            ticket_embed.add_field(name="💰 Price", value=f"${self.product_price}", inline=True)
        ticket_embed.add_field(name="⏰ Completed At", value=completed_time, inline=True)
        ticket_embed.add_field(
            name="🌐 Connect With Us",
            value="🔗 **Website:** [imvublackmarket.xyz](https://imvublackmarket.xyz/)\n📸 **Instagram:** [@imvublackmarket_official](https://www.instagram.com/imvublackmarket_official)",
            inline=False
        )
        ticket_embed.add_field(name="📋 Ticket", value=hidden_ticket, inline=True)
        ticket_embed.set_footer(text="BM Creations Support • Trusted since 2020")
        
        await interaction.followup.send(embed=ticket_embed)
        
        settings = await db_service.get_or_create_guild_settings(interaction.guild.id)
        if settings.order_channel_id:
            order_channel = self.bot.get_channel(settings.order_channel_id)
            if order_channel:
                status_embed = discord.Embed(
                    title="✅ 𝐎𝐫𝐝𝐞𝐫 𝐃𝐞𝐥𝐢𝐯𝐞𝐫𝐞𝐝",
                    description=f"Order has been **successfully delivered!** 🎉",
                    color=0x00ff00
                )
                status_embed.add_field(name="🆔 Order ID", value=hidden_order_id, inline=True)
                status_embed.add_field(name="👤 Customer", value=blurred_customer, inline=True)
                status_embed.add_field(name="📦 Status", value="✅ **COMPLETED**", inline=True)
                if self.product_name:
                    status_embed.add_field(name="🛒 Product", value=self.product_name, inline=True)
                if self.product_price:
                    status_embed.add_field(name="💰 Price", value=f"${self.product_price}", inline=True)
                status_embed.add_field(name="⏰ Completed At", value=completed_time, inline=True)
                status_embed.add_field(name="✍️ Completed By", value=interaction.user.mention, inline=True)
                status_embed.add_field(name="📋 Ticket", value=hidden_ticket, inline=True)
                status_embed.add_field(
                    name="🌐 Connect With Us",
                    value="🔗 **Website:** [imvublackmarket.xyz](https://imvublackmarket.xyz/)\n📸 **Instagram:** [@imvublackmarket_official](https://www.instagram.com/imvublackmarket_official)",
                    inline=False
                )
                status_embed.set_footer(text="BM Creations Support • Trusted since 2020")
                await order_channel.send(embed=status_embed)
        
        try:
            user = self.bot.get_user(order.user.discord_id)
            if user:
                dm_embed = discord.Embed(
                    title="🎉 Your Order is Complete!",
                    description=f"Your order **{self.order_id}** has been **successfully delivered!** 🚀\n\nThank you for choosing **BM Creations Market!**",
                    color=0x00ff00
                )
                dm_embed.add_field(
                    name="🌐 Connect With Us",
                    value="🔗 **Website:** [imvublackmarket.xyz](https://imvublackmarket.xyz/)\n📸 **Instagram:** [@imvublackmarket_official](https://www.instagram.com/imvublackmarket_official)",
                    inline=False
                )
                dm_embed.set_footer(text="BM Creations Support • Trusted since 2020")
                await user.send(embed=dm_embed)
        except:
            pass
        
        try:
            if interaction.channel:
                current_name = interaction.channel.name
                if "-pending" in current_name:
                    new_name = current_name.replace("-pending", "-complete")
                    await interaction.channel.edit(name=new_name)
                elif "pending" in current_name:
                    new_name = current_name.replace("pending", "complete")
                    await interaction.channel.edit(name=new_name)
        except:
            pass
        
        self.stop()

PERMANENT_TRIGGER_PRODUCTS = [
    {"name": "King Cummy", "price": 35},
    {"name": "Venom3", "price": 50},
    {"name": "KingKong V4", "price": 40},
    {"name": "Private BBC V5", "price": 55},
    {"name": "King Cummy V8", "price": 50},
    {"name": "Female Trigger", "price": 60},
    {"name": "Red Venom", "price": 60},
]

GIFTING_TRIGGER_PRODUCTS = [
    {"name": "HD Kong", "price": 38},
    {"name": "BBC King Ultra", "price": 38},
]

class ProductButtonView(ui.View):
    def __init__(self, user_id: int, channel_id: int, product: dict, is_permanent: bool, paypal_link: str, bot: commands.Bot, timeout: float = 600):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.channel_id = channel_id
        self.product = product
        self.is_permanent = is_permanent
        self.paypal_link = paypal_link
        self.bot = bot
        
        if paypal_link and paypal_link.startswith("http"):
            self.add_item(ui.Button(
                label="PayPal",
                style=discord.ButtonStyle.link,
                emoji="💳",
                url=paypal_link,
                row=0
            ))
            self.add_item(ui.Button(
                label="Credit Card",
                style=discord.ButtonStyle.link,
                emoji="💵",
                url=paypal_link,
                row=0
            ))
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This menu is not for you!", ephemeral=True)
            return False
        return True
    
    @ui.button(label="I've Made Payment", style=discord.ButtonStyle.success, emoji="✅", custom_id="product_payment_made", row=1)
    async def payment_made(self, interaction: discord.Interaction, button: ui.Button):
        for item in self.children:
            if hasattr(item, 'disabled'):
                item.disabled = True
        try:
            await interaction.message.edit(view=self)
        except:
            pass
        
        embed = create_embed(
            title="✅ 𝐏𝐚𝐲𝐦𝐞𝐧𝐭 𝐂𝐨𝐧𝐟𝐢𝐫𝐦𝐚𝐭𝐢𝐨𝐧",
            description=f"Thank you for purchasing **{self.product['name']}**!\n\n"
                       f"**📸 Please send the following:**\n"
                       f"1️⃣ Screenshot of your PayPal payment\n"
                       f"2️⃣ Your **IMVU Username** (for delivery)\n\n"
                       f"**⏳ Your order will be processed shortly!**",
            color=Config.SUCCESS_COLOR
        )
        embed.set_footer(text="BM Creations Market | Upload your screenshot below")
        
        await interaction.response.send_message(embed=embed)
        
        ticket = await db_service.get_ticket(channel_id=self.channel_id)
        if ticket:
            extra = ticket.extra_data or {}
            extra["awaiting_payment_proof"] = True
            extra["product_purchased"] = self.product['name']
            extra["product_price"] = self.product['price']
            extra["is_permanent"] = self.is_permanent
            await db_service.update_ticket_extra_data(ticket.ticket_id, extra)
    
    @ui.button(label="Back to Products", style=discord.ButtonStyle.secondary, emoji="⬅️", custom_id="back_to_products", row=1)
    async def back_to_products(self, interaction: discord.Interaction, button: ui.Button):
        ticket = await db_service.get_ticket(channel_id=self.channel_id)
        if ticket and ticket.extra_data:
            category = ticket.extra_data.get("selected_category", "permanent_triggers")
            if category == "permanent_triggers":
                view = PermanentTriggersView(self.user_id, self.channel_id, self.paypal_link, self.bot)
                title = "🎯 Permanent Triggers"
            else:
                view = GiftingTriggersView(self.user_id, self.channel_id, self.paypal_link, self.bot)
                title = "🎁 Gifting Triggers"
            
            embed = create_embed(
                title=title,
                description="Select the product you want to purchase:",
                color=Config.EMBED_COLOR
            )
            await interaction.response.send_message(embed=embed, view=view)
        else:
            await interaction.response.send_message("Please start a new purchase.", ephemeral=True)

class PermanentTriggersView(ui.View):
    def __init__(self, user_id: int, channel_id: int, paypal_link: str, bot: commands.Bot, timeout: float = 600):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.channel_id = channel_id
        self.paypal_link = paypal_link
        self.bot = bot
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This menu is not for you!", ephemeral=True)
            return False
        return True
    
    async def show_product_detail(self, interaction: discord.Interaction, product: dict):
        for item in self.children:
            item.disabled = True
        try:
            await interaction.message.edit(view=self)
        except:
            pass
        
        ticket = await db_service.get_ticket(channel_id=self.channel_id)
        if ticket:
            extra = ticket.extra_data or {}
            extra["selected_product"] = product["name"]
            extra["product_price"] = product["price"]
            await db_service.update_ticket_extra_data(ticket.ticket_id, extra)
        
        embed = discord.Embed(
            title=f"🎯 {product['name']}",
            color=Config.EMBED_COLOR
        )
        embed.add_field(name="💰 Price", value=f"**${product['price']}**", inline=True)
        embed.add_field(name="⏳ Permanent", value="**Yes**", inline=True)
        embed.add_field(name="🔐 Login Required", value="Yes (for uploading)", inline=True)
        embed.add_field(name="🏠 Sex Room Required", value="**Yes**", inline=True)
        embed.add_field(name="📝 Note", value="Send screenshot after payment", inline=False)
        embed.set_footer(text="BM Creations Market | Trusted Since 2020")
        
        view = ProductButtonView(self.user_id, self.channel_id, product, True, self.paypal_link, self.bot)
        await interaction.response.send_message(embed=embed, view=view)
        self.stop()
    
    @ui.button(label="King Cummy - $35", style=discord.ButtonStyle.success, custom_id="perm_king_cummy", row=0)
    async def king_cummy(self, interaction: discord.Interaction, button: ui.Button):
        await self.show_product_detail(interaction, {"name": "King Cummy", "price": 35})
    
    @ui.button(label="Venom3 - $50", style=discord.ButtonStyle.success, custom_id="perm_venom3", row=0)
    async def venom3(self, interaction: discord.Interaction, button: ui.Button):
        await self.show_product_detail(interaction, {"name": "Venom3", "price": 50})
    
    @ui.button(label="KingKong V4 - $40", style=discord.ButtonStyle.success, custom_id="perm_kingkong_v4", row=0)
    async def kingkong_v4(self, interaction: discord.Interaction, button: ui.Button):
        await self.show_product_detail(interaction, {"name": "KingKong V4", "price": 40})
    
    @ui.button(label="Private BBC V5 - $55", style=discord.ButtonStyle.success, custom_id="perm_private_bbc_v5", row=1)
    async def private_bbc_v5(self, interaction: discord.Interaction, button: ui.Button):
        await self.show_product_detail(interaction, {"name": "Private BBC V5", "price": 55})
    
    @ui.button(label="King Cummy V8 - $50", style=discord.ButtonStyle.success, custom_id="perm_king_cummy_v8", row=1)
    async def king_cummy_v8(self, interaction: discord.Interaction, button: ui.Button):
        await self.show_product_detail(interaction, {"name": "King Cummy V8", "price": 50})
    
    @ui.button(label="Female Trigger - $60", style=discord.ButtonStyle.success, custom_id="perm_female_trigger", row=2)
    async def female_trigger(self, interaction: discord.Interaction, button: ui.Button):
        await self.show_product_detail(interaction, {"name": "Female Trigger", "price": 60})
    
    @ui.button(label="Red Venom - $60", style=discord.ButtonStyle.success, custom_id="perm_red_venom", row=2)
    async def red_venom(self, interaction: discord.Interaction, button: ui.Button):
        await self.show_product_detail(interaction, {"name": "Red Venom", "price": 60})
    
    @ui.button(label="⬅️ Back", style=discord.ButtonStyle.secondary, custom_id="perm_back", row=2)
    async def back_button(self, interaction: discord.Interaction, button: ui.Button):
        embed = create_embed(
            title="🛍️ What would you like to buy?",
            description="Please select a product category below:",
            color=Config.EMBED_COLOR
        )
        view = ProductCategorySelect(self.user_id, self.channel_id, self.paypal_link, self.bot)
        await interaction.response.send_message(embed=embed, view=view)
        self.stop()

class GiftingTriggersView(ui.View):
    def __init__(self, user_id: int, channel_id: int, paypal_link: str, bot: commands.Bot, timeout: float = 600):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.channel_id = channel_id
        self.paypal_link = paypal_link
        self.bot = bot
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This menu is not for you!", ephemeral=True)
            return False
        return True
    
    async def show_product_detail(self, interaction: discord.Interaction, product: dict):
        for item in self.children:
            item.disabled = True
        try:
            await interaction.message.edit(view=self)
        except:
            pass
        
        ticket = await db_service.get_ticket(channel_id=self.channel_id)
        if ticket:
            extra = ticket.extra_data or {}
            extra["selected_product"] = product["name"]
            extra["product_price"] = product["price"]
            await db_service.update_ticket_extra_data(ticket.ticket_id, extra)
        
        embed = discord.Embed(
            title=f"🎁 {product['name']}",
            color=Config.EMBED_COLOR
        )
        embed.add_field(name="💰 Price", value=f"**${product['price']}**", inline=True)
        embed.add_field(name="⏳ Permanent", value="**6 Months**", inline=True)
        embed.add_field(name="🔐 Login Required", value="Yes (for uploading)", inline=True)
        embed.add_field(name="🏠 Sex Room Required", value="**Yes**", inline=True)
        embed.add_field(name="📝 Note", value="Send screenshot after payment", inline=False)
        embed.set_footer(text="BM Creations Market | Trusted Since 2020")
        
        view = ProductButtonView(self.user_id, self.channel_id, product, False, self.paypal_link, self.bot)
        await interaction.response.send_message(embed=embed, view=view)
        self.stop()
    
    @ui.button(label="HD Kong - $38", style=discord.ButtonStyle.primary, custom_id="gift_hd_kong", row=0)
    async def hd_kong(self, interaction: discord.Interaction, button: ui.Button):
        await self.show_product_detail(interaction, {"name": "HD Kong", "price": 38})
    
    @ui.button(label="BBC King Ultra - $38", style=discord.ButtonStyle.primary, custom_id="gift_bbc_king_ultra", row=0)
    async def bbc_king_ultra(self, interaction: discord.Interaction, button: ui.Button):
        await self.show_product_detail(interaction, {"name": "BBC King Ultra", "price": 38})
    
    @ui.button(label="⬅️ Back", style=discord.ButtonStyle.secondary, custom_id="gift_back", row=0)
    async def back_button(self, interaction: discord.Interaction, button: ui.Button):
        embed = create_embed(
            title="🛍️ What would you like to buy?",
            description="Please select a product category below:",
            color=Config.EMBED_COLOR
        )
        view = ProductCategorySelect(self.user_id, self.channel_id, self.paypal_link, self.bot)
        await interaction.response.send_message(embed=embed, view=view)
        self.stop()

class ProductCategorySelect(ui.View):
    def __init__(self, user_id: int, channel_id: int, paypal_link: str = None, bot: commands.Bot = None, timeout: float = 300):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.channel_id = channel_id
        self.paypal_link = paypal_link or ""
        self.bot = bot
        self.value = None
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This menu is not for you!", ephemeral=True)
            return False
        return True
    
    @ui.button(label="Permanent Triggers", style=discord.ButtonStyle.success, emoji="🎯", custom_id="cat_permanent_triggers", row=0)
    async def permanent_triggers_button(self, interaction: discord.Interaction, button: ui.Button):
        self.value = "permanent_triggers"
        await self.show_products(interaction, "permanent_triggers")
    
    @ui.button(label="Gifting Triggers", style=discord.ButtonStyle.primary, emoji="🎁", custom_id="cat_gifting_triggers", row=0)
    async def gifting_triggers_button(self, interaction: discord.Interaction, button: ui.Button):
        self.value = "gifting_triggers"
        await self.show_products(interaction, "gifting_triggers")
    
    @ui.button(label="Rooms", style=discord.ButtonStyle.primary, emoji="🏠", custom_id="cat_rooms", row=1)
    async def rooms_button(self, interaction: discord.Interaction, button: ui.Button):
        self.value = "rooms"
        await self.ask_product_name(interaction, "Rooms")
    
    @ui.button(label="Long Sex Poses", style=discord.ButtonStyle.danger, emoji="💋", custom_id="cat_poses", row=1)
    async def poses_button(self, interaction: discord.Interaction, button: ui.Button):
        self.value = "long_sex_poses"
        await self.ask_product_name(interaction, "Long Sex Poses")
    
    async def show_products(self, interaction: discord.Interaction, category: str):
        for item in self.children:
            item.disabled = True
        try:
            await interaction.message.edit(view=self)
        except:
            pass
        
        ticket = await db_service.get_ticket(channel_id=self.channel_id)
        if ticket:
            extra = ticket.extra_data or {}
            extra["selected_category"] = category
            await db_service.update_ticket_extra_data(ticket.ticket_id, extra)
        
        settings = await db_service.get_or_create_guild_settings(interaction.guild.id)
        paypal_link = settings.paypal_link or self.paypal_link
        
        if category == "permanent_triggers":
            embed = create_embed(
                title="🎯 Permanent Triggers",
                description="Select the product you want to purchase:\n\n*All Permanent Triggers include lifetime warranty*",
                color=Config.EMBED_COLOR
            )
            view = PermanentTriggersView(self.user_id, self.channel_id, paypal_link, self.bot)
        else:
            embed = create_embed(
                title="🎁 Gifting Triggers",
                description="Select the product you want to purchase:\n\n*Gifting Triggers have a 6-month warranty*",
                color=Config.EMBED_COLOR
            )
            view = GiftingTriggersView(self.user_id, self.channel_id, paypal_link, self.bot)
        
        await interaction.response.send_message(embed=embed, view=view)
        self.stop()
    
    async def ask_product_name(self, interaction: discord.Interaction, category: str):
        for item in self.children:
            item.disabled = True
        try:
            await interaction.message.edit(view=self)
        except:
            pass
        
        ticket = await db_service.get_ticket(channel_id=self.channel_id)
        if ticket:
            extra = ticket.extra_data or {}
            extra["selected_category"] = self.value
            extra["awaiting_product_name"] = True
            await db_service.update_ticket_extra_data(ticket.ticket_id, extra)
        
        examples = {
            "Rooms": "Bedroom, Lounge, Pool Party",
            "Long Sex Poses": "Romantic Pack, Couples Edition, Premium Bundle"
        }
        
        embed = create_embed(
            title=f"🛒 {category}",
            description=f"**Type the product name you want to purchase:**\n\n💡 **Examples:** `{examples.get(category, 'Product Name')}`",
            color=Config.EMBED_COLOR
        )
        embed.set_footer(text="BM Creations Market | Type product name below...")
        
        await interaction.response.send_message(embed=embed)
        self.stop()

class TicketWelcomeView(ui.View):
    def __init__(self, user_id: int, bot: commands.Bot, channel_id: int, timeout: float = None):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.bot = bot
        self.channel_id = channel_id
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This menu is not for you!", ephemeral=True)
            return False
        return True
    
    @ui.button(label="Buy Product", style=discord.ButtonStyle.success, emoji="🛒", custom_id="buy_product")
    async def buy_product(self, interaction: discord.Interaction, button: ui.Button):
        for item in self.children:
            item.disabled = True
        try:
            await interaction.message.edit(view=self)
        except:
            pass
        
        settings = await db_service.get_or_create_guild_settings(interaction.guild.id)
        paypal_link = settings.paypal_link or ""
        
        embed = create_embed(
            title="🛍️ What would you like to buy?",
            description="Please select a product category below:",
            color=Config.EMBED_COLOR
        )
        
        view = ProductCategorySelect(self.user_id, self.channel_id, paypal_link, self.bot)
        await interaction.response.send_message(embed=embed, view=view)
        
        ticket = await db_service.get_ticket(channel_id=self.channel_id)
        if ticket:
            extra = ticket.extra_data or {}
            extra["flow"] = "buy_product"
            await db_service.update_ticket_extra_data(ticket.ticket_id, extra)
    
    @ui.button(label="Any Queries", style=discord.ButtonStyle.primary, emoji="❓", custom_id="any_queries")
    async def any_queries(self, interaction: discord.Interaction, button: ui.Button):
        for item in self.children:
            item.disabled = True
        try:
            await interaction.message.edit(view=self)
        except:
            pass
        
        embed = create_embed(
            title="💬 How can I help you?",
            description="Please describe your question or concern, and I'll do my best to assist you!\n\nYou can ask about:\n• Product information\n• Order status\n• Payment issues\n• Technical support\n• Anything else!",
            color=Config.EMBED_COLOR
        )
        
        await interaction.response.send_message(embed=embed)
        
        ticket = await db_service.get_ticket(channel_id=self.channel_id)
        if ticket:
            extra = ticket.extra_data or {}
            extra["flow"] = "queries"
            extra["awaiting_query"] = True
            await db_service.update_ticket_extra_data(ticket.ticket_id, extra)
    
    @ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="close_ticket", row=1)
    async def close_ticket(self, interaction: discord.Interaction, button: ui.Button):
        ticket = await db_service.get_ticket(channel_id=self.channel_id)
        
        if not ticket:
            await interaction.response.send_message("This is not a ticket channel.", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        await db_service.update_ticket_status(ticket.ticket_id, TicketStatus.CLOSED)
        
        embed = create_embed(
            title="🔒 Ticket Closed",
            description=f"This ticket has been closed by {interaction.user.mention}\n\n**Thank you for using BM Creations Market!**",
            color=Config.WARNING_COLOR
        )
        embed.add_field(name="Ticket ID", value=ticket.ticket_id, inline=True)
        embed.add_field(name="Closed At", value=format_timestamp(get_eastern_time()), inline=True)
        
        await interaction.followup.send(embed=embed)
        
        await interaction.channel.send("This channel will be deleted in 10 seconds...")
        
        import asyncio
        await asyncio.sleep(10)
        
        try:
            await interaction.channel.delete(reason="Ticket closed by user")
        except:
            pass

class PaymentConfirmView(ui.View):
    def __init__(self, user_id: int, product_name: str, timeout: float = 600):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.product_name = product_name
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This menu is not for you!", ephemeral=True)
            return False
        return True
    
    @ui.button(label="I've Made Payment", style=discord.ButtonStyle.success, emoji="✅", custom_id="payment_made")
    async def payment_made(self, interaction: discord.Interaction, button: ui.Button):
        for item in self.children:
            item.disabled = True
        try:
            await interaction.message.edit(view=self)
        except:
            pass
        
        embed = create_embed(
            title="✅ Payment Confirmation",
            description=f"Thank you for your purchase of **{self.product_name}**!\n\nPlease send the following in this channel:\n\n**1.** Screenshot of your PayPal payment confirmation\n**2.** Your IMVU username (for delivery)\n**3.** Any specific customization requests\n\nA staff member will process your order and deliver your product shortly!",
            color=Config.SUCCESS_COLOR
        )
        embed.set_footer(text="Please wait for staff confirmation after uploading your details.")
        
        await interaction.response.send_message(embed=embed)
        
        ticket = await db_service.get_ticket(channel_id=interaction.channel.id)
        if ticket:
            extra = ticket.extra_data or {}
            extra["awaiting_payment_proof"] = True
            extra["product_purchased"] = self.product_name
            await db_service.update_ticket_extra_data(ticket.ticket_id, extra)
    
    @ui.button(label="Need Help with Payment", style=discord.ButtonStyle.secondary, emoji="🆘", custom_id="payment_help")
    async def payment_help(self, interaction: discord.Interaction, button: ui.Button):
        embed = create_embed(
            title="🆘 Payment Assistance",
            description="If you're having trouble with payment, here are some options:\n\n**PayPal Issues:**\n• Make sure you're logged into PayPal\n• Try using a different browser\n• Check if your payment method is valid\n\n**Alternative Payment:**\n• Contact staff for alternative payment options\n\nA staff member will assist you shortly!",
            color=Config.WARNING_COLOR
        )
        
        await interaction.response.send_message(embed=embed)

class PaymentButtonsView(ui.View):
    def __init__(self, user_id: int, product_name: str, paypal_link: str, timeout: float = 600):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.product_name = product_name
        self.paypal_link = paypal_link
        
        if paypal_link and paypal_link.startswith("http"):
            self.add_item(ui.Button(
                label="PayPal",
                style=discord.ButtonStyle.link,
                emoji="💳",
                url=paypal_link
            ))
            self.add_item(ui.Button(
                label="Credit Card",
                style=discord.ButtonStyle.link,
                emoji="💵",
                url=paypal_link
            ))
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This menu is not for you!", ephemeral=True)
            return False
        return True
    
    @ui.button(label="I've Made Payment", style=discord.ButtonStyle.success, emoji="✅", custom_id="payment_confirm", row=1)
    async def payment_confirm(self, interaction: discord.Interaction, button: ui.Button):
        for item in self.children:
            if hasattr(item, 'disabled'):
                item.disabled = True
        try:
            await interaction.message.edit(view=self)
        except:
            pass
        
        embed = create_embed(
            title="✅ 𝐏𝐚𝐲𝐦𝐞𝐧𝐭 𝐂𝐨𝐧𝐟𝐢𝐫𝐦𝐚𝐭𝐢𝐨𝐧",
            description=f"Thank you for purchasing **{self.product_name}**!\n\n"
                       f"**📸 Please send the following:**\n"
                       f"1️⃣ Screenshot of your PayPal payment\n"
                       f"2️⃣ Your **IMVU Username** (for delivery)\n"
                       f"3️⃣ Any customization requests\n\n"
                       f"**Staff will process your order shortly!**",
            color=Config.SUCCESS_COLOR
        )
        embed.set_footer(text="BM Creations Market | Upload your screenshot below")
        
        await interaction.response.send_message(embed=embed)
        
        ticket = await db_service.get_ticket(channel_id=interaction.channel.id)
        if ticket:
            extra = ticket.extra_data or {}
            extra["awaiting_payment_proof"] = True
            extra["product_purchased"] = self.product_name
            await db_service.update_ticket_extra_data(ticket.ticket_id, extra)
    
    @ui.button(label="Need Help", style=discord.ButtonStyle.secondary, emoji="❓", custom_id="payment_need_help", row=1)
    async def need_help(self, interaction: discord.Interaction, button: ui.Button):
        embed = create_embed(
            title="🆘 𝐏𝐚𝐲𝐦𝐞𝐧𝐭 𝐇𝐞𝐥𝐩",
            description="**Having trouble with payment?**\n\n"
                       "💡 **Tips:**\n"
                       "• Make sure you're logged into PayPal\n"
                       "• Try a different browser\n"
                       "• Check your payment method\n\n"
                       "**Staff will assist you shortly!**",
            color=Config.WARNING_COLOR
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

class SupportInteractionCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.product_await_users: Dict[int, Dict] = {}
        self.owner_username = "sizuka42"
    
    def is_owner(self, member: discord.Member) -> bool:
        username_lower = member.name.lower()
        display_lower = member.display_name.lower() if member.display_name else ""
        return (self.owner_username in username_lower or 
                self.owner_username in display_lower or
                "sizuka" in username_lower or
                "sizuka" in display_lower)
    
    def is_founder_or_admin(self, member: discord.Member, settings) -> bool:
        if self.is_owner(member):
            return True
            
        founder_roles = settings.founder_role_ids or []
        admin_roles = settings.admin_role_ids or []
        
        for role in member.roles:
            if role.id in founder_roles or role.id in admin_roles:
                return True
            if role.name.lower() in ["founder", "admin", "owner", "administrator"]:
                return True
        
        return member.guild_permissions.administrator
    
    def is_in_ignored_category(self, channel: discord.TextChannel) -> bool:
        if hasattr(channel, 'category') and channel.category:
            category_name = channel.category.name.lower()
            for ignored in IGNORED_CATEGORIES:
                if ignored in category_name:
                    return True
        return False
    
    def has_purchase_intent(self, message: str) -> bool:
        message_lower = message.lower()
        for keyword in PURCHASE_KEYWORDS:
            if keyword in message_lower:
                return True
        return False
    
    async def search_product_by_name(self, guild_id: int, product_name: str):
        products = await db_service.search_products(guild_id, product_name)
        if products:
            return products[0]
        
        all_products = await db_service.get_all_products(guild_id)
        product_name_lower = product_name.lower()
        
        for product in all_products:
            if product_name_lower in product.name.lower() or product.name.lower() in product_name_lower:
                return product
        
        return None
    
    async def generate_smart_response(self, message: str, guild_id: int) -> Optional[str]:
        message_lower = message.lower()
        
        faqs = await db_service.search_faqs(guild_id, message)
        if faqs:
            return faqs[0].answer
        
        products = await db_service.search_products(guild_id, message)
        if products:
            product = products[0]
            price_text = f"${product.price:.2f}" if product.price else "Contact for price"
            is_trigger = "trigger" in (product.category or "").lower()
            
            response = f"✨ **{product.name}**\n\n"
            response += f"{product.description or 'Premium product from BM Creations!'}\n\n"
            response += f"💰 **Price:** {price_text}\n"
            response += f"🛡️ **Warranty:** Permanent\n"
            response += f"👑 **VIP:** Onetime Platinum VIP\n"
            if is_trigger:
                response += f"🏠 **Note:** Private Room Needed\n"
            response += f"\n**Click 'Buy Product' above to purchase!**"
            return response
        
        keywords = {
            "price": "💰 Our prices vary by product! Which product are you interested in? Tell me the name and I'll check the price for you.",
            "cost": "💰 Our prices vary by product! Which product are you looking for? I can get the exact price.",
            "how much": "💰 Prices depend on the product! Tell me which one you're looking at and I'll get the price.",
            "payment": "💳 We accept **PayPal** and **Credit Card** payments! Which product would you like to purchase?",
            "paypal": "💳 Yes, we accept PayPal! Just tell me which product you want and I'll provide the payment link.",
            "pay": "💳 We accept PayPal payments! Which product are you interested in?",
            "delivery": "📦 After payment confirmation, your product will be delivered within **24 hours**. Most orders are completed within a few hours!",
            "how long": "⏰ Delivery is usually within a few hours, maximum **24 hours** after payment confirmation!",
            "when": "⏰ Your product will be delivered after payment is confirmed. Usually within a few hours!",
            "refund": "💵 For refund requests, please provide your order ID and a staff member will review your case.",
            "cancel": "❌ To cancel an order, please let us know immediately before delivery with your order ID.",
            "warranty": "🛡️ All our products come with **Permanent Warranty**! You're covered forever.",
            "vip": "👑 All purchases include **Onetime Platinum VIP** access!",
            "private room": "🏠 Triggers require a **Private Room** in IMVU. Make sure you have one before purchase!",
            "help": "🤝 I'm here to help! What would you like to know about our products?",
            "hi": "👋 Hello! Welcome to **BM Creations Market**! How can I help you today?",
            "hello": "👋 Hello! Welcome to **BM Creations**! What can I do for you?",
            "hey": "👋 Hey there! Welcome to **BM Creations**! How can I help?",
            "thanks": "😊 You're welcome! Is there anything else I can help you with?",
            "thank you": "😊 You're welcome! Let me know if you need anything else!",
            "trigger": "🎯 We have amazing triggers! **Permanent Triggers** and **Gifting Triggers**. Which one interests you?",
            "room": "🏠 We have beautiful rooms! Which room are you looking for? Tell me the name!",
            "pose": "💋 We have great **Long Sex Poses**! Which pose pack interests you?",
            "custom": "🎨 Yes, we offer custom work! Please describe what you'd like and staff will provide a quote.",
            "buy": "🛒 Great! Tell me the **product name** and I'll help you with the purchase!",
            "purchase": "🛒 Awesome! Which product would you like to purchase? I'll guide you through!",
            "want": "🛍️ Which product are you interested in? Tell me the name and I'll get you the details!",
            "interested": "✨ Great! Which product caught your eye? I can provide more information!",
            "categories": "📋 We have:\n• **Permanent Triggers** 🎯\n• **Gifting Triggers** 🎁\n• **Rooms** 🏠\n• **Long Sex Poses** 💋\n\nWhich category interests you?",
            "what do you sell": "🛍️ We sell:\n• **Permanent Triggers** 🎯\n• **Gifting Triggers** 🎁\n• **Rooms** 🏠\n• **Long Sex Poses** 💋\n\nAll with Permanent Warranty & Platinum VIP!",
            "products": "🛍️ Our products include:\n• **Permanent Triggers** 🎯\n• **Gifting Triggers** 🎁\n• **Rooms** 🏠\n• **Long Sex Poses** 💋\n\nTell me what you're looking for!",
        }
        
        for keyword, response in keywords.items():
            if keyword in message_lower:
                return response
        
        return "🤔 I'm not sure about that, but a **staff member** will be with you shortly to help!\n\nIn the meantime, tell me which **product** you're interested in and I can provide details."
    
    async def create_ticket_for_user(self, channel, user: discord.Member, subject: str = "Product Inquiry"):
        try:
            db_user = await db_service.get_or_create_user(
                discord_id=user.id,
                guild_id=channel.guild.id,
                username=str(user),
                display_name=user.display_name
            )
            
            ticket = await db_service.create_ticket(
                user_id=db_user.id,
                guild_id=channel.guild.id,
                channel_id=channel.id,
                subject=subject,
                extra_data={"auto_created": True, "channel_name": channel.name}
            )
            
            return ticket
        except Exception as e:
            print(f"Error creating ticket: {e}")
            return None
    
    @commands.Cog.listener()
    async def on_thread_create(self, thread: discord.Thread):
        if thread.id in processed_threads:
            return
        
        processed_threads.add(thread.id)
        
        if self.is_in_ignored_category(thread.parent):
            return
        
        await asyncio.sleep(1)
        
        try:
            await db_service.ensure_initialized()
            
            owner = thread.owner
            if not owner:
                try:
                    owner = await thread.guild.fetch_member(thread.owner_id)
                except:
                    return
            
            if owner.bot:
                return
            
            settings = await db_service.get_or_create_guild_settings(thread.guild.id)
            
            if self.is_founder_or_admin(owner, settings):
                return
            
            user = await db_service.get_or_create_user(
                discord_id=owner.id,
                guild_id=thread.guild.id,
                username=str(owner),
                display_name=owner.display_name
            )
            
            ticket = await db_service.create_ticket(
                user_id=user.id,
                guild_id=thread.guild.id,
                channel_id=thread.id,
                subject=thread.name or "Thread Support",
                extra_data={"thread_ticket": True, "thread_name": thread.name}
            )
            
            embed = create_embed(
                title="👋 Welcome to BM Creations Support!",
                description=f"Hello {owner.mention}!\n\n**Staff is coming to you shortly!**\n\nUntil then, I'm here to help you. Just type your question and I'll answer!\n\nOr select an option below:",
                color=Config.EMBED_COLOR
            )
            
            embed.add_field(name="🛒 Buy Product", value="Browse and purchase products", inline=True)
            embed.add_field(name="❓ Any Queries", value="Ask questions or get support", inline=True)
            embed.set_footer(text="BM Creations Support | Staff will be with you soon!")
            
            view = TicketWelcomeView(owner.id, self.bot, thread.id)
            await thread.send(embed=embed, view=view)
            
            print(f"Auto-ticket created for thread: {thread.name} by {owner}")
            
        except Exception as e:
            print(f"Error creating auto-ticket for thread: {e}")
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        
        await db_service.ensure_initialized()
        
        settings = await db_service.get_or_create_guild_settings(message.guild.id)
        
        if self.is_in_ignored_category(message.channel):
            return
        
        if message.channel.id in suppressed_channels:
            return
        
        if self.is_founder_or_admin(message.author, settings):
            ticket = await db_service.get_ticket(channel_id=message.channel.id)
            if ticket:
                suppressed_channels.add(message.channel.id)
                extra = ticket.extra_data or {}
                extra["staff_handling"] = True
                extra["staff_id"] = message.author.id
                await db_service.update_ticket_extra_data(ticket.ticket_id, extra)
            return
        
        ticket = await db_service.get_ticket(channel_id=message.channel.id)
        if ticket:
            await self.handle_ticket_message(message, ticket, settings)
            return
        
        is_support_desk = (settings.support_channel_id and 
                          message.channel.id == settings.support_channel_id)
        
        is_products_channel = (settings.products_channel_id and 
                              message.channel.id == settings.products_channel_id)
        
        is_general_chat = (settings.general_chat_id and 
                          message.channel.id == settings.general_chat_id)
        
        channel_name = message.channel.name.lower()
        is_support_by_name = any(x in channel_name for x in ["support", "help", "desk"])
        is_products_by_name = any(x in channel_name for x in ["product", "catalog", "shop", "store"])
        is_general_by_name = "general" in channel_name
        
        if is_support_desk or is_support_by_name:
            await self.handle_support_desk_message(message, settings)
            return
        
        if is_products_channel or is_products_by_name:
            await self.handle_products_channel_message(message, settings)
            return
        
        if is_general_chat or is_general_by_name:
            if self.has_purchase_intent(message.content):
                await self.handle_purchase_intent_message(message, settings)
            return
    
    async def handle_ticket_message(self, message: discord.Message, ticket, settings):
        extra = ticket.extra_data or {}
        
        if extra.get("awaiting_product_name"):
            product_name = message.content.strip()
            product = await self.search_product_by_name(message.guild.id, product_name)
            
            if product:
                await self.send_product_details(message.channel, product, message.author, settings)
                extra["awaiting_product_name"] = False
                extra["selected_product"] = product.name
            else:
                similar = await db_service.search_products(message.guild.id, product_name)
                
                embed = create_embed(
                    title="🔍 Product Not Found",
                    description=f"I couldn't find **{product_name}**.",
                    color=Config.WARNING_COLOR
                )
                
                if similar:
                    suggestions = "\n".join([f"• {p.name}" for p in similar[:5]])
                    embed.add_field(name="Did you mean?", value=suggestions, inline=False)
                else:
                    embed.add_field(name="What to do?", value="Please try a different name or wait for staff to help!", inline=False)
                
                await message.channel.send(embed=embed)
                return
            
            await db_service.update_ticket_extra_data(ticket.ticket_id, extra)
            return
        
        if extra.get("awaiting_query") or extra.get("thread_ticket") or extra.get("auto_created"):
            response = await self.generate_smart_response(message.content, message.guild.id)
            
            if response:
                embed = create_embed(
                    title="💡 Here's what I found",
                    description=response,
                    color=Config.EMBED_COLOR
                )
                embed.set_footer(text="Staff will be with you shortly!")
                await message.channel.send(embed=embed)
            else:
                embed = create_embed(
                    title="📝 Got it!",
                    description="I've noted your message. A staff member will respond shortly!\n\nFeel free to add more details.",
                    color=Config.EMBED_COLOR
                )
                await message.channel.send(embed=embed)
            return
        
        if extra.get("awaiting_payment_proof"):
            if message.attachments:
                product_name = extra.get('product_purchased', 'Product')
                product_price = extra.get('product_price', 0)
                is_permanent = extra.get('is_permanent', True)
                customer_imvu = extra.get('customer_imvu', '')
                order_id = await db_service.generate_unique_bm_order_id()
                
                user = await db_service.get_or_create_user(
                    discord_id=message.author.id,
                    guild_id=message.guild.id,
                    username=str(message.author),
                    display_name=message.author.display_name
                )
                
                order = await db_service.create_order(
                    guild_id=message.guild.id,
                    user_id=user.id,
                    ticket_id=ticket.id if ticket else None,
                    order_id=order_id,
                    channel_id=message.channel.id,
                    items=[{"name": product_name, "quantity": 1, "price": float(product_price) if product_price else 0.0}],
                    notes=f"Product: {product_name} | IMVU: {customer_imvu}"
                )
                
                blurred_customer = blur_name(message.author.display_name)
                warranty = "Permanent" if is_permanent else "6 Months"
                
                timeline_display = "✅ **Order Confirmed** ← Current\n⏳ Payment Received\n⏳ Order Processing\n⏳ Completed"
                
                order_embed = discord.Embed(
                    title="🎫 𝐍𝐞𝐰 𝐎𝐫𝐝𝐞𝐫 𝐂𝐫𝐞𝐚𝐭𝐞𝐝",
                    description=f"A new order has been placed!",
                    color=Config.EMBED_COLOR
                )
                
                order_embed.add_field(name="🆔 Order ID", value=f"**{order_id}**", inline=True)
                order_embed.add_field(name="👤 Customer", value=f"||{blurred_customer}||", inline=True)
                order_embed.add_field(name="📍 Ticket", value=f"||<#{message.channel.id}>||", inline=True)
                order_embed.add_field(name="🛍️ Product", value=product_name, inline=True)
                if product_price:
                    order_embed.add_field(name="💰 Price", value=f"${product_price}", inline=True)
                order_embed.add_field(name="⏳ Warranty", value=warranty, inline=True)
                if customer_imvu:
                    order_embed.add_field(name="🎮 IMVU", value=customer_imvu, inline=True)
                order_embed.add_field(name="🕐 Created At", value=format_timestamp(get_eastern_time()), inline=True)
                order_embed.add_field(name="📦 Status", value="🟡 **ORDER CONFIRMED**", inline=True)
                order_embed.add_field(name="📊 Timeline", value=timeline_display, inline=False)
                order_embed.set_footer(text="BM Creations Support • Trusted since 2020")
                
                if message.attachments:
                    order_embed.set_image(url=message.attachments[0].url)
                
                view = OrderTimelineView(
                    order_id, 
                    self.bot, 
                    customer_name=message.author.display_name,
                    product_name=product_name,
                    product_price=product_price,
                    ticket_channel_id=message.channel.id
                )
                order_msg = await message.channel.send(embed=order_embed, view=view)
                
                settings = await db_service.get_or_create_guild_settings(message.guild.id)
                if settings.order_channel_id:
                    order_channel = self.bot.get_channel(settings.order_channel_id)
                    if order_channel:
                        status_embed = discord.Embed(
                            title="🎫 𝐍𝐞𝐰 𝐎𝐫𝐝𝐞𝐫 𝐑𝐞𝐜𝐞𝐢𝐯𝐞𝐝",
                            description=f"Order **{order_id}** has been created!",
                            color=Config.EMBED_COLOR
                        )
                        status_embed.add_field(name="🆔 Order ID", value=f"**{order_id}**", inline=True)
                        status_embed.add_field(name="👤 Customer", value=f"||{blurred_customer}||", inline=True)
                        status_embed.add_field(name="📍 Ticket", value=f"||<#{message.channel.id}>||", inline=True)
                        status_embed.add_field(name="🛍️ Product", value=product_name, inline=True)
                        if product_price:
                            status_embed.add_field(name="💰 Price", value=f"${product_price}", inline=True)
                        status_embed.add_field(name="⏳ Warranty", value=warranty, inline=True)
                        status_embed.add_field(name="🕐 Time", value=format_timestamp(get_eastern_time()), inline=True)
                        status_embed.add_field(name="📦 Status", value="🟡 **ORDER CONFIRMED**", inline=True)
                        if message.attachments:
                            status_embed.set_image(url=message.attachments[0].url)
                        status_embed.set_footer(text="BM Creations Support • Trusted since 2020")
                        await order_channel.send(embed=status_embed)
                
                extra["payment_proof_received"] = True
                extra["order_id"] = order_id
                await db_service.update_ticket_extra_data(ticket.ticket_id, extra)
            else:
                imvu_keywords = ["imvu", "username", "@", "my name", "deliver to"]
                message_lower = message.content.lower()
                
                if any(kw in message_lower for kw in imvu_keywords):
                    embed = create_embed(
                        title="📝 IMVU Username Received",
                        description=f"Got it! **{message.content}**\n\nNow please upload a screenshot of your PayPal payment.",
                        color=Config.EMBED_COLOR
                    )
                    extra["customer_imvu"] = message.content
                    await db_service.update_ticket_extra_data(ticket.ticket_id, extra)
                else:
                    embed = create_embed(
                        title="📝 Info Received",
                        description="Thanks! Please also upload a screenshot of your payment.",
                        color=Config.EMBED_COLOR
                    )
                await message.channel.send(embed=embed)
            return
    
    async def handle_support_desk_message(self, message: discord.Message, settings):
        response = await self.generate_smart_response(message.content, message.guild.id)
        
        if response:
            embed = create_embed(
                title="💬 Support Response",
                description=response,
                color=Config.EMBED_COLOR
            )
            embed.set_footer(text="Need more help? Create a thread for personalized support!")
            await message.reply(embed=embed, mention_author=False)
        else:
            embed = create_embed(
                title="📝 Message Received",
                description="Thanks for your message! A staff member will help you soon.\n\n**Tip:** Create a thread for faster, personalized support!",
                color=Config.EMBED_COLOR
            )
            await message.reply(embed=embed, mention_author=False)
    
    async def handle_products_channel_message(self, message: discord.Message, settings):
        ticket = await self.create_ticket_for_user(message.channel, message.author, "Product Inquiry")
        
        if ticket:
            embed = create_embed(
                title="👋 Hi there!",
                description=f"Hello {message.author.mention}! I see you're interested in our products.\n\n**Staff is coming to help you shortly!**\n\nUntil then, tell me what you're looking for and I'll try to help!",
                color=Config.EMBED_COLOR
            )
            view = TicketWelcomeView(message.author.id, self.bot, message.channel.id)
            await message.reply(embed=embed, view=view, mention_author=False)
        else:
            response = await self.generate_smart_response(message.content, message.guild.id)
            if response:
                embed = create_embed(
                    title="💬 Product Info",
                    description=response,
                    color=Config.EMBED_COLOR
                )
                await message.reply(embed=embed, mention_author=False)
    
    async def handle_purchase_intent_message(self, message: discord.Message, settings):
        response = await self.generate_smart_response(message.content, message.guild.id)
        
        if response:
            embed = create_embed(
                title="🛒 Interested in buying?",
                description=response + "\n\n**Tip:** Create a thread for faster, personalized purchase assistance!",
                color=Config.EMBED_COLOR
            )
            await message.reply(embed=embed, mention_author=False)
    
    async def send_product_details(self, channel, product, user: discord.Member, settings):
        price_text = f"${product.price:.2f}" if product.price else "Contact for price"
        paypal_link = settings.paypal_link or "https://paypal.me/"
        
        is_trigger = "trigger" in (product.category or "").lower()
        
        embed = create_embed(
            title=f"✨ {product.name}",
            description=product.description or "**Premium product from BM Creations Market!**",
            color=Config.EMBED_COLOR,
            thumbnail_url=product.image_url if product.image_url else None
        )
        
        embed.add_field(name="💰 𝐏𝐫𝐢𝐜𝐞", value=f"**{price_text}**", inline=True)
        embed.add_field(name="📁 𝐂𝐚𝐭𝐞𝐠𝐨𝐫𝐲", value=product.category or "General", inline=True)
        embed.add_field(name="🛡️ 𝐖𝐚𝐫𝐫𝐚𝐧𝐭𝐲", value="**Permanent**", inline=True)
        embed.add_field(name="👑 𝐕𝐈𝐏", value="**Onetime Platinum VIP**", inline=True)
        
        if is_trigger:
            embed.add_field(name="🏠 𝐍𝐨𝐭𝐞", value="⚠️ **Private Room Needed**", inline=True)
        
        embed.add_field(
            name="━━━━━━━━━━━━━━━━━━━━━━",
            value="**📋 𝐇𝐨𝐰 𝐭𝐨 𝐏𝐮𝐫𝐜𝐡𝐚𝐬𝐞:**\n"
                  f"1️⃣ Click **PayPal** or **Credit Card** below\n"
                  f"2️⃣ Send **{price_text}** as payment\n"
                  f"3️⃣ Click **I've Made Payment** button\n"
                  f"4️⃣ Upload payment screenshot\n"
                  f"5️⃣ Provide your **IMVU Username**",
            inline=False
        )
        
        embed.set_footer(text="BM Creations Market | Trusted Since 2020")
        
        view = PaymentButtonsView(user.id, product.name, paypal_link)
        await channel.send(embed=embed, view=view)
    
    async def send_ticket_welcome(self, channel, user: discord.Member):
        embed = create_embed(
            title="👋 Welcome to BM Creations Support!",
            description=f"Hello {user.mention}!\n\n**Staff is coming to you shortly!**\n\nUntil then, I'm here to help. Select an option below or just type your question!",
            color=Config.EMBED_COLOR
        )
        
        embed.add_field(name="🛒 Buy Product", value="Browse and purchase products", inline=True)
        embed.add_field(name="❓ Any Queries", value="Ask questions or get support", inline=True)
        embed.set_footer(text="BM Creations Support | We're here to help!")
        
        view = TicketWelcomeView(user.id, self.bot, channel.id)
        await channel.send(embed=embed, view=view)
    
    @app_commands.command(name="setsupportchannel", description="Set the support desk channel (Admin)")
    @app_commands.describe(channel="The channel for support messages")
    @app_commands.default_permissions(administrator=True)
    async def set_support_channel(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        channel = channel or interaction.channel
        
        await db_service.update_guild_settings(
            interaction.guild.id,
            support_channel_id=channel.id
        )
        
        embed = create_embed(
            title="✅ Support Desk Channel Set",
            description=f"Support desk is now {channel.mention}\n\nBot will automatically reply to ALL messages in this channel!",
            color=Config.SUCCESS_COLOR
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="setproductschannel", description="Set the products channel (Admin)")
    @app_commands.describe(channel="The products channel - creates ticket when users message")
    @app_commands.default_permissions(administrator=True)
    async def set_products_channel(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        channel = channel or interaction.channel
        
        await db_service.update_guild_settings(
            interaction.guild.id,
            products_channel_id=channel.id
        )
        
        embed = create_embed(
            title="✅ Products Channel Set",
            description=f"Products channel is now {channel.mention}\n\nWhen users message here, bot will create a ticket and help them!",
            color=Config.SUCCESS_COLOR
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="setgeneralchat", description="Set the general chat channel (Admin)")
    @app_commands.describe(channel="General chat - bot only replies to purchase messages")
    @app_commands.default_permissions(administrator=True)
    async def set_general_chat(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        channel = channel or interaction.channel
        
        await db_service.update_guild_settings(
            interaction.guild.id,
            general_chat_id=channel.id
        )
        
        embed = create_embed(
            title="✅ General Chat Set",
            description=f"General chat is now {channel.mention}\n\nBot will only reply to purchase-related messages here!",
            color=Config.SUCCESS_COLOR
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="setpaypal", description="Set your PayPal payment link (Admin)")
    @app_commands.describe(link="Your PayPal.me or payment link")
    @app_commands.default_permissions(administrator=True)
    async def set_paypal(self, interaction: discord.Interaction, link: str):
        await db_service.update_guild_settings(
            interaction.guild.id,
            paypal_link=link
        )
        
        embed = create_embed(
            title="✅ PayPal Link Updated",
            description="Your PayPal payment link has been saved!",
            color=Config.SUCCESS_COLOR
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="setfounderrole", description="Add a Founder role (Admin)")
    @app_commands.describe(role="The Founder role - bot stops responding when they message")
    @app_commands.default_permissions(administrator=True)
    async def set_founder_role(self, interaction: discord.Interaction, role: discord.Role):
        settings = await db_service.get_or_create_guild_settings(interaction.guild.id)
        founder_roles = settings.founder_role_ids or []
        
        if role.id not in founder_roles:
            founder_roles.append(role.id)
        
        await db_service.update_guild_settings(
            interaction.guild.id,
            founder_role_ids=founder_roles
        )
        
        embed = create_embed(
            title="✅ Founder Role Added",
            description=f"{role.mention} is now a Founder role.\n\nBot stops auto-responding when Founders message in tickets!",
            color=Config.SUCCESS_COLOR
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="setadminrole", description="Add an Admin role (Admin)")
    @app_commands.describe(role="The Admin role - bot stops responding when they message")
    @app_commands.default_permissions(administrator=True)
    async def set_admin_role(self, interaction: discord.Interaction, role: discord.Role):
        settings = await db_service.get_or_create_guild_settings(interaction.guild.id)
        admin_roles = settings.admin_role_ids or []
        
        if role.id not in admin_roles:
            admin_roles.append(role.id)
        
        await db_service.update_guild_settings(
            interaction.guild.id,
            admin_role_ids=admin_roles
        )
        
        embed = create_embed(
            title="✅ Admin Role Added",
            description=f"{role.mention} is now an Admin role.\n\nBot stops auto-responding when Admins message in tickets!",
            color=Config.SUCCESS_COLOR
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="resumebot", description="Resume bot responses in this ticket (Staff)")
    @app_commands.default_permissions(manage_channels=True)
    async def resume_bot(self, interaction: discord.Interaction):
        ticket = await db_service.get_ticket(channel_id=interaction.channel.id)
        
        if not ticket:
            await interaction.response.send_message("This command can only be used in ticket channels.", ephemeral=True)
            return
        
        if interaction.channel.id in suppressed_channels:
            suppressed_channels.remove(interaction.channel.id)
        
        extra = ticket.extra_data or {}
        extra["staff_handling"] = False
        await db_service.update_ticket_extra_data(ticket.ticket_id, extra)
        
        embed = create_embed(
            title="🤖 Bot Resumed",
            description="I'm back online! I'll continue helping the customer.",
            color=Config.SUCCESS_COLOR
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="supportstatus", description="View support system configuration (Admin)")
    @app_commands.default_permissions(administrator=True)
    async def support_status(self, interaction: discord.Interaction):
        settings = await db_service.get_or_create_guild_settings(interaction.guild.id)
        
        embed = create_embed(
            title="⚙️ Support System Status",
            color=Config.EMBED_COLOR
        )
        
        support_ch = f"<#{settings.support_channel_id}>" if settings.support_channel_id else "Not set (auto-detects 'support')"
        products_ch = f"<#{settings.products_channel_id}>" if settings.products_channel_id else "Not set (auto-detects 'product')"
        general_ch = f"<#{settings.general_chat_id}>" if settings.general_chat_id else "Not set (auto-detects 'general')"
        
        embed.add_field(name="💬 Support Desk", value=support_ch, inline=True)
        embed.add_field(name="🛍️ Products Channel", value=products_ch, inline=True)
        embed.add_field(name="💭 General Chat", value=general_ch, inline=True)
        
        paypal_status = "✅ Configured" if settings.paypal_link else "❌ Not set"
        embed.add_field(name="💳 PayPal Link", value=paypal_status, inline=True)
        
        founder_count = len(settings.founder_role_ids or [])
        admin_count = len(settings.admin_role_ids or [])
        embed.add_field(name="👑 Founder Roles", value=str(founder_count), inline=True)
        embed.add_field(name="⚡ Admin Roles", value=str(admin_count), inline=True)
        
        embed.add_field(name="🔇 Suppressed Tickets", value=str(len(suppressed_channels)), inline=True)
        embed.add_field(name="🧵 Thread Tickets", value=str(len(processed_threads)), inline=True)
        
        embed.add_field(
            name="📋 Channel Rules",
            value="• **Support Desk:** Reply to ALL messages\n• **Products:** Create ticket + welcome\n• **General:** Only purchase messages\n• **Chat Zone/More Fun:** Ignored",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(SupportInteractionCog(bot))
