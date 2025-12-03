import discord
from discord.ext import commands
from discord import app_commands
import re

from src.services.database import db_service
from src.utils.helpers import create_embed, is_staff
from src.config import Config

class SyncCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.owner_username = "sizuka42"
    
    def is_owner_message(self, message: discord.Message) -> bool:
        username_lower = message.author.name.lower()
        display_lower = message.author.display_name.lower() if message.author.display_name else ""
        
        return (self.owner_username in username_lower or 
                self.owner_username in display_lower or
                "sizuka" in username_lower or
                "sizuka" in display_lower)
    
    async def parse_product_from_message(self, message: discord.Message) -> dict:
        content = message.content
        
        product_data = {
            "name": None,
            "description": None,
            "price": 0.0,
            "category": None,
            "image_url": None,
            "extra_data": {}
        }
        
        lines = content.split('\n')
        name_found = False
        description_lines = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            if any(x in line.lower() for x in ['price:', 'price ', '$', 'cost:', 'cost ']):
                price_match = re.search(r'\$?\s*(\d+(?:\.\d{2})?)', line)
                if price_match:
                    product_data["price"] = float(price_match.group(1))
                continue
            
            if not name_found and len(line) > 3:
                clean_name = re.sub(r'^[\*\#\-\>\s\:]+', '', line)
                clean_name = re.sub(r'[\*\#]+$', '', clean_name)
                if clean_name and len(clean_name) <= 100:
                    product_data["name"] = clean_name.strip()
                    name_found = True
                continue
            
            if name_found and len(line) > 5:
                description_lines.append(line)
        
        if not product_data["name"] and content:
            first_line = content.split('\n')[0][:100]
            product_data["name"] = re.sub(r'^[\*\#\-\>\s]+', '', first_line).strip()
        
        if description_lines:
            product_data["description"] = '\n'.join(description_lines[:5])[:500]
        
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
        
        product_data["extra_data"] = {
            "channel_name": message.channel.name,
            "message_id": message.id,
            "message_url": message.jump_url
        }
        
        return product_data
    
    @app_commands.command(name="syncall", description="Sync all products from all channels (Owner messages only)")
    @app_commands.default_permissions(administrator=True)
    async def sync_all(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        guild = interaction.guild
        channels = guild.text_channels
        
        total_synced = 0
        total_skipped = 0
        channels_processed = 0
        owner_messages_found = 0
        
        progress_embed = create_embed(
            title="🔄 Syncing Products...",
            description=f"Scanning {len(channels)} channels for messages from **@{self.owner_username}**...\n\nThis may take a few minutes.",
            color=Config.EMBED_COLOR
        )
        await interaction.followup.send(embed=progress_embed)
        
        for channel in channels:
            try:
                if not channel.permissions_for(guild.me).read_message_history:
                    continue
                
                if any(skip in channel.name.lower() for skip in ['ticket', 'log', 'staff-', 'admin-', 'mod-', 'bot-']):
                    continue
                
                channels_processed += 1
                
                async for message in channel.history(limit=200):
                    if message.author.bot:
                        continue
                    
                    if not self.is_owner_message(message):
                        continue
                    
                    owner_messages_found += 1
                    
                    if len(message.content) < 5 and not message.attachments:
                        total_skipped += 1
                        continue
                    
                    product_data = await self.parse_product_from_message(message)
                    
                    if not product_data["name"] or len(product_data["name"]) < 3:
                        total_skipped += 1
                        continue
                    
                    existing = await db_service.search_products(guild.id, product_data["name"])
                    if existing and any(p.name.lower() == product_data["name"].lower() for p in existing):
                        total_skipped += 1
                        continue
                    
                    await db_service.create_product(
                        guild_id=guild.id,
                        name=product_data["name"],
                        description=product_data["description"],
                        price=product_data["price"],
                        category=product_data["category"],
                        image_url=product_data["image_url"],
                        extra_data=product_data["extra_data"]
                    )
                    total_synced += 1
                    
            except Exception as e:
                print(f"Error syncing channel {channel.name}: {e}")
                continue
        
        embed = create_embed(
            title="✅ Product Sync Complete!",
            description=f"Successfully synced products from **@{self.owner_username}**'s messages",
            color=Config.SUCCESS_COLOR
        )
        embed.add_field(name="📁 Channels Scanned", value=str(channels_processed), inline=True)
        embed.add_field(name="💬 Owner Messages", value=str(owner_messages_found), inline=True)
        embed.add_field(name="🛍️ Products Added", value=str(total_synced), inline=True)
        embed.add_field(name="⏭️ Skipped", value=str(total_skipped), inline=True)
        embed.set_footer(text="Products are now available for the bot to help customers!")
        
        await interaction.edit_original_response(embed=embed)
    
    @app_commands.command(name="syncchannel", description="Sync products from a specific channel (Owner messages only)")
    @app_commands.describe(channel="The channel to sync products from")
    @app_commands.default_permissions(administrator=True)
    async def sync_channel(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        await interaction.response.defer()
        
        target_channel = channel or interaction.channel
        
        synced_count = 0
        skipped_count = 0
        owner_messages = 0
        
        async for message in target_channel.history(limit=200):
            if message.author.bot:
                continue
            
            if not self.is_owner_message(message):
                continue
            
            owner_messages += 1
            
            if len(message.content) < 5 and not message.attachments:
                skipped_count += 1
                continue
            
            product_data = await self.parse_product_from_message(message)
            
            if not product_data["name"]:
                skipped_count += 1
                continue
            
            existing = await db_service.search_products(interaction.guild.id, product_data["name"])
            if existing and any(p.name.lower() == product_data["name"].lower() for p in existing):
                skipped_count += 1
                continue
            
            await db_service.create_product(
                guild_id=interaction.guild.id,
                name=product_data["name"],
                description=product_data["description"],
                price=product_data["price"],
                category=product_data["category"],
                image_url=product_data["image_url"],
                extra_data=product_data["extra_data"]
            )
            synced_count += 1
        
        embed = create_embed(
            title="✅ Channel Sync Complete!",
            description=f"Synced products from {target_channel.mention}",
            color=Config.SUCCESS_COLOR
        )
        embed.add_field(name="Owner Messages", value=str(owner_messages), inline=True)
        embed.add_field(name="Products Added", value=str(synced_count), inline=True)
        embed.add_field(name="Skipped", value=str(skipped_count), inline=True)
        
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="fetchserver", description="Fetch and configure server data")
    @app_commands.default_permissions(administrator=True)
    async def fetch_server(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        guild = interaction.guild
        
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
        
        for channel in guild.text_channels:
            if "support" in channel.name.lower() or "help" in channel.name.lower():
                await db_service.update_guild_settings(guild.id, support_channel_id=channel.id)
                break
        
        for category in guild.categories:
            if "ticket" in category.name.lower():
                await db_service.update_guild_settings(guild.id, ticket_category_id=category.id)
                break
        
        staff_role_ids = []
        founder_role_ids = []
        admin_role_ids = []
        
        for role in guild.roles:
            role_lower = role.name.lower()
            if role_lower in ["founder", "owner"]:
                founder_role_ids.append(role.id)
            elif role_lower in ["admin", "administrator"]:
                admin_role_ids.append(role.id)
            elif role_lower in ["staff", "moderator", "support", "mod"]:
                staff_role_ids.append(role.id)
        
        if founder_role_ids:
            await db_service.update_guild_settings(guild.id, founder_role_ids=founder_role_ids)
        if admin_role_ids:
            await db_service.update_guild_settings(guild.id, admin_role_ids=admin_role_ids)
        if staff_role_ids:
            await db_service.update_guild_settings(guild.id, staff_role_ids=staff_role_ids)
        
        updated_settings = await db_service.get_or_create_guild_settings(guild.id)
        
        embed = create_embed(
            title="✅ Server Data Fetched!",
            description=f"Successfully configured **{guild.name}**",
            color=Config.SUCCESS_COLOR
        )
        
        embed.add_field(name="👥 Members Synced", value=str(len([m for m in guild.members if not m.bot])), inline=True)
        embed.add_field(name="📁 Text Channels", value=str(len(guild.text_channels)), inline=True)
        embed.add_field(name="📂 Categories", value=str(len(guild.categories)), inline=True)
        
        channels_info = []
        if updated_settings.order_channel_id:
            channels_info.append(f"📦 Orders: <#{updated_settings.order_channel_id}>")
        if updated_settings.welcome_channel_id:
            channels_info.append(f"👋 Welcome: <#{updated_settings.welcome_channel_id}>")
        if updated_settings.support_channel_id:
            channels_info.append(f"💬 Support: <#{updated_settings.support_channel_id}>")
        if updated_settings.ticket_category_id:
            channels_info.append(f"🎫 Tickets: <#{updated_settings.ticket_category_id}>")
        
        embed.add_field(
            name="🔧 Auto-Configured",
            value='\n'.join(channels_info) if channels_info else "No special channels detected",
            inline=False
        )
        
        roles_info = []
        if founder_role_ids:
            roles_info.append(f"👑 Founder roles: {len(founder_role_ids)}")
        if admin_role_ids:
            roles_info.append(f"⚡ Admin roles: {len(admin_role_ids)}")
        if staff_role_ids:
            roles_info.append(f"🛡️ Staff roles: {len(staff_role_ids)}")
        
        embed.add_field(
            name="👮 Roles Configured",
            value='\n'.join(roles_info) if roles_info else "Using admin permissions",
            inline=False
        )
        
        embed.add_field(
            name="📋 Next Steps",
            value="Use `/syncall` to sync all products from your messages, or `/syncchannel` for a specific channel.",
            inline=False
        )
        
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="listproducts", description="View all synced products")
    async def list_products(self, interaction: discord.Interaction):
        products = await db_service.get_all_products(interaction.guild.id)
        
        if not products:
            await interaction.response.send_message("No products synced yet. Use `/syncall` to sync products from your channels.", ephemeral=True)
            return
        
        embed = create_embed(
            title=f"🛍️ Products ({len(products)} total)",
            description="Here are all synced products:",
            color=Config.EMBED_COLOR
        )
        
        for i, product in enumerate(products[:15]):
            price_text = f"${product.price:.2f}" if product.price else "Contact for price"
            value = f"**Price:** {price_text}\n**Category:** {product.category or 'General'}"
            if product.description:
                value += f"\n{product.description[:80]}..."
            embed.add_field(name=f"{i+1}. {product.name}", value=value, inline=False)
        
        if len(products) > 15:
            embed.set_footer(text=f"Showing 15 of {len(products)} products")
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="clearproducts", description="Clear all products from database (Admin)")
    @app_commands.default_permissions(administrator=True)
    async def clear_products(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        async with db_service.session_factory() as session:
            from sqlalchemy import delete
            from src.models.database import Product
            
            result = await session.execute(
                delete(Product).where(Product.guild_id == interaction.guild.id)
            )
            await session.commit()
        
        embed = create_embed(
            title="🗑️ Products Cleared",
            description="All products have been removed from the database. Use `/syncall` to re-sync.",
            color=Config.SUCCESS_COLOR
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="addproduct", description="Manually add a product (Admin)")
    @app_commands.describe(
        name="Product name",
        price="Price in dollars",
        category="Product category",
        description="Product description"
    )
    @app_commands.default_permissions(administrator=True)
    async def add_product(self, interaction: discord.Interaction, name: str, price: float = 0.0, category: str = "General", description: str = None):
        existing = await db_service.search_products(interaction.guild.id, name)
        if existing and any(p.name.lower() == name.lower() for p in existing):
            await interaction.response.send_message(f"A product named **{name}** already exists!", ephemeral=True)
            return
        
        await db_service.create_product(
            guild_id=interaction.guild.id,
            name=name,
            description=description,
            price=price,
            category=category
        )
        
        embed = create_embed(
            title="✅ Product Added!",
            description=f"**{name}** has been added to the product catalog.",
            color=Config.SUCCESS_COLOR
        )
        embed.add_field(name="Price", value=f"${price:.2f}", inline=True)
        embed.add_field(name="Category", value=category, inline=True)
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="serverstats", description="View detailed server and product statistics")
    async def server_stats(self, interaction: discord.Interaction):
        guild = interaction.guild
        settings = await db_service.get_or_create_guild_settings(guild.id)
        products = await db_service.get_all_products(guild.id)
        
        embed = create_embed(
            title=f"ℹ️ {guild.name}",
            description=guild.description or "Welcome to our server!",
            color=Config.EMBED_COLOR,
            thumbnail_url=guild.icon.url if guild.icon else None
        )
        
        embed.add_field(name="👥 Members", value=str(guild.member_count), inline=True)
        embed.add_field(name="📁 Channels", value=str(len(guild.text_channels)), inline=True)
        embed.add_field(name="🛍️ Products", value=str(len(products)), inline=True)
        
        if guild.owner:
            embed.add_field(name="👑 Owner", value=guild.owner.mention, inline=True)
        
        embed.add_field(name="📅 Created", value=guild.created_at.strftime("%B %d, %Y"), inline=True)
        embed.add_field(name="🚀 Boost Level", value=f"Level {guild.premium_tier}", inline=True)
        
        categories = set()
        for product in products:
            if product.category:
                categories.add(product.category)
        
        if categories:
            embed.add_field(name="📦 Product Categories", value=", ".join(sorted(categories)[:5]), inline=False)
        
        await interaction.response.send_message(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(SyncCog(bot))
