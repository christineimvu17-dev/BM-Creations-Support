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
    
    @app_commands.command(name="ping", description="Check bot latency")
    async def ping(self, interaction: discord.Interaction):
        latency = round(self.bot.latency * 1000)
        embed = create_embed(
            title="Pong!",
            description=f"Bot latency: **{latency}ms**",
            color=Config.EMBED_COLOR
        )
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="help", description="Show all available commands")
    async def help_command(self, interaction: discord.Interaction):
        user = await db_service.get_or_create_user(interaction.user.id, interaction.guild.id)
        lang = user.language if user else "en"
        
        embed = create_embed(
            title=get_text("help_title", lang),
            description="Here are all available slash commands:",
            color=Config.EMBED_COLOR
        )
        
        embed.add_field(
            name="General Commands",
            value="""
`/ping` - Check bot latency
`/help` - Show this help message
`/setlanguage` - Set your preferred language
`/profile` - View your profile
            """,
            inline=False
        )
        
        embed.add_field(
            name="Ticket Commands",
            value="""
`/newticket` - Create a new ticket
`/closeticket` - Close current ticket
`/viewtickets` - View all active tickets (Staff)
            """,
            inline=False
        )
        
        embed.add_field(
            name="Order Commands",
            value="""
`/order` - Create a new order
`/trackorder` - Track an order
`/myorders` - View your orders
`/completeorder` - Complete an order (Staff)
            """,
            inline=False
        )
        
        embed.add_field(
            name="Shopping Commands",
            value="""
`/cart` - View your cart
`/addtocart` - Add item to cart
`/clearcart` - Clear your cart
`/wishlist` - View your wishlist
`/addtowishlist` - Add item to wishlist
            """,
            inline=False
        )
        
        embed.add_field(
            name="FAQ & Info",
            value="""
`/faq` - View FAQ list
`/ask` - Ask a question
`/products` - View available products
            """,
            inline=False
        )
        
        embed.add_field(
            name="Moderation (Staff)",
            value="""
`/warn` - Warn a user
`/warnings` - View user warnings
`/announce` - Send announcement
`/stats` - View server statistics
            """,
            inline=False
        )
        
        embed.add_field(
            name="Utilities",
            value="""
`/remind` - Set a reminder
`/feedback` - Submit feedback
`/weather` - Get weather info
            """,
            inline=False
        )
        
        embed.set_footer(text="BM Creations Support Bot | Type / to see all commands")
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="setlanguage", description="Set your preferred language")
    @app_commands.describe(language="Your preferred language code")
    @app_commands.choices(language=[
        app_commands.Choice(name="English", value="en"),
        app_commands.Choice(name="Spanish", value="es"),
        app_commands.Choice(name="French", value="fr"),
        app_commands.Choice(name="German", value="de"),
        app_commands.Choice(name="Portuguese", value="pt"),
        app_commands.Choice(name="Arabic", value="ar"),
        app_commands.Choice(name="Chinese", value="zh"),
        app_commands.Choice(name="Japanese", value="ja"),
        app_commands.Choice(name="Korean", value="ko"),
        app_commands.Choice(name="Russian", value="ru"),
    ])
    async def set_language(self, interaction: discord.Interaction, language: str):
        await db_service.update_user_language(interaction.user.id, interaction.guild.id, language)
        
        embed = create_embed(
            title=get_text("language_updated", language),
            description=get_text("language_set_message", language, lang=language.upper()),
            color=Config.SUCCESS_COLOR
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="profile", description="View your profile")
    async def profile(self, interaction: discord.Interaction):
        user = await db_service.get_or_create_user(
            interaction.user.id, interaction.guild.id, str(interaction.user), interaction.user.display_name
        )
        
        orders = await db_service.get_user_orders(interaction.user.id, interaction.guild.id)
        total_orders = len(orders) if orders else 0
        total_spent = sum(o.total_amount for o in orders) if orders else 0
        
        embed = create_embed(
            title=f"Profile: {interaction.user.display_name}",
            color=Config.EMBED_COLOR,
            thumbnail_url=interaction.user.display_avatar.url if interaction.user.display_avatar else None
        )
        
        embed.add_field(name="Language", value=user.language.upper() if user else "EN", inline=True)
        embed.add_field(name="Total Orders", value=str(total_orders), inline=True)
        embed.add_field(name="Total Spent", value=f"${total_spent:.2f}", inline=True)
        
        if user:
            member_since = user.created_at.strftime("%B %d, %Y") if user.created_at else "Unknown"
            embed.add_field(name="Member Since", value=member_since, inline=True)
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="setwelcome", description="Set the welcome channel (Admin)")
    @app_commands.describe(channel="The channel for welcome messages")
    @app_commands.default_permissions(administrator=True)
    async def set_welcome(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await db_service.update_guild_settings(interaction.guild.id, welcome_channel_id=channel.id)
        
        embed = create_embed(
            title="Welcome Channel Set",
            description=f"Welcome messages will now be sent to {channel.mention}",
            color=Config.SUCCESS_COLOR
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="setwelcomemsg", description="Set the welcome message (Admin)")
    @app_commands.describe(message="The welcome message (use {user} and {server} as placeholders)")
    @app_commands.default_permissions(administrator=True)
    async def set_welcome_message(self, interaction: discord.Interaction, message: str):
        await db_service.update_guild_settings(interaction.guild.id, welcome_message=message)
        
        embed = create_embed(
            title="Welcome Message Updated",
            description=f"New welcome message:\n\n{message}",
            color=Config.SUCCESS_COLOR
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="setorders", description="Set the order status channel (Admin)")
    @app_commands.describe(channel="The channel for order updates")
    @app_commands.default_permissions(administrator=True)
    async def set_orders(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await db_service.update_guild_settings(interaction.guild.id, order_channel_id=channel.id)
        
        embed = create_embed(
            title="Order Channel Set",
            description=f"Order updates will now be posted to {channel.mention}",
            color=Config.SUCCESS_COLOR
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="serverinfo", description="View server information")
    async def server_info(self, interaction: discord.Interaction):
        guild = interaction.guild
        
        embed = create_embed(
            title=guild.name,
            color=Config.EMBED_COLOR,
            thumbnail_url=guild.icon.url if guild.icon else None
        )
        
        embed.add_field(name="Owner", value=guild.owner.mention if guild.owner else "Unknown", inline=True)
        embed.add_field(name="Members", value=str(guild.member_count), inline=True)
        embed.add_field(name="Channels", value=str(len(guild.channels)), inline=True)
        embed.add_field(name="Roles", value=str(len(guild.roles)), inline=True)
        embed.add_field(name="Created", value=guild.created_at.strftime("%B %d, %Y"), inline=True)
        embed.add_field(name="Boost Level", value=str(guild.premium_tier), inline=True)
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="userinfo", description="View info about a user")
    @app_commands.describe(member="The user to view info about")
    async def user_info(self, interaction: discord.Interaction, member: discord.Member = None):
        member = member or interaction.user
        
        embed = create_embed(
            title=f"User Info: {member.display_name}",
            color=member.color if member.color != discord.Color.default() else Config.EMBED_COLOR,
            thumbnail_url=member.display_avatar.url if member.display_avatar else None
        )
        
        embed.add_field(name="Username", value=str(member), inline=True)
        embed.add_field(name="ID", value=str(member.id), inline=True)
        embed.add_field(name="Joined Server", value=member.joined_at.strftime("%B %d, %Y") if member.joined_at else "Unknown", inline=True)
        embed.add_field(name="Account Created", value=member.created_at.strftime("%B %d, %Y"), inline=True)
        
        roles = [r.mention for r in member.roles if r.name != "@everyone"][:5]
        embed.add_field(name="Roles", value=", ".join(roles) if roles else "None", inline=False)
        
        await interaction.response.send_message(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(CoreCog(bot))
