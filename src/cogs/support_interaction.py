import discord
from discord.ext import commands
from discord import ui
from typing import Optional, Dict, Set
import asyncio
from datetime import datetime

from src.services.database import db_service
from src.models.database import TicketStatus
from src.utils.helpers import create_embed, is_staff, format_timestamp, get_eastern_time
from src.config import Config

suppressed_channels: Set[int] = set()

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
    
    @ui.button(label="Triggers", style=discord.ButtonStyle.primary, emoji="", custom_id="cat_triggers")
    async def triggers_button(self, interaction: discord.Interaction, button: ui.Button):
        self.value = "triggers"
        await self.ask_product_name(interaction, "Triggers")
    
    @ui.button(label="Rooms", style=discord.ButtonStyle.primary, emoji="", custom_id="cat_rooms")
    async def rooms_button(self, interaction: discord.Interaction, button: ui.Button):
        self.value = "rooms"
        await self.ask_product_name(interaction, "Rooms")
    
    @ui.button(label="Poses", style=discord.ButtonStyle.primary, emoji="", custom_id="cat_poses")
    async def poses_button(self, interaction: discord.Interaction, button: ui.Button):
        self.value = "poses"
        await self.ask_product_name(interaction, "Poses")
    
    @ui.button(label="Other", style=discord.ButtonStyle.secondary, emoji="", custom_id="cat_other")
    async def other_button(self, interaction: discord.Interaction, button: ui.Button):
        self.value = "other"
        await self.ask_product_name(interaction, "Other Products")
    
    async def ask_product_name(self, interaction: discord.Interaction, category: str):
        for item in self.children:
            item.disabled = True
        await interaction.message.edit(view=self)
        
        ticket = await db_service.get_ticket(channel_id=self.channel_id)
        if ticket:
            extra = ticket.extra_data or {}
            extra["selected_category"] = self.value
            extra["awaiting_product_name"] = True
            await db_service.update_ticket_extra_data(ticket.ticket_id, extra)
        
        embed = create_embed(
            title=f" {category}",
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
    
    @ui.button(label="Buy Product", style=discord.ButtonStyle.success, emoji="", custom_id="buy_product")
    async def buy_product(self, interaction: discord.Interaction, button: ui.Button):
        for item in self.children:
            item.disabled = True
        await interaction.message.edit(view=self)
        
        embed = create_embed(
            title=" What would you like to buy?",
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
    
    @ui.button(label="Any Queries", style=discord.ButtonStyle.primary, emoji="", custom_id="any_queries")
    async def any_queries(self, interaction: discord.Interaction, button: ui.Button):
        for item in self.children:
            item.disabled = True
        await interaction.message.edit(view=self)
        
        embed = create_embed(
            title=" How can I help you?",
            description="Please describe your question or concern, and I'll do my best to assist you!\n\nYou can ask about:\n- Product information\n- Order status\n- Payment issues\n- Technical support\n- Anything else!",
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
    
    @ui.button(label="I've Made Payment", style=discord.ButtonStyle.success, emoji="", custom_id="payment_made")
    async def payment_made(self, interaction: discord.Interaction, button: ui.Button):
        for item in self.children:
            item.disabled = True
        await interaction.message.edit(view=self)
        
        embed = create_embed(
            title=" Payment Confirmation",
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
    
    @ui.button(label="Need Help with Payment", style=discord.ButtonStyle.secondary, emoji="", custom_id="payment_help")
    async def payment_help(self, interaction: discord.Interaction, button: ui.Button):
        embed = create_embed(
            title=" Payment Assistance",
            description="If you're having trouble with payment, here are some options:\n\n**PayPal Issues:**\n- Make sure you're logged into PayPal\n- Try using a different browser\n- Check if your payment method is valid\n\n**Alternative Payment:**\n- Contact staff for alternative payment options\n\nA staff member will assist you shortly!",
            color=Config.WARNING_COLOR
        )
        
        await interaction.response.send_message(embed=embed)

class SupportInteractionCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.product_await_users: Dict[int, Dict] = {}
    
    def is_founder_or_admin(self, member: discord.Member, settings) -> bool:
        founder_roles = settings.founder_role_ids or []
        admin_roles = settings.admin_role_ids or []
        
        for role in member.roles:
            if role.id in founder_roles or role.id in admin_roles:
                return True
            if role.name.lower() in ["founder", "admin", "owner", "administrator"]:
                return True
        
        return member.guild_permissions.administrator
    
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
            "price": "Our prices vary by product! Would you like to browse our catalog? Use the 'Buy Product' option or ask about a specific item.",
            "cost": "Our prices vary by product! Would you like to browse our catalog? Use the 'Buy Product' option or ask about a specific item.",
            "how much": "Our prices vary by product! Would you like to browse our catalog? Use the 'Buy Product' option or ask about a specific item.",
            "payment": "We accept PayPal payments! Once you select a product, I'll provide you with our PayPal link for secure payment.",
            "paypal": "We accept PayPal payments! Once you select a product, I'll provide you with our PayPal link for secure payment.",
            "pay": "We accept PayPal payments! Once you select a product, I'll provide you with our PayPal link for secure payment.",
            "delivery": "After payment confirmation, your product will be delivered to your IMVU account within 24 hours. Most orders are completed within a few hours!",
            "how long": "After payment confirmation, your product will be delivered to your IMVU account within 24 hours. Most orders are completed within a few hours!",
            "when": "After payment confirmation, your product will be delivered to your IMVU account within 24 hours. Most orders are completed within a few hours!",
            "refund": "For refund requests, please provide your order details and a staff member will review your case.",
            "cancel": "To cancel an order, please let us know immediately before delivery. If already delivered, we'll need to review the situation.",
            "help": "I'm here to help! You can ask me about products, prices, delivery, or any other questions. What would you like to know?",
            "hi": "Hello! Welcome to BM Creations! How can I assist you today?",
            "hello": "Hello! Welcome to BM Creations! How can I assist you today?",
            "hey": "Hey there! Welcome to BM Creations! How can I help you?",
            "thanks": "You're welcome! Is there anything else I can help you with?",
            "thank you": "You're welcome! Is there anything else I can help you with?",
            "trigger": "We have a great selection of triggers! Would you like to browse our trigger collection? Just tell me which trigger you're looking for.",
            "room": "We have amazing room designs! Would you like to see our room collection? Just tell me what type of room you're interested in.",
            "pose": "We have beautiful pose packs! Would you like to browse our poses? Just let me know what style you're looking for.",
            "custom": "Yes, we offer custom work! Please describe what you'd like customized and a staff member will provide a quote.",
        }
        
        for keyword, response in keywords.items():
            if keyword in message_lower:
                return response
        
        products = await db_service.search_products(guild_id, message)
        if products:
            product = products[0]
            price_text = f"${product.price:.2f}" if product.price else "Contact for price"
            return f"I found **{product.name}**! {product.description or ''}\n\nPrice: {price_text}\n\nWould you like to purchase this? Just confirm and I'll guide you through the payment process!"
        
        return None
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        
        await db_service.ensure_initialized()
        
        settings = await db_service.get_or_create_guild_settings(message.guild.id)
        
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
                        title=" Product Not Found",
                        description=f"I couldn't find an exact match for **{product_name}**.",
                        color=Config.WARNING_COLOR
                    )
                    
                    if similar:
                        suggestions = "\n".join([f"- {p.name}" for p in similar[:5]])
                        embed.add_field(
                            name="Did you mean one of these?",
                            value=suggestions,
                            inline=False
                        )
                        embed.set_footer(text="Please type the exact product name from the list above.")
                    else:
                        embed.add_field(
                            name="What to do?",
                            value="Please try a different name or ask a staff member for help with finding the right product.",
                            inline=False
                        )
                    
                    await message.channel.send(embed=embed)
                    return
                
                await db_service.update_ticket_extra_data(ticket.ticket_id, extra)
                return
            
            if extra.get("awaiting_query"):
                response = await self.generate_smart_response(message.content, message.guild.id)
                
                if response:
                    embed = create_embed(
                        title=" Here's what I found",
                        description=response,
                        color=Config.EMBED_COLOR
                    )
                    embed.set_footer(text="Need more help? A staff member will assist you shortly!")
                    await message.channel.send(embed=embed)
                else:
                    embed = create_embed(
                        title=" I'll get help for you",
                        description="I've noted your question. A staff member will respond to you shortly!\n\nIn the meantime, feel free to provide more details about your inquiry.",
                        color=Config.EMBED_COLOR
                    )
                    await message.channel.send(embed=embed)
                return
            
            if extra.get("awaiting_payment_proof"):
                if message.attachments:
                    embed = create_embed(
                        title=" Screenshot Received!",
                        description=f"Thank you for uploading your payment proof for **{extra.get('product_purchased', 'your product')}**!\n\nA staff member will verify your payment and process your order shortly.\n\n**What happens next:**\n1. Staff verifies payment\n2. Product is prepared\n3. Delivery to your account\n4. You receive confirmation",
                        color=Config.SUCCESS_COLOR
                    )
                    embed.set_footer(text="Please wait for staff confirmation.")
                    await message.channel.send(embed=embed)
                    
                    extra["payment_proof_received"] = True
                    await db_service.update_ticket_extra_data(ticket.ticket_id, extra)
                return
        
        if settings.support_channel_id and message.channel.id == settings.support_channel_id:
            response = await self.generate_smart_response(message.content, message.guild.id)
            
            if response:
                embed = create_embed(
                    title=" Support Response",
                    description=response,
                    color=Config.EMBED_COLOR
                )
                embed.set_footer(text="For personalized assistance, please create a ticket!")
                await message.reply(embed=embed, mention_author=False)
    
    async def send_product_details(self, channel: discord.TextChannel, product, user: discord.Member, settings):
        price_text = f"${product.price:.2f}" if product.price else "Contact for price"
        
        embed = create_embed(
            title=f" {product.name}",
            description=product.description or "A premium product from BM Creations!",
            color=Config.EMBED_COLOR,
            thumbnail_url=product.image_url if product.image_url else None
        )
        
        embed.add_field(name=" Price", value=price_text, inline=True)
        embed.add_field(name=" Category", value=product.category or "General", inline=True)
        
        if product.extra_data and product.extra_data.get("features"):
            embed.add_field(
                name=" Features",
                value=product.extra_data["features"],
                inline=False
            )
        
        paypal_link = settings.paypal_link or "Contact staff for payment link"
        
        embed.add_field(
            name=" Payment Link",
            value=f"[Click here to pay via PayPal]({paypal_link})" if paypal_link.startswith("http") else paypal_link,
            inline=False
        )
        
        embed.add_field(
            name=" How to Purchase",
            value=f"1. Click the PayPal link above\n2. Send **{price_text}** as payment\n3. Click 'I've Made Payment' button below\n4. Upload your payment screenshot\n5. Provide your IMVU username",
            inline=False
        )
        
        embed.set_footer(text="BM Creations | Quality Products")
        
        view = PaymentConfirmView(user.id, product.name)
        await channel.send(embed=embed, view=view)
    
    async def send_ticket_welcome(self, channel: discord.TextChannel, user: discord.Member):
        embed = create_embed(
            title=" Welcome to BM Creations Support!",
            description=f"Hello {user.mention}! Thank you for reaching out.\n\n**How can I help you today?**\n\nPlease select an option below to get started:",
            color=Config.EMBED_COLOR
        )
        
        embed.add_field(
            name=" Buy Product",
            value="Browse and purchase our amazing products",
            inline=True
        )
        
        embed.add_field(
            name=" Any Queries",
            value="Ask questions or get support",
            inline=True
        )
        
        embed.set_footer(text="BM Creations Support | We're here to help!")
        
        view = TicketWelcomeView(user.id, self.bot, channel.id)
        await channel.send(embed=embed, view=view)
    
    @commands.command(name="setsupportchannel")
    @commands.has_permissions(administrator=True)
    async def set_support_channel(self, ctx: commands.Context, channel: discord.TextChannel = None):
        channel = channel or ctx.channel
        
        await db_service.update_guild_settings(
            ctx.guild.id,
            support_channel_id=channel.id
        )
        
        embed = create_embed(
            title=" Support Channel Set",
            description=f"Auto-responses will now be active in {channel.mention}!\n\nThe bot will automatically answer questions in this channel.",
            color=Config.SUCCESS_COLOR
        )
        
        await ctx.send(embed=embed)
    
    @commands.command(name="setpaypal")
    @commands.has_permissions(administrator=True)
    async def set_paypal(self, ctx: commands.Context, *, link: str):
        try:
            await ctx.message.delete()
        except:
            pass
        
        await db_service.update_guild_settings(
            ctx.guild.id,
            paypal_link=link
        )
        
        embed = create_embed(
            title=" PayPal Link Updated",
            description="Your PayPal payment link has been saved and will be shown to customers during checkout.",
            color=Config.SUCCESS_COLOR
        )
        
        await ctx.send(embed=embed, delete_after=10)
    
    @commands.command(name="setfounderrole")
    @commands.has_permissions(administrator=True)
    async def set_founder_role(self, ctx: commands.Context, role: discord.Role):
        settings = await db_service.get_or_create_guild_settings(ctx.guild.id)
        founder_roles = settings.founder_role_ids or []
        
        if role.id not in founder_roles:
            founder_roles.append(role.id)
        
        await db_service.update_guild_settings(
            ctx.guild.id,
            founder_role_ids=founder_roles
        )
        
        embed = create_embed(
            title=" Founder Role Added",
            description=f"{role.mention} has been set as a Founder role.\n\nWhen someone with this role messages in a ticket, the bot will stop auto-responding.",
            color=Config.SUCCESS_COLOR
        )
        
        await ctx.send(embed=embed)
    
    @commands.command(name="setadminrole")
    @commands.has_permissions(administrator=True)
    async def set_admin_role(self, ctx: commands.Context, role: discord.Role):
        settings = await db_service.get_or_create_guild_settings(ctx.guild.id)
        admin_roles = settings.admin_role_ids or []
        
        if role.id not in admin_roles:
            admin_roles.append(role.id)
        
        await db_service.update_guild_settings(
            ctx.guild.id,
            admin_role_ids=admin_roles
        )
        
        embed = create_embed(
            title=" Admin Role Added",
            description=f"{role.mention} has been set as an Admin role.\n\nWhen someone with this role messages in a ticket, the bot will stop auto-responding.",
            color=Config.SUCCESS_COLOR
        )
        
        await ctx.send(embed=embed)
    
    @commands.command(name="resumebot")
    @commands.has_permissions(manage_channels=True)
    async def resume_bot(self, ctx: commands.Context):
        ticket = await db_service.get_ticket(channel_id=ctx.channel.id)
        
        if not ticket:
            await ctx.send("This command can only be used in ticket channels.", delete_after=5)
            return
        
        if ctx.channel.id in suppressed_channels:
            suppressed_channels.remove(ctx.channel.id)
        
        extra = ticket.extra_data or {}
        extra["staff_handling"] = False
        await db_service.update_ticket_extra_data(ticket.ticket_id, extra)
        
        embed = create_embed(
            title=" Bot Resumed",
            description="I'm back online in this ticket! I'll continue assisting the customer.",
            color=Config.SUCCESS_COLOR
        )
        
        await ctx.send(embed=embed)
    
    @commands.command(name="supportstatus")
    @commands.has_permissions(administrator=True)
    async def support_status(self, ctx: commands.Context):
        settings = await db_service.get_or_create_guild_settings(ctx.guild.id)
        
        embed = create_embed(
            title=" Support System Status",
            color=Config.EMBED_COLOR
        )
        
        support_channel = f"<#{settings.support_channel_id}>" if settings.support_channel_id else "Not set"
        embed.add_field(name="Support Channel", value=support_channel, inline=True)
        
        paypal_status = "" if settings.paypal_link else ""
        embed.add_field(name="PayPal Link", value=f"{paypal_status} {'Configured' if settings.paypal_link else 'Not set'}", inline=True)
        
        founder_count = len(settings.founder_role_ids or [])
        admin_count = len(settings.admin_role_ids or [])
        embed.add_field(name="Founder Roles", value=str(founder_count), inline=True)
        embed.add_field(name="Admin Roles", value=str(admin_count), inline=True)
        
        embed.add_field(name="Suppressed Channels", value=str(len(suppressed_channels)), inline=True)
        
        await ctx.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(SupportInteractionCog(bot))
