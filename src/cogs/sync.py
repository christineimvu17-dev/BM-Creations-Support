import discord
from discord.ext import commands, tasks
import re

from src.services.database import db_service
from src.utils.helpers import create_embed, is_staff
from src.config import Config

class SyncCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    async def parse_product_from_message(self, message: discord.Message) -> dict:
        content = message.content
        
        product_data = {
            "name": None,
            "description": None,
            "price": 0.0,
            "category": None,
            "image_url": None
        }
        
        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            if any(x in line.lower() for x in ['price:', '$', 'cost:']):
                price_match = re.search(r'\$?(\d+(?:\.\d{2})?)', line)
                if price_match:
                    product_data["price"] = float(price_match.group(1))
                continue
            
            if not product_data["name"] and len(line) > 3:
                clean_name = re.sub(r'^[\*\#\-\>\s]+', '', line)
                clean_name = re.sub(r'[\*\#]+$', '', clean_name)
                if clean_name and len(clean_name) <= 100:
                    product_data["name"] = clean_name
                continue
        
        if not product_data["name"] and content:
            first_line = content.split('\n')[0][:100]
            product_data["name"] = re.sub(r'^[\*\#\-\>\s]+', '', first_line).strip()
        
        if message.attachments:
            for attachment in message.attachments:
                if any(attachment.filename.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
                    product_data["image_url"] = attachment.url
                    break
        
        if message.embeds:
            for embed in message.embeds:
                if embed.image:
                    product_data["image_url"] = embed.image.url
                    break
                if embed.thumbnail:
                    product_data["image_url"] = embed.thumbnail.url
                    break
        
        if message.channel.category:
            product_data["category"] = message.channel.category.name
        else:
            product_data["category"] = message.channel.name
        
        remaining_lines = [l for l in lines[1:] if l.strip() and 'price' not in l.lower() and '$' not in l]
        if remaining_lines:
            product_data["description"] = ' '.join(remaining_lines[:3])[:500]
        
        return product_data
    
    @commands.command(name="syncproducts")
    @commands.has_permissions(administrator=True)
    async def sync_products(self, ctx: commands.Context, channel: discord.TextChannel = None):
        target_channel = channel or ctx.channel
        
        progress_msg = await ctx.send(f"Syncing products from {target_channel.mention}... This may take a moment.")
        
        synced_count = 0
        skipped_count = 0
        
        async for message in target_channel.history(limit=100):
            if message.author.bot:
                continue
            
            if len(message.content) < 10 and not message.attachments:
                skipped_count += 1
                continue
            
            product_data = await self.parse_product_from_message(message)
            
            if not product_data["name"]:
                skipped_count += 1
                continue
            
            existing = await db_service.search_products(ctx.guild.id, product_data["name"])
            if existing and any(p.name.lower() == product_data["name"].lower() for p in existing):
                skipped_count += 1
                continue
            
            await db_service.create_product(
                guild_id=ctx.guild.id,
                channel_id=target_channel.id,
                message_id=message.id,
                name=product_data["name"],
                description=product_data["description"],
                price=product_data["price"],
                category=product_data["category"],
                image_url=product_data["image_url"]
            )
            synced_count += 1
        
        embed = create_embed(
            title="Product Sync Complete",
            description=f"Successfully synced products from {target_channel.mention}",
            color=Config.SUCCESS_COLOR
        )
        embed.add_field(name="Products Added", value=str(synced_count), inline=True)
        embed.add_field(name="Skipped", value=str(skipped_count), inline=True)
        
        await progress_msg.edit(content=None, embed=embed)
    
    @commands.command(name="syncallchannels")
    @commands.has_permissions(administrator=True)
    async def sync_all_channels(self, ctx: commands.Context, category: discord.CategoryChannel = None):
        if category:
            channels = category.text_channels
        else:
            channels = ctx.guild.text_channels
        
        progress_msg = await ctx.send(f"Syncing products from {len(channels)} channels... This may take a while.")
        
        total_synced = 0
        total_skipped = 0
        
        for channel in channels:
            try:
                if not channel.permissions_for(ctx.guild.me).read_messages:
                    continue
                
                if any(skip in channel.name.lower() for skip in ['ticket', 'log', 'staff', 'admin', 'mod', 'bot']):
                    continue
                
                async for message in channel.history(limit=50):
                    if message.author.bot:
                        continue
                    
                    if len(message.content) < 10 and not message.attachments:
                        total_skipped += 1
                        continue
                    
                    product_data = await self.parse_product_from_message(message)
                    
                    if not product_data["name"]:
                        total_skipped += 1
                        continue
                    
                    existing = await db_service.search_products(ctx.guild.id, product_data["name"])
                    if existing and any(p.name.lower() == product_data["name"].lower() for p in existing):
                        total_skipped += 1
                        continue
                    
                    await db_service.create_product(
                        guild_id=ctx.guild.id,
                        channel_id=channel.id,
                        message_id=message.id,
                        name=product_data["name"],
                        description=product_data["description"],
                        price=product_data["price"],
                        category=product_data["category"],
                        image_url=product_data["image_url"]
                    )
                    total_synced += 1
                    
            except Exception as e:
                print(f"Error syncing channel {channel.name}: {e}")
                continue
        
        embed = create_embed(
            title="Full Product Sync Complete",
            description=f"Successfully synced products from all channels",
            color=Config.SUCCESS_COLOR
        )
        embed.add_field(name="Channels Scanned", value=str(len(channels)), inline=True)
        embed.add_field(name="Products Added", value=str(total_synced), inline=True)
        embed.add_field(name="Skipped", value=str(total_skipped), inline=True)
        
        await progress_msg.edit(content=None, embed=embed)
    
    @commands.command(name="fetchserver")
    @commands.has_permissions(administrator=True)
    async def fetch_server_data(self, ctx: commands.Context):
        progress_msg = await ctx.send("Fetching server data... Please wait.")
        
        guild = ctx.guild
        
        for member in guild.members:
            if not member.bot:
                await db_service.get_or_create_user(
                    discord_id=member.id,
                    guild_id=guild.id,
                    username=str(member),
                    display_name=member.display_name
                )
        
        settings = await db_service.get_or_create_guild_settings(guild.id)
        
        for channel in guild.text_channels:
            if "order" in channel.name.lower() or "status" in channel.name.lower():
                await db_service.update_guild_settings(guild.id, order_channel_id=channel.id)
                break
        
        for channel in guild.text_channels:
            if "welcome" in channel.name.lower():
                await db_service.update_guild_settings(guild.id, welcome_channel_id=channel.id)
                break
        
        for channel in guild.text_channels:
            if "log" in channel.name.lower():
                await db_service.update_guild_settings(guild.id, log_channel_id=channel.id)
                break
        
        for category in guild.categories:
            if "ticket" in category.name.lower():
                await db_service.update_guild_settings(guild.id, ticket_category_id=category.id)
                break
        
        staff_role_ids = []
        for role in guild.roles:
            if role.name.lower() in ["staff", "moderator", "admin", "support", "owner"]:
                staff_role_ids.append(role.id)
        
        if staff_role_ids:
            await db_service.update_guild_settings(guild.id, staff_role_ids=staff_role_ids)
        
        updated_settings = await db_service.get_or_create_guild_settings(guild.id)
        
        embed = create_embed(
            title="Server Data Fetched",
            description=f"Successfully fetched and configured server data for **{guild.name}**",
            color=Config.SUCCESS_COLOR
        )
        
        embed.add_field(name="Members Synced", value=str(len([m for m in guild.members if not m.bot])), inline=True)
        embed.add_field(name="Text Channels", value=str(len(guild.text_channels)), inline=True)
        embed.add_field(name="Categories", value=str(len(guild.categories)), inline=True)
        
        embed.add_field(
            name="Auto-Detected Channels",
            value=f"""
Order Channel: {f'<#{updated_settings.order_channel_id}>' if updated_settings.order_channel_id else 'Not found'}
Welcome Channel: {f'<#{updated_settings.welcome_channel_id}>' if updated_settings.welcome_channel_id else 'Not found'}
Log Channel: {f'<#{updated_settings.log_channel_id}>' if updated_settings.log_channel_id else 'Not found'}
Ticket Category: {f'<#{updated_settings.ticket_category_id}>' if updated_settings.ticket_category_id else 'Not found'}
            """,
            inline=False
        )
        
        embed.add_field(
            name="Staff Roles Found",
            value=str(len(staff_role_ids)) if staff_role_ids else "None (all admins have staff access)",
            inline=True
        )
        
        embed.add_field(
            name="Next Steps",
            value="Use `!syncproducts #channel` to sync products from specific channels, or `!syncallchannels` to sync from all channels.",
            inline=False
        )
        
        await progress_msg.edit(content=None, embed=embed)
    
    @commands.command(name="clearprodcts")
    @commands.has_permissions(administrator=True)
    async def clear_products(self, ctx: commands.Context):
        async with db_service.session_factory() as session:
            from sqlalchemy import delete
            from src.models.database import Product
            
            await session.execute(
                delete(Product).where(Product.guild_id == ctx.guild.id)
            )
            await session.commit()
        
        embed = create_embed(
            title="Products Cleared",
            description="All products have been removed from the database.",
            color=Config.SUCCESS_COLOR
        )
        await ctx.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(SyncCog(bot))
