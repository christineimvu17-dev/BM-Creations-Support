import discord
from discord.ext import commands
from discord import app_commands, ui
from typing import Optional, Dict, Set
import asyncio
from datetime import datetime

from src.services.database import db_service
from src.models.database import TicketStatus
from src.utils.helpers import create_embed, is_staff, format_timestamp, get_eastern_time
from src.config import Config

suppressed_channels: Set[int] = set()
processed_threads: Set[int] = set()

IGNORED_CATEGORIES = ["chat zone", "more fun", "chatzone", "morefun"]
PURCHASE_KEYWORDS = [
    "buy", "purchase", "want to buy", "wanna buy", "buying", "i want",
    "how much", "price", "cost", "order", "get this", "interested",
    "can i get", "looking for", "need", "want this", "trigger", "room", "pose"
]

class ProductCategorySelect(ui.View):
    def __init__(self, user_id: int, channel_id: int, timeout: float = 300):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.channel_id = channel_id
        self.value = None
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This menu is not for you!", ephemeral=True)
            return False
        return True
    
    @ui.button(label="Triggers", style=discord.ButtonStyle.primary, emoji="🎮", custom_id="cat_triggers")
    async def triggers_button(self, interaction: discord.Interaction, button: ui.Button):
        self.value = "triggers"
        await self.ask_product_name(interaction, "Triggers")
    
    @ui.button(label="Rooms", style=discord.ButtonStyle.primary, emoji="🏠", custom_id="cat_rooms")
    async def rooms_button(self, interaction: discord.Interaction, button: ui.Button):
        self.value = "rooms"
        await self.ask_product_name(interaction, "Rooms")
    
    @ui.button(label="Poses", style=discord.ButtonStyle.primary, emoji="💃", custom_id="cat_poses")
    async def poses_button(self, interaction: discord.Interaction, button: ui.Button):
        self.value = "poses"
        await self.ask_product_name(interaction, "Poses")
    
    @ui.button(label="Other", style=discord.ButtonStyle.secondary, emoji="📦", custom_id="cat_other")
    async def other_button(self, interaction: discord.Interaction, button: ui.Button):
        self.value = "other"
        await self.ask_product_name(interaction, "Other Products")
    
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
        
        embed = create_embed(
            title=f"🛍️ {category}",
            description=f"Please type the **name** of the {category.lower()} product you want to purchase.\n\nFor example: `Night Club`, `Beach House`, `Dance Pose Pack`",
            color=Config.EMBED_COLOR
        )
        embed.set_footer(text="Type the product name below...")
        
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
        
        embed = create_embed(
            title="🛍️ What would you like to buy?",
            description="Please select a product category below:",
            color=Config.EMBED_COLOR
        )
        
        view = ProductCategorySelect(self.user_id, self.channel_id)
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
        
        keywords = {
            "price": "Our prices vary by product! What product are you interested in? I can check the price for you.",
            "cost": "Our prices vary by product! What product are you interested in? I can check the price for you.",
            "how much": "Our prices vary by product! Tell me which product you're looking at and I'll get the price for you.",
            "payment": "We accept PayPal payments! Once you tell me which product you want, I'll provide the PayPal link.",
            "paypal": "We accept PayPal payments! Just let me know which product you'd like to purchase.",
            "pay": "We accept PayPal payments! Which product are you interested in?",
            "delivery": "After payment confirmation, your product will be delivered to your IMVU account within 24 hours. Most orders are completed within a few hours!",
            "how long": "Delivery is usually within a few hours, maximum 24 hours after payment confirmation!",
            "when": "Your product will be delivered to your IMVU account after payment is confirmed. Usually within a few hours!",
            "refund": "For refund requests, please provide your order details and a staff member will review your case.",
            "cancel": "To cancel an order, please let us know immediately before delivery.",
            "help": "I'm here to help! What would you like to know about our products or services?",
            "hi": "Hello! Welcome to BM Creations! How can I help you today?",
            "hello": "Hello! Welcome to BM Creations! What can I do for you?",
            "hey": "Hey there! Welcome to BM Creations! How can I help?",
            "thanks": "You're welcome! Is there anything else I can help you with?",
            "thank you": "You're welcome! Let me know if you need anything else!",
            "trigger": "We have great triggers! Which trigger are you interested in? Tell me the name and I'll get the details.",
            "room": "We have amazing rooms! Which room are you looking for? I can check the price and details.",
            "pose": "We have beautiful poses! Which pose pack interests you?",
            "custom": "Yes, we offer custom work! Please describe what you'd like and staff will provide a quote.",
            "buy": "Great! What would you like to buy? Tell me the product name and I'll help you with the purchase!",
            "purchase": "Awesome! Which product would you like to purchase? I'll help you with the process!",
            "want": "What product are you interested in? Tell me and I'll get you the details!",
            "interested": "Great! Which product caught your eye? I can provide more information!",
        }
        
        for keyword, response in keywords.items():
            if keyword in message_lower:
                return response
        
        products = await db_service.search_products(guild_id, message)
        if products:
            product = products[0]
            price_text = f"${product.price:.2f}" if product.price else "Contact for price"
            return f"I found **{product.name}**!\n\n{product.description or 'A great product from BM Creations!'}\n\n**Price:** {price_text}\n\nWould you like to purchase this? Just confirm and I'll guide you through the payment!"
        
        return None
    
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
                embed = create_embed(
                    title="✅ Screenshot Received!",
                    description=f"Thank you! Staff will verify your payment and process your order.\n\n**Product:** {extra.get('product_purchased', 'Your order')}",
                    color=Config.SUCCESS_COLOR
                )
                await message.channel.send(embed=embed)
                
                extra["payment_proof_received"] = True
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
        
        embed = create_embed(
            title=f"🛍️ {product.name}",
            description=product.description or "A premium product from BM Creations!",
            color=Config.EMBED_COLOR,
            thumbnail_url=product.image_url if product.image_url else None
        )
        
        embed.add_field(name="💰 Price", value=price_text, inline=True)
        embed.add_field(name="📁 Category", value=product.category or "General", inline=True)
        
        paypal_link = settings.paypal_link or "Contact staff for payment link"
        
        embed.add_field(
            name="💳 Payment Link",
            value=f"[Click here to pay via PayPal]({paypal_link})" if paypal_link.startswith("http") else paypal_link,
            inline=False
        )
        
        embed.add_field(
            name="📋 How to Purchase",
            value=f"1. Click the PayPal link above\n2. Send **{price_text}** as payment\n3. Click 'I've Made Payment' button below\n4. Upload your payment screenshot\n5. Provide your IMVU username",
            inline=False
        )
        
        view = PaymentConfirmView(user.id, product.name)
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
