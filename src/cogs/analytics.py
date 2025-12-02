import discord
from discord.ext import commands
from datetime import datetime, timedelta

from src.services.database import db_service
from src.utils.helpers import create_embed, is_staff, format_price, create_progress_bar
from src.utils.translations import get_text
from src.config import Config

class AnalyticsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    @commands.command(name="stats")
    @commands.has_permissions(administrator=True)
    async def server_stats(self, ctx: commands.Context, days: int = 30):
        user = await db_service.get_or_create_user(ctx.author.id, ctx.guild.id)
        lang = user.language
        
        analytics = await db_service.get_guild_analytics(ctx.guild.id, days)
        
        embed = create_embed(
            title=get_text("stats_title", lang),
            description=f"Statistics for the last {days} days",
            color=Config.EMBED_COLOR
        )
        
        embed.add_field(name="Total Users", value=str(analytics["total_users"]), inline=True)
        embed.add_field(name="Orders", value=str(analytics["orders_count"]), inline=True)
        embed.add_field(name="Revenue", value=format_price(analytics["total_revenue"]), inline=True)
        embed.add_field(name="Tickets", value=str(analytics["tickets_count"]), inline=True)
        embed.add_field(name="Server Members", value=str(ctx.guild.member_count), inline=True)
        embed.add_field(name="Channels", value=str(len(ctx.guild.channels)), inline=True)
        
        embed.set_footer(text=f"Data from last {days} days | {ctx.guild.name}")
        embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else None)
        
        await ctx.send(embed=embed)
    
    @commands.command(name="dashboard")
    @commands.has_permissions(administrator=True)
    async def dashboard(self, ctx: commands.Context):
        guild = ctx.guild
        
        analytics_30 = await db_service.get_guild_analytics(guild.id, 30)
        analytics_7 = await db_service.get_guild_analytics(guild.id, 7)
        analytics_1 = await db_service.get_guild_analytics(guild.id, 1)
        
        embed = create_embed(
            title=f"Dashboard - {guild.name}",
            description="Comprehensive server overview",
            color=Config.EMBED_COLOR
        )
        
        member_breakdown = f"**Total:** {guild.member_count}\n"
        humans = len([m for m in guild.members if not m.bot])
        bots = len([m for m in guild.members if m.bot])
        member_breakdown += f"**Humans:** {humans} | **Bots:** {bots}\n"
        online = len([m for m in guild.members if m.status != discord.Status.offline])
        member_breakdown += f"**Online:** {online}"
        
        embed.add_field(name="Members", value=member_breakdown, inline=True)
        
        channel_breakdown = f"**Text:** {len(guild.text_channels)}\n"
        channel_breakdown += f"**Voice:** {len(guild.voice_channels)}\n"
        channel_breakdown += f"**Categories:** {len(guild.categories)}"
        
        embed.add_field(name="Channels", value=channel_breakdown, inline=True)
        
        server_info = f"**Boost Level:** {guild.premium_tier}\n"
        server_info += f"**Boosters:** {guild.premium_subscription_count or 0}\n"
        server_info += f"**Roles:** {len(guild.roles)}"
        
        embed.add_field(name="Server Info", value=server_info, inline=True)
        
        orders_summary = f"**Today:** {analytics_1['orders_count']}\n"
        orders_summary += f"**This Week:** {analytics_7['orders_count']}\n"
        orders_summary += f"**This Month:** {analytics_30['orders_count']}"
        
        embed.add_field(name="Orders", value=orders_summary, inline=True)
        
        revenue_summary = f"**Today:** {format_price(analytics_1['total_revenue'])}\n"
        revenue_summary += f"**This Week:** {format_price(analytics_7['total_revenue'])}\n"
        revenue_summary += f"**This Month:** {format_price(analytics_30['total_revenue'])}"
        
        embed.add_field(name="Revenue", value=revenue_summary, inline=True)
        
        tickets_summary = f"**Today:** {analytics_1['tickets_count']}\n"
        tickets_summary += f"**This Week:** {analytics_7['tickets_count']}\n"
        tickets_summary += f"**This Month:** {analytics_30['tickets_count']}"
        
        embed.add_field(name="Tickets", value=tickets_summary, inline=True)
        
        active_tickets = await db_service.get_active_tickets(guild.id)
        if active_tickets:
            embed.add_field(
                name="Active Tickets", 
                value=f"{len(active_tickets)} tickets currently open", 
                inline=False
            )
        
        embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
        embed.set_footer(text=f"Last updated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
        
        await ctx.send(embed=embed)
    
    @commands.command(name="userstats")
    @commands.has_permissions(administrator=True)
    async def user_stats(self, ctx: commands.Context, member: discord.Member = None):
        target = member or ctx.author
        
        history = await db_service.get_user_history(target.id, ctx.guild.id)
        
        if not history.get("user"):
            await ctx.send("No data found for this user.", delete_after=5)
            return
        
        user = history["user"]
        
        embed = create_embed(
            title=f"User Statistics: {target.display_name}",
            color=Config.EMBED_COLOR,
            thumbnail_url=target.display_avatar.url if target.display_avatar else None
        )
        
        embed.add_field(name="Total Orders", value=str(user.total_orders), inline=True)
        embed.add_field(name="Total Spent", value=format_price(user.total_spent), inline=True)
        embed.add_field(name="VIP Status", value="Yes" if user.is_vip else "No", inline=True)
        
        embed.add_field(name="Language", value=user.language.upper(), inline=True)
        embed.add_field(name="Joined", value=user.joined_at.strftime("%b %d, %Y"), inline=True)
        embed.add_field(name="Last Active", value=user.last_active.strftime("%b %d, %Y"), inline=True)
        
        if history.get("orders"):
            orders = history["orders"]
            embed.add_field(name="Order Count", value=str(len(orders)), inline=True)
        
        if history.get("tickets"):
            tickets = history["tickets"]
            embed.add_field(name="Ticket Count", value=str(len(tickets)), inline=True)
        
        if history.get("interactions"):
            interactions = history["interactions"]
            embed.add_field(name="Interactions", value=str(len(interactions)), inline=True)
        
        await ctx.send(embed=embed)
    
    @commands.command(name="orderstats")
    @commands.has_permissions(administrator=True)
    async def order_stats(self, ctx: commands.Context):
        async with db_service.session_factory() as session:
            from sqlalchemy import select, func
            from src.models.database import Order, OrderStatus
            
            total_result = await session.execute(
                select(func.count(Order.id)).where(Order.guild_id == ctx.guild.id)
            )
            total_orders = total_result.scalar() or 0
            
            delivered_result = await session.execute(
                select(func.count(Order.id)).where(
                    Order.guild_id == ctx.guild.id,
                    Order.status == OrderStatus.DELIVERED
                )
            )
            delivered_orders = delivered_result.scalar() or 0
            
            pending_result = await session.execute(
                select(func.count(Order.id)).where(
                    Order.guild_id == ctx.guild.id,
                    Order.status.in_([OrderStatus.PENDING, OrderStatus.CONFIRMED, OrderStatus.PROCESSING])
                )
            )
            pending_orders = pending_result.scalar() or 0
            
            revenue_result = await session.execute(
                select(func.sum(Order.total_amount)).where(
                    Order.guild_id == ctx.guild.id,
                    Order.status == OrderStatus.DELIVERED
                )
            )
            total_revenue = revenue_result.scalar() or 0.0
            
            avg_result = await session.execute(
                select(func.avg(Order.total_amount)).where(
                    Order.guild_id == ctx.guild.id,
                    Order.status == OrderStatus.DELIVERED
                )
            )
            avg_order = avg_result.scalar() or 0.0
        
        completion_rate = (delivered_orders / total_orders * 100) if total_orders > 0 else 0
        
        embed = create_embed(
            title="Order Statistics",
            description=f"Overview of all orders",
            color=Config.EMBED_COLOR
        )
        
        embed.add_field(name="Total Orders", value=str(total_orders), inline=True)
        embed.add_field(name="Delivered", value=str(delivered_orders), inline=True)
        embed.add_field(name="Pending", value=str(pending_orders), inline=True)
        embed.add_field(name="Total Revenue", value=format_price(total_revenue), inline=True)
        embed.add_field(name="Average Order", value=format_price(avg_order), inline=True)
        embed.add_field(name="Completion Rate", value=f"{completion_rate:.1f}%", inline=True)
        
        progress = create_progress_bar(delivered_orders, total_orders)
        embed.add_field(name="Completion Progress", value=f"{progress} {delivered_orders}/{total_orders}", inline=False)
        
        await ctx.send(embed=embed)
    
    @commands.command(name="topbuyers")
    @commands.has_permissions(administrator=True)
    async def top_buyers(self, ctx: commands.Context, limit: int = 10):
        async with db_service.session_factory() as session:
            from sqlalchemy import select
            from src.models.database import User
            
            result = await session.execute(
                select(User).where(
                    User.guild_id == ctx.guild.id,
                    User.total_orders > 0
                ).order_by(User.total_spent.desc()).limit(limit)
            )
            top_users = result.scalars().all()
        
        if not top_users:
            await ctx.send("No buyers found yet.", delete_after=5)
            return
        
        embed = create_embed(
            title=f"Top {limit} Buyers",
            description="Ranked by total spent",
            color=Config.EMBED_COLOR
        )
        
        for i, user in enumerate(top_users, 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"#{i}"
            member = ctx.guild.get_member(user.discord_id)
            name = member.display_name if member else f"User {user.discord_id}"
            
            embed.add_field(
                name=f"{medal} {name}",
                value=f"**Orders:** {user.total_orders} | **Spent:** {format_price(user.total_spent)}",
                inline=False
            )
        
        await ctx.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(AnalyticsCog(bot))
