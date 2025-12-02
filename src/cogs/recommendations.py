import discord
from discord.ext import commands
from typing import List

from src.services.database import db_service
from src.utils.helpers import create_embed, is_staff, is_ticket_channel, format_price
from src.utils.translations import get_text
from src.config import Config

class RecommendationsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    async def get_personalized_recommendations(self, discord_id: int, guild_id: int, limit: int = 5) -> List:
        history = await db_service.get_user_history(discord_id, guild_id)
        
        if not history.get("user"):
            return await db_service.get_products(guild_id, available_only=True)
        
        user = history["user"]
        orders = history.get("orders", [])
        interactions = history.get("interactions", [])
        
        purchased_categories = set()
        purchased_product_ids = set()
        
        for order in orders:
            if hasattr(order, 'items'):
                for item in order.items:
                    purchased_product_ids.add(item.product_id)
                    if item.product and item.product.category:
                        purchased_categories.add(item.product.category)
        
        all_products = await db_service.get_products(guild_id, available_only=True)
        
        recommendations = []
        for product in all_products:
            if product.id not in purchased_product_ids:
                score = 0
                
                if product.category in purchased_categories:
                    score += 10
                
                if user.preferences:
                    pref_categories = user.preferences.get("categories", [])
                    if product.category in pref_categories:
                        score += 5
                
                if user.is_vip:
                    score += 2
                
                recommendations.append((product, score))
        
        recommendations.sort(key=lambda x: x[1], reverse=True)
        
        return [p for p, s in recommendations[:limit]]
    
    @commands.command(name="recommend")
    async def get_recommendations(self, ctx: commands.Context):
        if not is_ticket_channel(ctx.channel):
            embed = create_embed(
                title="Privacy Notice",
                description="Personalized recommendations are only available in ticket channels for your privacy.",
                color=Config.WARNING_COLOR
            )
            embed.add_field(
                name="Create a Ticket",
                value="Use `!newticket` to create a private ticket and get personalized recommendations.",
                inline=False
            )
            await ctx.send(embed=embed, delete_after=10)
            return
        
        user = await db_service.get_or_create_user(ctx.author.id, ctx.guild.id)
        lang = user.language
        
        recommendations = await self.get_personalized_recommendations(ctx.author.id, ctx.guild.id)
        
        if not recommendations:
            embed = create_embed(
                title=get_text("recommendation_title", lang),
                description="No recommendations available at the moment. Check back later!",
                color=Config.WARNING_COLOR
            )
            await ctx.send(embed=embed)
            return
        
        embed = create_embed(
            title=get_text("recommendation_title", lang),
            description=f"Based on your preferences and purchase history, here are some items you might like:",
            color=Config.EMBED_COLOR
        )
        
        for i, product in enumerate(recommendations, 1):
            product_info = f"**Price:** {format_price(product.price)}\n"
            if product.description:
                product_info += f"{product.description[:100]}..."
            if product.category:
                product_info += f"\n**Category:** {product.category}"
            
            embed.add_field(name=f"{i}. {product.name}", value=product_info, inline=False)
        
        embed.set_footer(text="Use !addtocart <product> to add to your cart")
        
        ticket = await db_service.get_ticket(channel_id=ctx.channel.id)
        if ticket:
            product_ids = [p.id for p in recommendations]
            await db_service.create_recommendation(
                ticket_id=ticket.id,
                user_discord_id=ctx.author.id,
                product_ids=product_ids,
                message="Personalized recommendations based on user history",
                reason="purchase_history"
            )
        
        await ctx.send(embed=embed)
    
    @commands.command(name="similar")
    async def similar_products(self, ctx: commands.Context, *, product_name: str):
        if not is_ticket_channel(ctx.channel):
            embed = create_embed(
                title="Privacy Notice",
                description="Product similarity search is only available in ticket channels.",
                color=Config.WARNING_COLOR
            )
            await ctx.send(embed=embed, delete_after=10)
            return
        
        products = await db_service.search_products(ctx.guild.id, product_name)
        
        if not products:
            await ctx.send("Product not found.", delete_after=5)
            return
        
        target_product = products[0]
        
        all_products = await db_service.get_products(ctx.guild.id, category=target_product.category)
        
        similar = [p for p in all_products if p.id != target_product.id][:5]
        
        if not similar:
            await ctx.send("No similar products found.", delete_after=5)
            return
        
        embed = create_embed(
            title=f"Products Similar to {target_product.name}",
            description=f"Based on category: {target_product.category or 'General'}",
            color=Config.EMBED_COLOR
        )
        
        for product in similar:
            product_info = f"**Price:** {format_price(product.price)}\n"
            if product.description:
                product_info += f"{product.description[:100]}..."
            
            embed.add_field(name=product.name, value=product_info, inline=False)
        
        await ctx.send(embed=embed)
    
    @commands.command(name="bestsellers")
    async def best_sellers(self, ctx: commands.Context, limit: int = 5):
        async with db_service.session_factory() as session:
            from sqlalchemy import select, func
            from src.models.database import OrderItem, Product
            
            result = await session.execute(
                select(
                    OrderItem.product_id,
                    func.count(OrderItem.id).label('sold_count')
                )
                .where(OrderItem.product_id.isnot(None))
                .group_by(OrderItem.product_id)
                .order_by(func.count(OrderItem.id).desc())
                .limit(limit)
            )
            best_sellers = result.all()
            
            if not best_sellers:
                await ctx.send("No sales data available yet.", delete_after=5)
                return
            
            products = []
            for product_id, sold_count in best_sellers:
                product_result = await session.execute(
                    select(Product).where(Product.id == product_id)
                )
                product = product_result.scalar_one_or_none()
                if product:
                    products.append((product, sold_count))
        
        embed = create_embed(
            title=f"Top {limit} Best Sellers",
            description="Most popular products by sales",
            color=Config.EMBED_COLOR
        )
        
        for i, (product, sold_count) in enumerate(products, 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"#{i}"
            
            product_info = f"**Price:** {format_price(product.price)}\n"
            product_info += f"**Sold:** {sold_count} units"
            
            embed.add_field(name=f"{medal} {product.name}", value=product_info, inline=False)
        
        await ctx.send(embed=embed)
    
    @commands.command(name="newproducts")
    async def new_products(self, ctx: commands.Context, limit: int = 5):
        async with db_service.session_factory() as session:
            from sqlalchemy import select
            from src.models.database import Product
            
            result = await session.execute(
                select(Product)
                .where(Product.guild_id == ctx.guild.id, Product.is_available == True)
                .order_by(Product.created_at.desc())
                .limit(limit)
            )
            products = result.scalars().all()
        
        if not products:
            await ctx.send("No products available.", delete_after=5)
            return
        
        embed = create_embed(
            title=f"New Arrivals",
            description=f"Latest {len(products)} products",
            color=Config.EMBED_COLOR
        )
        
        for product in products:
            product_info = f"**Price:** {format_price(product.price)}\n"
            if product.description:
                product_info += f"{product.description[:100]}..."
            product_info += f"\n**Added:** {product.created_at.strftime('%m/%d/%Y')}"
            
            embed.add_field(name=f"🆕 {product.name}", value=product_info, inline=False)
        
        embed.set_footer(text="Use !addtocart <product> to add to your cart")
        
        await ctx.send(embed=embed)
    
    @commands.command(name="setpreferences")
    async def set_preferences(self, ctx: commands.Context, *, categories: str):
        category_list = [c.strip() for c in categories.split(",")]
        
        preferences = {"categories": category_list}
        
        await db_service.update_user_preferences(ctx.author.id, ctx.guild.id, preferences)
        
        embed = create_embed(
            title="Preferences Updated",
            description="Your product preferences have been saved!",
            color=Config.SUCCESS_COLOR
        )
        embed.add_field(
            name="Preferred Categories", 
            value=", ".join(category_list), 
            inline=False
        )
        embed.add_field(
            name="Note",
            value="Use `!recommend` in a ticket channel to get personalized recommendations based on your preferences.",
            inline=False
        )
        
        await ctx.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(RecommendationsCog(bot))
