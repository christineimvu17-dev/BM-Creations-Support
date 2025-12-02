import discord
from discord.ext import commands
from datetime import datetime, timedelta

from src.services.database import db_service
from src.models.database import WarningLevel
from src.utils.helpers import create_embed, is_staff, format_timestamp, get_eastern_time, parse_duration
from src.config import Config

class ModerationCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    @commands.command(name="warn")
    @commands.has_permissions(kick_members=True)
    async def warn_user(self, ctx: commands.Context, member: discord.Member, *, reason: str):
        await ctx.message.delete()
        
        if member.bot:
            await ctx.send("Cannot warn bots.", delete_after=5)
            return
        
        if member.top_role >= ctx.author.top_role:
            await ctx.send("Cannot warn someone with equal or higher role.", delete_after=5)
            return
        
        user = await db_service.get_or_create_user(member.id, ctx.guild.id, str(member), member.display_name)
        
        existing_warnings = await db_service.get_user_warnings(member.id, ctx.guild.id)
        warning_count = len(existing_warnings)
        
        if warning_count >= 2:
            level = WarningLevel.FINAL
        elif warning_count >= 1:
            level = WarningLevel.WRITTEN
        else:
            level = WarningLevel.VERBAL
        
        warning = await db_service.add_warning(
            guild_id=ctx.guild.id,
            user_id=user.id,
            moderator_id=ctx.author.id,
            reason=reason,
            level=level
        )
        
        embed = create_embed(
            title="Warning Issued",
            description=f"{member.mention} has received a warning.",
            color=Config.WARNING_COLOR
        )
        
        embed.add_field(name="User", value=member.mention, inline=True)
        embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
        embed.add_field(name="Level", value=level.value.title(), inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="Total Warnings", value=str(warning_count + 1), inline=True)
        
        await ctx.send(embed=embed)
        
        try:
            dm_embed = create_embed(
                title=f"Warning from {ctx.guild.name}",
                description=f"You have received a **{level.value.title()}** warning.",
                color=Config.WARNING_COLOR
            )
            dm_embed.add_field(name="Reason", value=reason, inline=False)
            dm_embed.add_field(name="Total Warnings", value=str(warning_count + 1), inline=True)
            
            if warning_count + 1 >= 3:
                dm_embed.add_field(
                    name="Final Warning",
                    value="This is your final warning. Further violations may result in a ban.",
                    inline=False
                )
            
            await member.send(embed=dm_embed)
        except:
            pass
        
        settings = await db_service.get_or_create_guild_settings(ctx.guild.id)
        if settings.log_channel_id:
            log_channel = self.bot.get_channel(settings.log_channel_id)
            if log_channel:
                await log_channel.send(embed=embed)
    
    @commands.command(name="warnings")
    async def view_warnings(self, ctx: commands.Context, member: discord.Member = None):
        target = member or ctx.author
        
        if member and member != ctx.author and not is_staff(ctx.author):
            await ctx.send("You can only view your own warnings.", delete_after=5)
            return
        
        warnings = await db_service.get_user_warnings(target.id, ctx.guild.id)
        
        if not warnings:
            embed = create_embed(
                title=f"Warnings for {target.display_name}",
                description="No active warnings.",
                color=Config.SUCCESS_COLOR
            )
            await ctx.send(embed=embed)
            return
        
        embed = create_embed(
            title=f"Warnings for {target.display_name}",
            description=f"Total active warnings: **{len(warnings)}**",
            color=Config.WARNING_COLOR
        )
        
        for i, warning in enumerate(warnings[:10], 1):
            warning_info = f"**Level:** {warning.level.value.title()}\n"
            warning_info += f"**Reason:** {warning.reason[:100]}\n"
            warning_info += f"**Date:** {format_timestamp(warning.created_at, '%m/%d/%Y')}\n"
            warning_info += f"**Moderator:** <@{warning.moderator_id}>"
            
            embed.add_field(name=f"Warning #{i}", value=warning_info, inline=False)
        
        await ctx.send(embed=embed)
    
    @commands.command(name="clearwarnings")
    @commands.has_permissions(administrator=True)
    async def clear_warnings(self, ctx: commands.Context, member: discord.Member):
        async with db_service.session_factory() as session:
            from sqlalchemy import select, update
            from src.models.database import Warning, User
            
            user_result = await session.execute(
                select(User).where(User.discord_id == member.id, User.guild_id == ctx.guild.id)
            )
            user = user_result.scalar_one_or_none()
            
            if user:
                await session.execute(
                    update(Warning)
                    .where(Warning.user_id == user.id, Warning.is_active == True)
                    .values(is_active=False)
                )
                await session.commit()
        
        embed = create_embed(
            title="Warnings Cleared",
            description=f"All warnings for {member.mention} have been cleared.",
            color=Config.SUCCESS_COLOR
        )
        embed.add_field(name="Cleared by", value=ctx.author.mention, inline=True)
        
        await ctx.send(embed=embed)
    
    @commands.command(name="mute")
    @commands.has_permissions(manage_roles=True)
    async def mute_user(self, ctx: commands.Context, member: discord.Member, duration: str = "1h", *, reason: str = "No reason provided"):
        await ctx.message.delete()
        
        seconds = parse_duration(duration)
        if not seconds:
            await ctx.send("Invalid duration format. Use: 30m, 1h, 1d, etc.", delete_after=5)
            return
        
        muted_role = discord.utils.get(ctx.guild.roles, name="Muted")
        
        if not muted_role:
            muted_role = await ctx.guild.create_role(
                name="Muted",
                reason="Created for mute command"
            )
            for channel in ctx.guild.channels:
                await channel.set_permissions(muted_role, send_messages=False, speak=False)
        
        await member.add_roles(muted_role, reason=reason)
        
        embed = create_embed(
            title="User Muted",
            description=f"{member.mention} has been muted.",
            color=Config.WARNING_COLOR
        )
        embed.add_field(name="Duration", value=duration, inline=True)
        embed.add_field(name="Reason", value=reason, inline=True)
        embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
        
        await ctx.send(embed=embed)
        
        try:
            dm_embed = create_embed(
                title=f"Muted in {ctx.guild.name}",
                description=f"You have been muted for **{duration}**.",
                color=Config.WARNING_COLOR
            )
            dm_embed.add_field(name="Reason", value=reason, inline=False)
            await member.send(embed=dm_embed)
        except:
            pass
    
    @commands.command(name="unmute")
    @commands.has_permissions(manage_roles=True)
    async def unmute_user(self, ctx: commands.Context, member: discord.Member):
        muted_role = discord.utils.get(ctx.guild.roles, name="Muted")
        
        if not muted_role or muted_role not in member.roles:
            await ctx.send(f"{member.display_name} is not muted.", delete_after=5)
            return
        
        await member.remove_roles(muted_role)
        
        embed = create_embed(
            title="User Unmuted",
            description=f"{member.mention} has been unmuted.",
            color=Config.SUCCESS_COLOR
        )
        embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
        
        await ctx.send(embed=embed)
    
    @commands.command(name="kick")
    @commands.has_permissions(kick_members=True)
    async def kick_user(self, ctx: commands.Context, member: discord.Member, *, reason: str = "No reason provided"):
        await ctx.message.delete()
        
        if member.top_role >= ctx.author.top_role:
            await ctx.send("Cannot kick someone with equal or higher role.", delete_after=5)
            return
        
        try:
            dm_embed = create_embed(
                title=f"Kicked from {ctx.guild.name}",
                description="You have been kicked from the server.",
                color=Config.ERROR_COLOR
            )
            dm_embed.add_field(name="Reason", value=reason, inline=False)
            await member.send(embed=dm_embed)
        except:
            pass
        
        await member.kick(reason=f"{reason} | Kicked by {ctx.author}")
        
        embed = create_embed(
            title="User Kicked",
            description=f"**{member}** has been kicked from the server.",
            color=Config.ERROR_COLOR
        )
        embed.add_field(name="Reason", value=reason, inline=True)
        embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
        
        await ctx.send(embed=embed)
    
    @commands.command(name="ban")
    @commands.has_permissions(ban_members=True)
    async def ban_user(self, ctx: commands.Context, member: discord.Member, *, reason: str = "No reason provided"):
        await ctx.message.delete()
        
        if member.top_role >= ctx.author.top_role:
            await ctx.send("Cannot ban someone with equal or higher role.", delete_after=5)
            return
        
        try:
            dm_embed = create_embed(
                title=f"Banned from {ctx.guild.name}",
                description="You have been banned from the server.",
                color=Config.ERROR_COLOR
            )
            dm_embed.add_field(name="Reason", value=reason, inline=False)
            await member.send(embed=dm_embed)
        except:
            pass
        
        await member.ban(reason=f"{reason} | Banned by {ctx.author}")
        
        embed = create_embed(
            title="User Banned",
            description=f"**{member}** has been banned from the server.",
            color=Config.ERROR_COLOR
        )
        embed.add_field(name="Reason", value=reason, inline=True)
        embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
        
        await ctx.send(embed=embed)
    
    @commands.command(name="purge")
    @commands.has_permissions(manage_messages=True)
    async def purge_messages(self, ctx: commands.Context, amount: int):
        if amount > 100:
            await ctx.send("Cannot delete more than 100 messages at once.", delete_after=5)
            return
        
        deleted = await ctx.channel.purge(limit=amount + 1)
        
        msg = await ctx.send(f"Deleted {len(deleted) - 1} messages.")
        await msg.delete(delay=3)

async def setup(bot: commands.Bot):
    await bot.add_cog(ModerationCog(bot))
