import discord
from discord.ext import commands
from datetime import datetime
import pytz

from src.services.database import db_service
from src.models.database import TicketStatus
from src.utils.helpers import create_embed, is_staff, get_eastern_time, format_timestamp, get_status_emoji
from src.utils.translations import get_text
from src.config import Config

class TicketsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
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
    
    @commands.command(name="newticket")
    async def new_ticket(self, ctx: commands.Context, *, subject: str = "General Support"):
        await ctx.message.delete()
        
        user = await db_service.get_or_create_user(
            ctx.author.id, ctx.guild.id, str(ctx.author), ctx.author.display_name
        )
        lang = user.language
        
        category = await self.get_ticket_category(ctx.guild)
        
        overwrites = {
            ctx.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            ctx.author: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            ctx.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
        }
        
        for role in ctx.guild.roles:
            if role.name in ["Staff", "Moderator", "Admin", "Support"]:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        
        channel = await ctx.guild.create_text_channel(
            name=f"ticket-{ctx.author.name}",
            category=category,
            overwrites=overwrites,
            reason=f"Ticket created by {ctx.author}"
        )
        
        ticket = await db_service.create_ticket(
            guild_id=ctx.guild.id,
            user_id=user.id,
            channel_id=channel.id,
            subject=subject,
            category="support"
        )
        
        embed = create_embed(
            title=f"{get_status_emoji('open')} {get_text('ticket_created', lang)}",
            description=f"Thank you for creating a ticket, {ctx.author.mention}!",
            color=Config.EMBED_COLOR
        )
        
        embed.add_field(name="Ticket ID", value=ticket.ticket_id, inline=True)
        embed.add_field(name="Subject", value=subject, inline=True)
        embed.add_field(name="Status", value=f"{get_status_emoji('open')} Open", inline=True)
        embed.add_field(name="Created At", value=format_timestamp(get_eastern_time()), inline=False)
        embed.add_field(
            name="Instructions",
            value="Please describe your issue and a staff member will assist you shortly.\nUse `!closeticket` to close this ticket when resolved.",
            inline=False
        )
        
        embed.set_footer(text=f"BM Creations Support | Ticket: {ticket.ticket_id}")
        
        await channel.send(ctx.author.mention, embed=embed)
        
        confirm = await ctx.send(f"Ticket created! Please check {channel.mention}")
        await confirm.delete(delay=5)
    
    @commands.command(name="closeticket")
    async def close_ticket(self, ctx: commands.Context, *, reason: str = "Resolved"):
        ticket = await db_service.get_ticket(channel_id=ctx.channel.id)
        
        if not ticket:
            await ctx.send("This is not a ticket channel.", delete_after=5)
            return
        
        if ticket.user.discord_id != ctx.author.id and not is_staff(ctx.author):
            await ctx.send("You don't have permission to close this ticket.", delete_after=5)
            return
        
        await db_service.update_ticket_status(ticket.ticket_id, TicketStatus.CLOSED)
        
        embed = create_embed(
            title=f"{get_status_emoji('closed')} Ticket Closed",
            description=f"This ticket has been closed by {ctx.author.mention}",
            color=Config.WARNING_COLOR
        )
        embed.add_field(name="Ticket ID", value=ticket.ticket_id, inline=True)
        embed.add_field(name="Reason", value=reason, inline=True)
        embed.add_field(name="Closed At", value=format_timestamp(get_eastern_time()), inline=False)
        
        await ctx.send(embed=embed)
        
        await ctx.send("This channel will be deleted in 10 seconds...")
        await discord.utils.sleep_until(datetime.utcnow().replace(second=datetime.utcnow().second + 10))
        await ctx.channel.delete(reason=f"Ticket closed: {reason}")
    
    @commands.command(name="viewtickets")
    async def view_tickets(self, ctx: commands.Context):
        await ctx.message.delete()
        
        if not is_staff(ctx.author):
            await ctx.send("You don't have permission to use this command.", delete_after=5)
            return
        
        tickets = await db_service.get_active_tickets(ctx.guild.id)
        
        if not tickets:
            await ctx.send("No active tickets at the moment.", delete_after=5)
            return
        
        embed = create_embed(
            title="Active Tickets",
            description=f"Currently tracking **{len(tickets)}** active ticket(s)",
            color=Config.WARNING_COLOR
        )
        
        for ticket in tickets[:25]:
            status_emoji = get_status_emoji(ticket.status.value)
            ticket_info = f"**Customer:** <@{ticket.user.discord_id}>\n"
            ticket_info += f"**Subject:** {ticket.subject or 'General'}\n"
            ticket_info += f"**Status:** {status_emoji} {ticket.status.value.title()}\n"
            ticket_info += f"**Channel:** <#{ticket.channel_id}>\n"
            ticket_info += f"**Created:** {format_timestamp(ticket.created_at)}"
            
            embed.add_field(name=f"Ticket: {ticket.ticket_id}", value=ticket_info, inline=False)
        
        embed.set_footer(text="Use !closeticket to close a ticket")
        await ctx.send(embed=embed)
    
    @commands.command(name="claimticket")
    async def claim_ticket(self, ctx: commands.Context):
        if not is_staff(ctx.author):
            await ctx.send("You don't have permission to use this command.", delete_after=5)
            return
        
        ticket = await db_service.get_ticket(channel_id=ctx.channel.id)
        
        if not ticket:
            await ctx.send("This is not a ticket channel.", delete_after=5)
            return
        
        await db_service.update_ticket_status(
            ticket.ticket_id, 
            TicketStatus.IN_PROGRESS, 
            assigned_staff_id=ctx.author.id
        )
        
        embed = create_embed(
            title="Ticket Claimed",
            description=f"{ctx.author.mention} has claimed this ticket and will assist you.",
            color=Config.SUCCESS_COLOR
        )
        
        await ctx.send(embed=embed)
    
    @commands.command(name="transferticket")
    async def transfer_ticket(self, ctx: commands.Context, staff_member: discord.Member):
        if not is_staff(ctx.author):
            await ctx.send("You don't have permission to use this command.", delete_after=5)
            return
        
        if not is_staff(staff_member):
            await ctx.send("You can only transfer to staff members.", delete_after=5)
            return
        
        ticket = await db_service.get_ticket(channel_id=ctx.channel.id)
        
        if not ticket:
            await ctx.send("This is not a ticket channel.", delete_after=5)
            return
        
        await db_service.update_ticket_status(
            ticket.ticket_id, 
            TicketStatus.IN_PROGRESS, 
            assigned_staff_id=staff_member.id
        )
        
        embed = create_embed(
            title="Ticket Transferred",
            description=f"This ticket has been transferred to {staff_member.mention}",
            color=Config.EMBED_COLOR
        )
        
        await ctx.send(embed=embed)
    
    @commands.command(name="ticketinfo")
    async def ticket_info(self, ctx: commands.Context):
        ticket = await db_service.get_ticket(channel_id=ctx.channel.id)
        
        if not ticket:
            await ctx.send("This is not a ticket channel.", delete_after=5)
            return
        
        embed = create_embed(
            title=f"Ticket Information: {ticket.ticket_id}",
            color=Config.EMBED_COLOR
        )
        
        embed.add_field(name="Customer", value=f"<@{ticket.user.discord_id}>", inline=True)
        embed.add_field(name="Subject", value=ticket.subject or "General", inline=True)
        embed.add_field(name="Status", value=f"{get_status_emoji(ticket.status.value)} {ticket.status.value.title()}", inline=True)
        embed.add_field(name="Created At", value=format_timestamp(ticket.created_at), inline=True)
        
        if ticket.assigned_staff_id:
            embed.add_field(name="Assigned To", value=f"<@{ticket.assigned_staff_id}>", inline=True)
        
        await ctx.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(TicketsCog(bot))
