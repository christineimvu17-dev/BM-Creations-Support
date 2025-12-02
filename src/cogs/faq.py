import discord
from discord.ext import commands
from typing import List

from src.services.database import db_service
from src.utils.helpers import create_embed, extract_keywords, is_staff
from src.utils.translations import get_text
from src.config import Config

class FAQCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.auto_response_cache = {}
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        
        if message.content.startswith("!"):
            return
        
        content_lower = message.content.lower()
        
        question_indicators = ["?", "how", "what", "when", "where", "why", "can", "do you", "is there"]
        is_question = any(indicator in content_lower for indicator in question_indicators)
        
        if not is_question:
            return
        
        faqs = await db_service.search_faq(message.guild.id, message.content[:100])
        
        if faqs:
            best_match = faqs[0]
            
            async with db_service.session_factory() as session:
                from sqlalchemy import select
                from src.models.database import FAQ
                result = await session.execute(
                    select(FAQ).where(FAQ.id == best_match.id)
                )
                faq = result.scalar_one_or_none()
                if faq:
                    faq.usage_count += 1
                    await session.commit()
            
            embed = create_embed(
                title="Related FAQ",
                description=f"**Q:** {best_match.question}\n\n**A:** {best_match.answer}",
                color=Config.EMBED_COLOR
            )
            embed.set_footer(text="Use !ask <question> for more specific answers")
            
            await message.reply(embed=embed, mention_author=False)
    
    @commands.command(name="faq")
    async def faq_list(self, ctx: commands.Context, category: str = None):
        faqs = await db_service.get_all_faqs(ctx.guild.id)
        
        if not faqs:
            await ctx.send("No FAQs available yet.", delete_after=5)
            return
        
        if category:
            faqs = [f for f in faqs if f.category and f.category.lower() == category.lower()]
        
        embed = create_embed(
            title="Frequently Asked Questions",
            description=f"Showing {len(faqs)} FAQ(s)",
            color=Config.EMBED_COLOR
        )
        
        for faq in faqs[:25]:
            answer_preview = faq.answer[:200] + "..." if len(faq.answer) > 200 else faq.answer
            embed.add_field(
                name=f"Q: {faq.question[:100]}", 
                value=f"A: {answer_preview}", 
                inline=False
            )
        
        if not faqs:
            embed.add_field(
                name="No FAQs Found",
                value="No FAQs match the specified category." if category else "No FAQs available.",
                inline=False
            )
        
        await ctx.send(embed=embed)
    
    @commands.command(name="ask")
    async def ask_question(self, ctx: commands.Context, *, question: str):
        user = await db_service.get_or_create_user(ctx.author.id, ctx.guild.id)
        lang = user.language
        
        faqs = await db_service.search_faq(ctx.guild.id, question)
        
        if faqs:
            embed = create_embed(
                title="Here's what I found:",
                color=Config.EMBED_COLOR
            )
            
            for i, faq in enumerate(faqs[:3], 1):
                embed.add_field(
                    name=f"{i}. {faq.question[:100]}",
                    value=faq.answer[:500],
                    inline=False
                )
            
            embed.set_footer(text="Didn't find what you're looking for? Create a ticket with !newticket")
            await ctx.send(embed=embed)
        else:
            embed = create_embed(
                title="No Answer Found",
                description=get_text("faq_not_found", lang),
                color=Config.WARNING_COLOR
            )
            embed.add_field(
                name="Need Help?",
                value="Create a support ticket with `!newticket` for personalized assistance.",
                inline=False
            )
            await ctx.send(embed=embed)
    
    @commands.command(name="addfaq")
    @commands.has_permissions(administrator=True)
    async def add_faq(self, ctx: commands.Context, *, content: str):
        try:
            parts = content.split("|")
            if len(parts) < 2:
                await ctx.send("Format: `!addfaq Question | Answer | Category (optional)`", delete_after=10)
                return
            
            question = parts[0].strip()
            answer = parts[1].strip()
            category = parts[2].strip() if len(parts) > 2 else None
            
            keywords = extract_keywords(question)
            
            faq = await db_service.get_or_create_faq(
                guild_id=ctx.guild.id,
                question=question,
                answer=answer,
                keywords=keywords,
                category=category
            )
            
            embed = create_embed(
                title="FAQ Added",
                description="New FAQ entry has been added successfully!",
                color=Config.SUCCESS_COLOR
            )
            embed.add_field(name="Question", value=question, inline=False)
            embed.add_field(name="Answer", value=answer[:1024], inline=False)
            if category:
                embed.add_field(name="Category", value=category, inline=True)
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"Error adding FAQ: {str(e)}", delete_after=10)
    
    @commands.command(name="removefaq")
    @commands.has_permissions(administrator=True)
    async def remove_faq(self, ctx: commands.Context, faq_id: int):
        async with db_service.session_factory() as session:
            from sqlalchemy import select, delete
            from src.models.database import FAQ
            
            result = await session.execute(
                select(FAQ).where(FAQ.id == faq_id, FAQ.guild_id == ctx.guild.id)
            )
            faq = result.scalar_one_or_none()
            
            if not faq:
                await ctx.send("FAQ not found.", delete_after=5)
                return
            
            await session.execute(
                delete(FAQ).where(FAQ.id == faq_id)
            )
            await session.commit()
        
        embed = create_embed(
            title="FAQ Removed",
            description=f"FAQ #{faq_id} has been removed.",
            color=Config.SUCCESS_COLOR
        )
        await ctx.send(embed=embed)
    
    @commands.command(name="editfaq")
    @commands.has_permissions(administrator=True)
    async def edit_faq(self, ctx: commands.Context, faq_id: int, *, content: str):
        try:
            parts = content.split("|")
            question = parts[0].strip() if len(parts) > 0 else None
            answer = parts[1].strip() if len(parts) > 1 else None
            
            async with db_service.session_factory() as session:
                from sqlalchemy import select
                from src.models.database import FAQ
                
                result = await session.execute(
                    select(FAQ).where(FAQ.id == faq_id, FAQ.guild_id == ctx.guild.id)
                )
                faq = result.scalar_one_or_none()
                
                if not faq:
                    await ctx.send("FAQ not found.", delete_after=5)
                    return
                
                if question:
                    faq.question = question
                    faq.keywords = extract_keywords(question)
                if answer:
                    faq.answer = answer
                
                await session.commit()
            
            embed = create_embed(
                title="FAQ Updated",
                description=f"FAQ #{faq_id} has been updated.",
                color=Config.SUCCESS_COLOR
            )
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"Error updating FAQ: {str(e)}", delete_after=10)
    
    @commands.command(name="faqstats")
    @commands.has_permissions(administrator=True)
    async def faq_stats(self, ctx: commands.Context):
        faqs = await db_service.get_all_faqs(ctx.guild.id)
        
        if not faqs:
            await ctx.send("No FAQs available.", delete_after=5)
            return
        
        sorted_faqs = sorted(faqs, key=lambda x: x.usage_count, reverse=True)
        
        embed = create_embed(
            title="FAQ Statistics",
            description=f"Total FAQs: {len(faqs)}",
            color=Config.EMBED_COLOR
        )
        
        top_faqs = sorted_faqs[:10]
        for i, faq in enumerate(top_faqs, 1):
            embed.add_field(
                name=f"{i}. {faq.question[:50]}...",
                value=f"Used {faq.usage_count} times",
                inline=False
            )
        
        await ctx.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(FAQCog(bot))
