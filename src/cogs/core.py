import discord
from discord.ext import commands
from discord import app_commands
from src.services.database import db_service
from src.utils.helpers import create_embed, is_staff
from src.utils.translations import get_text
from src.config import Config

class CoreCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    @commands.Cog.listener()
    async def on_ready(self):
        print(f"{self.bot.user} is now online and ready!")
        try:
            await db_service.initialize()
            print("Database initialized successfully!")
        except Exception as e:
            print(f"Database initialization error (will retry on first use): {e}")
    
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        await db_service.get_or_create_user(
            discord_id=member.id,
            guild_id=member.guild.id,
            username=str(member),
            display_name=member.display_name
        )
        
        settings = await db_service.get_or_create_guild_settings(member.guild.id)
        if settings.welcome_channel_id:
            channel = self.bot.get_channel(settings.welcome_channel_id)
            if channel:
                user = await db_service.get_or_create_user(member.id, member.guild.id)
                lang = user.language if user else "en"
                
                welcome_msg = settings.welcome_message or get_text("welcome_message", lang, user=member.mention, server=member.guild.name)
                
                embed = create_embed(
                    title=get_text("welcome_title", lang, server=member.guild.name),
                    description=welcome_msg,
                    color=Config.SUCCESS_COLOR,
                    thumbnail_url=member.display_avatar.url if member.display_avatar else None
                )
                embed.add_field(name="Member Count", value=f"You are member #{member.guild.member_count}!", inline=False)
                
                await channel.send(embed=embed)
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        
        if message.guild:
            user = await db_service.get_or_create_user(
                discord_id=message.author.id,
                guild_id=message.guild.id,
                username=str(message.author),
                display_name=message.author.display_name
            )
            
            await db_service.log_interaction(
                user_id=user.id,
                guild_id=message.guild.id,
                interaction_type="message",
                channel_id=message.channel.id,
                content=message.content[:500] if message.content else None
            )
    
    @commands.command(name="ping")
    async def ping(self, ctx: commands.Context):
        latency = round(self.bot.latency * 1000)
        embed = create_embed(
            title="Pong!",
            description=f"Bot latency: **{latency}ms**",
            color=Config.EMBED_COLOR
        )
        await ctx.send(embed=embed)
    
    @commands.command(name="help")
    async def help_command(self, ctx: commands.Context):
        user = await db_service.get_or_create_user(ctx.author.id, ctx.guild.id)
        lang = user.language if user else "en"
        
        embed = create_embed(
            title=get_text("help_title", lang),
            description="Here are all available commands:",
            color=Config.EMBED_COLOR
        )
        
        embed.add_field(
            name="General Commands",
            value="""
`!ping` - Check bot latency
`!help` - Show this help message
`!setlanguage <lang>` - Set your preferred language
`!profile` - View your profile
            """,
            inline=False
        )
        
        embed.add_field(
            name="Ticket Commands",
            value="""
`!newticket <subject>` - Create a new ticket
`!closeticket` - Close current ticket
`!viewtickets` - View all active tickets (Staff)
            """,
            inline=False
        )
        
        embed.add_field(
            name="Order Commands",
            value="""
`!order <details>` - Create a new order
`!trackorder <order_id>` - Track an order
`!myorders` - View your orders
`!completeorder <order_id>` - Complete an order (Staff)
            """,
            inline=False
        )
        
        embed.add_field(
            name="Shopping Commands",
            value="""
`!cart` - View your cart
`!addtocart <product>` - Add item to cart
`!clearcart` - Clear your cart
`!wishlist` - View your wishlist
`!addtowishlist <product>` - Add item to wishlist
            """,
            inline=False
        )
        
        embed.add_field(
            name="FAQ & Info",
            value="""
`!faq` - View FAQ list
`!ask <question>` - Ask a question
`!products` - View available products
`!search <term>` - Search products
            """,
            inline=False
        )
        
        embed.add_field(
            name="Moderation (Staff)",
            value="""
`!warn <user> <reason>` - Warn a user
`!warnings <user>` - View user warnings
`!announce <message>` - Send announcement
`!stats` - View server statistics
            """,
            inline=False
        )
        
        embed.add_field(
            name="Reminders",
            value="""
`!remind <time> <message>` - Set a reminder
`!feedback <message>` - Submit feedback
            """,
            inline=False
        )
        
        embed.set_footer(text="BM Creations Support Bot")
        await ctx.send(embed=embed)
    
    @commands.command(name="setlanguage")
    async def set_language(self, ctx: commands.Context, language: str):
        supported = Config.SUPPORTED_LANGUAGES
        
        if language.lower() not in supported:
            await ctx.send(f"Supported languages: {', '.join(supported)}")
            return
        
        await db_service.set_user_language(ctx.author.id, ctx.guild.id, language.lower())
        
        embed = create_embed(
            title="Language Updated",
            description=get_text("language_changed", language.lower()),
            color=Config.SUCCESS_COLOR
        )
        await ctx.send(embed=embed)
    
    @commands.command(name="profile")
    async def profile(self, ctx: commands.Context, member: discord.Member = None):
        target = member or ctx.author
        user = await db_service.get_or_create_user(target.id, ctx.guild.id, str(target), target.display_name)
        history = await db_service.get_user_history(target.id, ctx.guild.id)
        
        embed = create_embed(
            title=f"Profile: {target.display_name}",
            color=Config.EMBED_COLOR,
            thumbnail_url=target.display_avatar.url if target.display_avatar else None
        )
        
        embed.add_field(name="Language", value=user.language.upper(), inline=True)
        embed.add_field(name="Total Orders", value=str(user.total_orders), inline=True)
        embed.add_field(name="Total Spent", value=f"${user.total_spent:.2f}", inline=True)
        embed.add_field(name="VIP Status", value="Yes" if user.is_vip else "No", inline=True)
        embed.add_field(name="Member Since", value=user.joined_at.strftime("%b %d, %Y"), inline=True)
        embed.add_field(name="Last Active", value=user.last_active.strftime("%b %d, %Y"), inline=True)
        
        if history.get("orders"):
            embed.add_field(name="Recent Orders", value=str(len(history["orders"])), inline=True)
        
        await ctx.send(embed=embed)
    
    @commands.command(name="serverinfo")
    async def server_info(self, ctx: commands.Context):
        guild = ctx.guild
        
        embed = create_embed(
            title=f"Server Info: {guild.name}",
            color=Config.EMBED_COLOR,
            thumbnail_url=guild.icon.url if guild.icon else None
        )
        
        embed.add_field(name="Owner", value=guild.owner.mention if guild.owner else "Unknown", inline=True)
        embed.add_field(name="Members", value=str(guild.member_count), inline=True)
        embed.add_field(name="Channels", value=str(len(guild.channels)), inline=True)
        embed.add_field(name="Roles", value=str(len(guild.roles)), inline=True)
        embed.add_field(name="Created", value=guild.created_at.strftime("%b %d, %Y"), inline=True)
        embed.add_field(name="Boost Level", value=str(guild.premium_tier), inline=True)
        
        await ctx.send(embed=embed)
    
    @commands.command(name="setup")
    @commands.has_permissions(administrator=True)
    async def setup_command(self, ctx: commands.Context):
        settings = await db_service.get_or_create_guild_settings(ctx.guild.id)
        
        embed = create_embed(
            title="Bot Setup",
            description="Configure the bot settings for your server.",
            color=Config.EMBED_COLOR
        )
        
        embed.add_field(
            name="Current Settings",
            value=f"""
Welcome Channel: {f'<#{settings.welcome_channel_id}>' if settings.welcome_channel_id else 'Not set'}
Order Channel: {f'<#{settings.order_channel_id}>' if settings.order_channel_id else 'Not set'}
Ticket Category: {f'<#{settings.ticket_category_id}>' if settings.ticket_category_id else 'Not set'}
Log Channel: {f'<#{settings.log_channel_id}>' if settings.log_channel_id else 'Not set'}
            """,
            inline=False
        )
        
        embed.add_field(
            name="Setup Commands",
            value="""
`!setwelcome #channel` - Set welcome channel
`!setorders #channel` - Set order status channel
`!settickets #category` - Set ticket category
`!setlogs #channel` - Set log channel
`!setwelcomemsg <message>` - Set welcome message
            """,
            inline=False
        )
        
        await ctx.send(embed=embed)
    
    @commands.command(name="setwelcome")
    @commands.has_permissions(administrator=True)
    async def set_welcome_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        await db_service.update_guild_settings(ctx.guild.id, welcome_channel_id=channel.id)
        await ctx.send(f"Welcome channel set to {channel.mention}")
    
    @commands.command(name="setorders")
    @commands.has_permissions(administrator=True)
    async def set_orders_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        await db_service.update_guild_settings(ctx.guild.id, order_channel_id=channel.id)
        await ctx.send(f"Order status channel set to {channel.mention}")
    
    @commands.command(name="settickets")
    @commands.has_permissions(administrator=True)
    async def set_tickets_category(self, ctx: commands.Context, category: discord.CategoryChannel):
        await db_service.update_guild_settings(ctx.guild.id, ticket_category_id=category.id)
        await ctx.send(f"Ticket category set to {category.name}")
    
    @commands.command(name="setlogs")
    @commands.has_permissions(administrator=True)
    async def set_logs_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        await db_service.update_guild_settings(ctx.guild.id, log_channel_id=channel.id)
        await ctx.send(f"Log channel set to {channel.mention}")
    
    @commands.command(name="setwelcomemsg")
    @commands.has_permissions(administrator=True)
    async def set_welcome_message(self, ctx: commands.Context, *, message: str):
        await db_service.update_guild_settings(ctx.guild.id, welcome_message=message)
        await ctx.send(f"Welcome message updated!")

async def setup(bot: commands.Bot):
    await bot.add_cog(CoreCog(bot))
