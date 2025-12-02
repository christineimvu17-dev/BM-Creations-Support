import discord
from discord.ext import commands

from src.services.database import db_service
from src.utils.helpers import create_embed, is_staff, format_timestamp
from src.utils.translations import get_text
from src.config import Config

class FeedbackCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    @commands.command(name="feedback")
    async def submit_feedback(self, ctx: commands.Context, *, message: str):
        await ctx.message.delete()
        
        user = await db_service.get_or_create_user(ctx.author.id, ctx.guild.id, str(ctx.author), ctx.author.display_name)
        lang = user.language
        
        feedback = await db_service.add_feedback(
            guild_id=ctx.guild.id,
            user_id=user.id,
            comment=message,
            category="general"
        )
        
        embed = create_embed(
            title="Feedback Submitted",
            description=get_text("feedback_thanks", lang),
            color=Config.SUCCESS_COLOR
        )
        embed.add_field(name="Your Feedback", value=message[:1024], inline=False)
        
        await ctx.send(embed=embed)
        
        settings = await db_service.get_or_create_guild_settings(ctx.guild.id)
        if settings.log_channel_id:
            log_channel = self.bot.get_channel(settings.log_channel_id)
            if log_channel:
                log_embed = create_embed(
                    title="New Feedback Received",
                    description=f"From: {ctx.author.mention}",
                    color=Config.EMBED_COLOR
                )
                log_embed.add_field(name="Feedback", value=message[:1024], inline=False)
                await log_channel.send(embed=log_embed)
    
    @commands.command(name="review")
    async def submit_review(self, ctx: commands.Context, rating: int, *, comment: str = None):
        await ctx.message.delete()
        
        if not 1 <= rating <= 5:
            await ctx.send("Rating must be between 1 and 5 stars.", delete_after=5)
            return
        
        user = await db_service.get_or_create_user(ctx.author.id, ctx.guild.id, str(ctx.author), ctx.author.display_name)
        
        orders = await db_service.get_user_orders(ctx.author.id, ctx.guild.id)
        order_id = orders[0].id if orders else None
        
        feedback = await db_service.add_feedback(
            guild_id=ctx.guild.id,
            user_id=user.id,
            rating=rating,
            comment=comment,
            order_id=order_id,
            category="review",
            is_public=True
        )
        
        stars = "⭐" * rating + "☆" * (5 - rating)
        
        embed = create_embed(
            title="Review Submitted",
            description=f"Thank you for your review!\n\n{stars}",
            color=Config.SUCCESS_COLOR
        )
        
        if comment:
            embed.add_field(name="Your Review", value=comment[:1024], inline=False)
        
        await ctx.send(embed=embed)
        
        settings = await db_service.get_or_create_guild_settings(ctx.guild.id)
        if settings.order_channel_id:
            review_channel = self.bot.get_channel(settings.order_channel_id)
            if review_channel:
                public_embed = create_embed(
                    title="New Review",
                    description=f"**Rating:** {stars}\n\n{comment or 'No comment provided.'}",
                    color=Config.SUCCESS_COLOR
                )
                public_embed.set_author(
                    name=ctx.author.display_name, 
                    icon_url=ctx.author.display_avatar.url if ctx.author.display_avatar else None
                )
                await review_channel.send(embed=public_embed)
    
    @commands.command(name="suggest")
    async def submit_suggestion(self, ctx: commands.Context, *, suggestion: str):
        await ctx.message.delete()
        
        user = await db_service.get_or_create_user(ctx.author.id, ctx.guild.id, str(ctx.author), ctx.author.display_name)
        
        await db_service.add_feedback(
            guild_id=ctx.guild.id,
            user_id=user.id,
            comment=suggestion,
            category="suggestion"
        )
        
        embed = create_embed(
            title="Suggestion Submitted",
            description="Thank you for your suggestion! Our team will review it.",
            color=Config.SUCCESS_COLOR
        )
        embed.add_field(name="Your Suggestion", value=suggestion[:1024], inline=False)
        
        suggestion_msg = await ctx.send(embed=embed)
        
        await suggestion_msg.add_reaction("👍")
        await suggestion_msg.add_reaction("👎")
    
    @commands.command(name="report")
    async def submit_report(self, ctx: commands.Context, *, issue: str):
        await ctx.message.delete()
        
        user = await db_service.get_or_create_user(ctx.author.id, ctx.guild.id, str(ctx.author), ctx.author.display_name)
        
        await db_service.add_feedback(
            guild_id=ctx.guild.id,
            user_id=user.id,
            comment=issue,
            category="report"
        )
        
        embed = create_embed(
            title="Report Submitted",
            description="Thank you for your report. Our moderation team will review it.",
            color=Config.WARNING_COLOR
        )
        
        await ctx.author.send(embed=embed)
        
        settings = await db_service.get_or_create_guild_settings(ctx.guild.id)
        if settings.log_channel_id:
            log_channel = self.bot.get_channel(settings.log_channel_id)
            if log_channel:
                report_embed = create_embed(
                    title="New Report",
                    description=f"From: {ctx.author.mention}",
                    color=Config.ERROR_COLOR
                )
                report_embed.add_field(name="Report", value=issue[:1024], inline=False)
                report_embed.add_field(name="Channel", value=ctx.channel.mention, inline=True)
                await log_channel.send(embed=report_embed)
    
    @commands.command(name="viewfeedback")
    @commands.has_permissions(administrator=True)
    async def view_feedback(self, ctx: commands.Context, category: str = None):
        async with db_service.session_factory() as session:
            from sqlalchemy import select
            from src.models.database import Feedback, User
            
            query = select(Feedback).where(Feedback.guild_id == ctx.guild.id)
            if category:
                query = query.where(Feedback.category == category.lower())
            query = query.order_by(Feedback.created_at.desc()).limit(20)
            
            result = await session.execute(query)
            feedbacks = result.scalars().all()
        
        if not feedbacks:
            await ctx.send("No feedback found.", delete_after=5)
            return
        
        embed = create_embed(
            title=f"Feedback ({len(feedbacks)} entries)",
            description=f"Category: {category or 'All'}",
            color=Config.EMBED_COLOR
        )
        
        for fb in feedbacks[:10]:
            rating_str = f"{'⭐' * fb.rating if fb.rating else 'N/A'}"
            fb_info = f"**Category:** {fb.category}\n"
            if fb.rating:
                fb_info += f"**Rating:** {rating_str}\n"
            fb_info += f"**Comment:** {fb.comment[:100] if fb.comment else 'No comment'}..."
            
            embed.add_field(
                name=f"Feedback #{fb.id} | {format_timestamp(fb.created_at, '%m/%d/%Y')}",
                value=fb_info,
                inline=False
            )
        
        await ctx.send(embed=embed)
    
    @commands.command(name="reviews")
    async def view_reviews(self, ctx: commands.Context):
        async with db_service.session_factory() as session:
            from sqlalchemy import select, func
            from src.models.database import Feedback
            
            result = await session.execute(
                select(Feedback).where(
                    Feedback.guild_id == ctx.guild.id,
                    Feedback.category == "review",
                    Feedback.is_public == True
                ).order_by(Feedback.created_at.desc()).limit(10)
            )
            reviews = result.scalars().all()
            
            avg_result = await session.execute(
                select(func.avg(Feedback.rating)).where(
                    Feedback.guild_id == ctx.guild.id,
                    Feedback.category == "review",
                    Feedback.rating.isnot(None)
                )
            )
            avg_rating = avg_result.scalar() or 0
        
        embed = create_embed(
            title="Recent Reviews",
            description=f"Average Rating: {'⭐' * round(avg_rating)} ({avg_rating:.1f}/5)",
            color=Config.SUCCESS_COLOR
        )
        
        for review in reviews:
            stars = "⭐" * review.rating + "☆" * (5 - review.rating) if review.rating else "N/A"
            embed.add_field(
                name=f"{stars}",
                value=review.comment[:200] if review.comment else "No comment",
                inline=False
            )
        
        if not reviews:
            embed.add_field(name="No Reviews Yet", value="Be the first to leave a review with !review <1-5> <comment>", inline=False)
        
        await ctx.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(FeedbackCog(bot))
