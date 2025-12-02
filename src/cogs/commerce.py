import discord
from discord.ext import commands

from src.services.database import db_service
from src.utils.helpers import create_embed, format_price
from src.utils.translations import get_text
from src.config import Config

class CommerceCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    @commands.command(name="cart")
    async def view_cart(self, ctx: commands.Context):
        user = await db_service.get_or_create_user(ctx.author.id, ctx.guild.id)
        cart_items = await db_service.get_cart(ctx.author.id, ctx.guild.id)
        
        lang = user.language
        
        if not cart_items:
            embed = create_embed(
                title="Shopping Cart",
                description=get_text("cart_empty", lang),
                color=Config.WARNING_COLOR
            )
            await ctx.send(embed=embed)
            return
        
        total = 0.0
        items_text = ""
        
        for item in cart_items:
            if item.product:
                item_total = item.product.price * item.quantity
                total += item_total
                items_text += f"**{item.product.name}** x{item.quantity} - {format_price(item_total)}\n"
            else:
                items_text += f"**Unknown Product** x{item.quantity}\n"
        
        embed = create_embed(
            title=f"Shopping Cart ({len(cart_items)} items)",
            description=items_text or "Your cart is empty.",
            color=Config.EMBED_COLOR
        )
        
        embed.add_field(name="Total", value=format_price(total), inline=False)
        embed.set_footer(text="Use !checkout to place an order")
        
        await ctx.send(embed=embed)
    
    @commands.command(name="addtocart")
    async def add_to_cart(self, ctx: commands.Context, *, product_name: str):
        user = await db_service.get_or_create_user(ctx.author.id, ctx.guild.id)
        lang = user.language
        
        products = await db_service.search_products(ctx.guild.id, product_name)
        
        if not products:
            embed = create_embed(
                title="Product Not Found",
                description=get_text("product_not_found", lang),
                color=Config.ERROR_COLOR
            )
            await ctx.send(embed=embed, delete_after=5)
            return
        
        product = products[0]
        
        await db_service.add_to_cart(ctx.author.id, ctx.guild.id, product.id)
        
        embed = create_embed(
            title="Added to Cart",
            description=get_text("cart_added", lang, item=product.name),
            color=Config.SUCCESS_COLOR
        )
        
        embed.add_field(name="Product", value=product.name, inline=True)
        embed.add_field(name="Price", value=format_price(product.price), inline=True)
        
        await ctx.send(embed=embed)
    
    @commands.command(name="removefromcart")
    async def remove_from_cart(self, ctx: commands.Context, *, product_name: str):
        user = await db_service.get_or_create_user(ctx.author.id, ctx.guild.id)
        cart_items = await db_service.get_cart(ctx.author.id, ctx.guild.id)
        
        for item in cart_items:
            if item.product and product_name.lower() in item.product.name.lower():
                async with db_service.session_factory() as session:
                    from sqlalchemy import delete
                    from src.models.database import CartItem
                    await session.execute(
                        delete(CartItem).where(CartItem.id == item.id)
                    )
                    await session.commit()
                
                embed = create_embed(
                    title="Removed from Cart",
                    description=f"**{item.product.name}** has been removed from your cart.",
                    color=Config.SUCCESS_COLOR
                )
                await ctx.send(embed=embed)
                return
        
        await ctx.send("Product not found in your cart.", delete_after=5)
    
    @commands.command(name="clearcart")
    async def clear_cart(self, ctx: commands.Context):
        await db_service.clear_cart(ctx.author.id, ctx.guild.id)
        
        embed = create_embed(
            title="Cart Cleared",
            description="Your shopping cart has been cleared.",
            color=Config.SUCCESS_COLOR
        )
        await ctx.send(embed=embed)
    
    @commands.command(name="wishlist")
    async def view_wishlist(self, ctx: commands.Context):
        user = await db_service.get_or_create_user(ctx.author.id, ctx.guild.id)
        wishlist_items = await db_service.get_wishlist(ctx.author.id, ctx.guild.id)
        
        lang = user.language
        
        if not wishlist_items:
            embed = create_embed(
                title="Wishlist",
                description=get_text("wishlist_empty", lang),
                color=Config.WARNING_COLOR
            )
            await ctx.send(embed=embed)
            return
        
        items_text = ""
        for item in wishlist_items:
            if item.product:
                items_text += f"**{item.product.name}** - {format_price(item.product.price)}\n"
        
        embed = create_embed(
            title=f"Wishlist ({len(wishlist_items)} items)",
            description=items_text or "Your wishlist is empty.",
            color=Config.EMBED_COLOR
        )
        
        embed.set_footer(text="Use !addtocart <product> to add items to your cart")
        
        await ctx.send(embed=embed)
    
    @commands.command(name="addtowishlist")
    async def add_to_wishlist(self, ctx: commands.Context, *, product_name: str):
        user = await db_service.get_or_create_user(ctx.author.id, ctx.guild.id)
        lang = user.language
        
        products = await db_service.search_products(ctx.guild.id, product_name)
        
        if not products:
            embed = create_embed(
                title="Product Not Found",
                description=get_text("product_not_found", lang),
                color=Config.ERROR_COLOR
            )
            await ctx.send(embed=embed, delete_after=5)
            return
        
        product = products[0]
        
        await db_service.add_to_wishlist(ctx.author.id, ctx.guild.id, product.id)
        
        embed = create_embed(
            title="Added to Wishlist",
            description=get_text("wishlist_added", lang, item=product.name),
            color=Config.SUCCESS_COLOR
        )
        
        embed.add_field(name="Product", value=product.name, inline=True)
        embed.add_field(name="Price", value=format_price(product.price), inline=True)
        
        await ctx.send(embed=embed)
    
    @commands.command(name="removefromwishlist")
    async def remove_from_wishlist(self, ctx: commands.Context, *, product_name: str):
        wishlist_items = await db_service.get_wishlist(ctx.author.id, ctx.guild.id)
        
        for item in wishlist_items:
            if item.product and product_name.lower() in item.product.name.lower():
                async with db_service.session_factory() as session:
                    from sqlalchemy import delete
                    from src.models.database import WishlistItem
                    await session.execute(
                        delete(WishlistItem).where(WishlistItem.id == item.id)
                    )
                    await session.commit()
                
                embed = create_embed(
                    title="Removed from Wishlist",
                    description=f"**{item.product.name}** has been removed from your wishlist.",
                    color=Config.SUCCESS_COLOR
                )
                await ctx.send(embed=embed)
                return
        
        await ctx.send("Product not found in your wishlist.", delete_after=5)
    
    @commands.command(name="checkout")
    async def checkout(self, ctx: commands.Context):
        user = await db_service.get_or_create_user(ctx.author.id, ctx.guild.id)
        cart_items = await db_service.get_cart(ctx.author.id, ctx.guild.id)
        
        if not cart_items:
            await ctx.send("Your cart is empty. Add items before checking out.", delete_after=5)
            return
        
        items = []
        for item in cart_items:
            if item.product:
                items.append({
                    "product_id": item.product.id,
                    "name": item.product.name,
                    "quantity": item.quantity,
                    "price": item.product.price
                })
        
        order = await db_service.create_order(
            guild_id=ctx.guild.id,
            user_id=user.id,
            items=items
        )
        
        await db_service.clear_cart(ctx.author.id, ctx.guild.id)
        
        embed = create_embed(
            title="Order Placed Successfully!",
            description=f"Your order **{order.order_id}** has been placed!",
            color=Config.SUCCESS_COLOR
        )
        
        items_text = "\n".join([f"- {item['name']} x{item['quantity']}" for item in items])
        embed.add_field(name="Items", value=items_text[:1024], inline=False)
        embed.add_field(name="Total", value=format_price(order.total_amount), inline=True)
        
        embed.set_footer(text=f"Track your order with: !trackorder {order.order_id}")
        
        await ctx.send(embed=embed)
    
    @commands.command(name="products")
    async def list_products(self, ctx: commands.Context, category: str = None):
        products = await db_service.get_products(ctx.guild.id, category=category)
        
        if not products:
            await ctx.send("No products available at the moment.", delete_after=5)
            return
        
        embed = create_embed(
            title="Available Products",
            description=f"Showing {len(products)} product(s)",
            color=Config.EMBED_COLOR
        )
        
        for product in products[:25]:
            product_info = f"**Price:** {format_price(product.price)}\n"
            if product.description:
                product_info += f"{product.description[:100]}..."
            if product.category:
                product_info += f"\n**Category:** {product.category}"
            
            embed.add_field(name=product.name, value=product_info, inline=True)
        
        embed.set_footer(text="Use !addtocart <product> to add to cart")
        
        await ctx.send(embed=embed)
    
    @commands.command(name="search")
    async def search_products(self, ctx: commands.Context, *, search_term: str):
        products = await db_service.search_products(ctx.guild.id, search_term)
        
        if not products:
            await ctx.send(f"No products found matching '{search_term}'.", delete_after=5)
            return
        
        embed = create_embed(
            title=f"Search Results for '{search_term}'",
            description=f"Found {len(products)} product(s)",
            color=Config.EMBED_COLOR
        )
        
        for product in products[:10]:
            product_info = f"**Price:** {format_price(product.price)}\n"
            if product.description:
                product_info += f"{product.description[:100]}..."
            
            embed.add_field(name=product.name, value=product_info, inline=True)
        
        await ctx.send(embed=embed)
    
    @commands.command(name="addproduct")
    @commands.has_permissions(administrator=True)
    async def add_product(self, ctx: commands.Context, name: str, price: float, *, description: str = None):
        product = await db_service.create_product(
            guild_id=ctx.guild.id,
            name=name,
            description=description,
            price=price
        )
        
        embed = create_embed(
            title="Product Added",
            description=f"**{product.name}** has been added to the store!",
            color=Config.SUCCESS_COLOR
        )
        
        embed.add_field(name="Price", value=format_price(product.price), inline=True)
        if description:
            embed.add_field(name="Description", value=description, inline=False)
        
        await ctx.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(CommerceCog(bot))
