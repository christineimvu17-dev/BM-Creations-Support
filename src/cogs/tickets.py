import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import pytz

from src.services.database import db_service
from src.models.database import TicketStatus
from src.utils.helpers import create_embed, is_staff, get_eastern_time, format_timestamp, get_status_emoji
from src.utils.translations import get_text
from src.config import Config

OWNER_USERNAME = "sizuka42"
MAX_TICKETS_PER_USER = 2

class TicketsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    async def get_owner_member(self, guild: discord.Guild) -> discord.Member:
        for member in guild.members:
            if member.name.lower() == OWNER_USERNAME:
                return member
        return None
    
    async def get_ticket_category(self, guild: discord.Guild) -> discord.CategoryChannel:
        settings = await db_service.get_or_create_guild_settings(guild.id)
        
        if settings.ticket_category_id:
            category = guild.get_channel(settings.ticket_category_id)
            if category:
                return category
        
        for cat in guild.categories:
            if "ticket" in cat.name.lower():
                return cat
        
        category = await guild.create_category(
            name="Tickets",
            reason="Created for ticket system"
        )
        await db_service.update_guild_settings(guild.id, ticket_category_id=category.id)
        return category
    
    async def count_user_open_tickets(self, user_id: int, guild_id: int) -> int:
        tickets = await db_service.get_user_tickets(user_id, guild_id)
        if not tickets:
            return 0
        open_statuses = [TicketStatus.OPEN, TicketStatus.IN_PROGRESS, TicketStatus.PENDING]
        open_tickets = [t for t in tickets if t.status in open_statuses]
        return len(open_tickets)
    
    @app_commands.command(name="newticket", description="Create a new support ticket")
    @app_commands.describe(subject="The subject/reason for your ticket")
    async def new_ticket(self, interaction: discord.Interaction, subject: str = "General Support"):
        await interaction.response.defer(ephemeral=True)
        
        user = await db_service.get_or_create_user(
            interaction.user.id, interaction.guild.id, str(interaction.user), interaction.user.display_name
        )
        lang = user.language
        
        open_ticket_count = await self.count_user_open_tickets(user.id, interaction.guild.id)
        
        if open_ticket_count >= MAX_TICKETS_PER_USER:
            embed = create_embed(
                title="⚠️ Ticket Limit Reached",
                description=f"You already have **{open_ticket_count} open tickets**.\n\nPlease wait for your existing tickets to be closed before creating a new one.",
                color=Config.WARNING_COLOR
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        category = await self.get_ticket_category(interaction.guild)
        
        owner = await self.get_owner_member(interaction.guild)
        
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            interaction.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
        }
        
        if owner:
            overwrites[owner] = discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_messages=True)
        
        for role in interaction.guild.roles:
            if role.name.lower() in ["staff", "moderator", "admin", "support", "founder"]:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        
        safe_username = interaction.user.name[:20].replace(" ", "-").lower()
        channel = await interaction.guild.create_text_channel(
            name=f"{safe_username}-pending",
            category=category,
            overwrites=overwrites,
            reason=f"Ticket created by {interaction.user}"
        )
        
        ticket = await db_service.create_ticket(
            guild_id=interaction.guild.id,
            user_id=user.id,
            channel_id=channel.id,
            subject=subject,
            category="support"
        )
        
        embed = create_embed(
            title=f"🎫 {get_text('ticket_created', lang)}",
            description=f"Welcome {interaction.user.mention}!\n\n**Staff will be with you shortly!**",
            color=Config.EMBED_COLOR
        )
        
        embed.add_field(name="🆔 Ticket ID", value=ticket.ticket_id, inline=True)
        embed.add_field(name="📋 Subject", value=subject, inline=True)
        embed.add_field(name="📦 Status", value="🟢 **Open**", inline=True)
        embed.add_field(name="🕐 Created At", value=format_timestamp(get_eastern_time()), inline=False)
        embed.set_footer(text=f"BM Creations Market | Ticket: {ticket.ticket_id}")
        
        mentions = interaction.user.mention
        if owner:
            mentions += f" | Owner: {owner.mention}"
        
        await channel.send(mentions, embed=embed)
        
        support_cog = self.bot.get_cog("SupportInteractionCog")
        if support_cog:
            await support_cog.send_ticket_welcome(channel, interaction.user)
        
        if owner:
            try:
                dm_embed = create_embed(
                    title="🎫 New Ticket Created",
                    description=f"**{interaction.user}** created a new ticket!",
                    color=Config.EMBED_COLOR
                )
                dm_embed.add_field(name="Subject", value=subject, inline=True)
                dm_embed.add_field(name="Channel", value=channel.mention, inline=True)
                await owner.send(embed=dm_embed)
            except:
                pass
        
        await interaction.followup.send(f"✅ Ticket created! Please check {channel.mention}", ephemeral=True)
    
    @app_commands.command(name="closeticket", description="Close the current ticket")
    @app_commands.describe(reason="Reason for closing the ticket")
    async def close_ticket(self, interaction: discord.Interaction, reason: str = "Resolved"):
        ticket = await db_service.get_ticket(channel_id=interaction.channel.id)
        
        if not ticket:
            await interaction.response.send_message("This is not a ticket channel.", ephemeral=True)
            return
        
        if ticket.user.discord_id != interaction.user.id and not is_staff(interaction.user):
            await interaction.response.send_message("You don't have permission to close this ticket.", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        await db_service.update_ticket_status(ticket.ticket_id, TicketStatus.CLOSED)
        
        embed = create_embed(
            title="🔒 Ticket Closed",
            description=f"This ticket has been closed by {interaction.user.mention}",
            color=Config.WARNING_COLOR
        )
        embed.add_field(name="Ticket ID", value=ticket.ticket_id, inline=True)
        embed.add_field(name="Reason", value=reason, inline=True)
        embed.add_field(name="Closed At", value=format_timestamp(get_eastern_time()), inline=False)
        
        await interaction.followup.send(embed=embed)
        
        await interaction.channel.send("This channel will be deleted in 10 seconds...")
        await discord.utils.sleep_until(datetime.utcnow().replace(second=datetime.utcnow().second + 10))
        await interaction.channel.delete(reason=f"Ticket closed: {reason}")
    
    @app_commands.command(name="viewtickets", description="View all open tickets (Staff only)")
    @app_commands.default_permissions(manage_messages=True)
    async def view_tickets(self, interaction: discord.Interaction):
        if not is_staff(interaction.user):
            await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
            return
        
        tickets = await db_service.get_guild_tickets(interaction.guild.id, status=TicketStatus.OPEN)
        
        if not tickets:
            await interaction.response.send_message("No open tickets found.", ephemeral=True)
            return
        
        embed = create_embed(
            title=f"🎫 Open Tickets ({len(tickets)} total)",
            description="Here are all open tickets:",
            color=Config.EMBED_COLOR
        )
        
        for ticket in tickets[:10]:
            channel = interaction.guild.get_channel(ticket.channel_id)
            channel_mention = channel.mention if channel else "Deleted Channel"
            
            ticket_info = f"**User:** <@{ticket.user.discord_id}>\n"
            ticket_info += f"**Subject:** {ticket.subject}\n"
            ticket_info += f"**Channel:** {channel_mention}\n"
            ticket_info += f"**Created:** {format_timestamp(ticket.created_at, '%m/%d %H:%M')}"
            
            embed.add_field(name=f"Ticket: {ticket.ticket_id}", value=ticket_info, inline=False)
        
        if len(tickets) > 10:
            embed.set_footer(text=f"Showing 10 of {len(tickets)} tickets")
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="claimticket", description="Claim a ticket to handle it (Staff only)")
    @app_commands.default_permissions(manage_messages=True)
    async def claim_ticket(self, interaction: discord.Interaction):
        if not is_staff(interaction.user):
            await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
            return
        
        ticket = await db_service.get_ticket(channel_id=interaction.channel.id)
        
        if not ticket:
            await interaction.response.send_message("This is not a ticket channel.", ephemeral=True)
            return
        
        await db_service.update_ticket_status(ticket.ticket_id, TicketStatus.IN_PROGRESS)
        
        embed = create_embed(
            title="✅ Ticket Claimed",
            description=f"{interaction.user.mention} is now handling this ticket.",
            color=Config.SUCCESS_COLOR
        )
        embed.add_field(name="Staff Member", value=interaction.user.mention, inline=True)
        embed.add_field(name="Claimed At", value=format_timestamp(get_eastern_time()), inline=True)
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="transferticket", description="Transfer a ticket to another staff member")
    @app_commands.describe(member="The staff member to transfer the ticket to")
    @app_commands.default_permissions(manage_messages=True)
    async def transfer_ticket(self, interaction: discord.Interaction, member: discord.Member):
        if not is_staff(interaction.user):
            await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
            return
        
        ticket = await db_service.get_ticket(channel_id=interaction.channel.id)
        
        if not ticket:
            await interaction.response.send_message("This is not a ticket channel.", ephemeral=True)
            return
        
        await interaction.channel.set_permissions(member, read_messages=True, send_messages=True)
        
        embed = create_embed(
            title="🔄 Ticket Transferred",
            description=f"This ticket has been transferred to {member.mention}",
            color=Config.EMBED_COLOR
        )
        embed.add_field(name="From", value=interaction.user.mention, inline=True)
        embed.add_field(name="To", value=member.mention, inline=True)
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="addtoticket", description="Add a user to the current ticket")
    @app_commands.describe(member="The user to add to this ticket")
    async def add_to_ticket(self, interaction: discord.Interaction, member: discord.Member):
        ticket = await db_service.get_ticket(channel_id=interaction.channel.id)
        
        if not ticket:
            await interaction.response.send_message("This is not a ticket channel.", ephemeral=True)
            return
        
        if ticket.user.discord_id != interaction.user.id and not is_staff(interaction.user):
            await interaction.response.send_message("You don't have permission to add users to this ticket.", ephemeral=True)
            return
        
        await interaction.channel.set_permissions(member, read_messages=True, send_messages=True)
        
        embed = create_embed(
            title="➕ User Added to Ticket",
            description=f"{member.mention} has been added to this ticket by {interaction.user.mention}",
            color=Config.SUCCESS_COLOR
        )
        
        await interaction.response.send_message(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(TicketsCog(bot))
