import discord
from discord.ext import commands
from datetime import datetime, timedelta

from src.services.database import db_service
from src.utils.helpers import create_embed, is_staff, format_timestamp, get_eastern_time, parse_duration
from src.config import Config

class AnnouncementsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    @commands.command(name="announce")
    @commands.has_permissions(administrator=True)
    async def announce(self, ctx: commands.Context, *, message: str):
        try:
            await ctx.message.delete()
        except:
            pass
        
        embed = create_embed(
            title="Announcement",
            description=message,
            color=Config.EMBED_COLOR
        )
        embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url if ctx.author.display_avatar else None)
        embed.set_footer(text=f"{ctx.guild.name} | {format_timestamp(get_eastern_time())}")
        
        await ctx.send("@everyone", embed=embed)
        
        announcement = await db_service.create_announcement(
            guild_id=ctx.guild.id,
            title="Announcement",
            content=message,
            created_by=ctx.author.id,
            channel_ids=[ctx.channel.id],
            scheduled_at=datetime.utcnow()
        )
        await db_service.mark_announcement_sent(announcement.id)
    
    @commands.command(name="broadcast")
    @commands.has_permissions(administrator=True)
    async def broadcast(self, ctx: commands.Context, *, message: str):
        try:
            await ctx.message.delete()
        except:
            pass
        
        embed = create_embed(
            title="Broadcast",
            description=message,
            color=Config.EMBED_COLOR
        )
        embed.set_author(name=ctx.guild.name, icon_url=ctx.guild.icon.url if ctx.guild.icon else None)
        embed.set_footer(text=format_timestamp(get_eastern_time()))
        
        sent_count = 0
        for channel in ctx.guild.text_channels:
            try:
                if channel.permissions_for(ctx.guild.me).send_messages:
                    await channel.send(embed=embed)
                    sent_count += 1
            except:
                continue
        
        confirm = await ctx.send(f"Broadcast sent to {sent_count} channels!")
        await confirm.delete(delay=5)
    
    @commands.command(name="dmall")
    @commands.has_permissions(administrator=True)
    async def dm_all(self, ctx: commands.Context, *, message: str):
        try:
            await ctx.message.delete()
        except:
            pass
        
        embed = create_embed(
            title=f"Message from {ctx.guild.name}",
            description=message,
            color=Config.EMBED_COLOR
        )
        embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else None)
        embed.set_footer(text=format_timestamp(get_eastern_time()))
        
        sent_count = 0
        failed_count = 0
        
        progress_msg = await ctx.send("Sending DMs... This may take a while.")
        
        for member in ctx.guild.members:
            if not member.bot:
                try:
                    await member.send(embed=embed)
                    sent_count += 1
                except:
                    failed_count += 1
        
        await progress_msg.edit(content=f"DMs sent: {sent_count} successful, {failed_count} failed.")
    
    @commands.command(name="scheduleannounce")
    @commands.has_permissions(administrator=True)
    async def schedule_announce(self, ctx: commands.Context, delay: str, channel: discord.TextChannel, *, message: str):
        try:
            await ctx.message.delete()
        except:
            pass
        
        seconds = parse_duration(delay)
        if not seconds:
            await ctx.send("Invalid duration format. Use: 30m, 1h, 1d, etc.", delete_after=5)
            return
        
        scheduled_time = datetime.utcnow() + timedelta(seconds=seconds)
        
        announcement = await db_service.create_announcement(
            guild_id=ctx.guild.id,
            title="Scheduled Announcement",
            content=message,
            created_by=ctx.author.id,
            channel_ids=[channel.id],
            scheduled_at=scheduled_time
        )
        
        embed = create_embed(
            title="Announcement Scheduled",
            description=f"Your announcement has been scheduled for {channel.mention}",
            color=Config.SUCCESS_COLOR
        )
        embed.add_field(name="Scheduled For", value=format_timestamp(scheduled_time), inline=True)
        embed.add_field(name="Message Preview", value=message[:200] + "..." if len(message) > 200 else message, inline=False)
        
        await ctx.send(embed=embed)
    
    @commands.command(name="poll")
    async def create_poll(self, ctx: commands.Context, question: str, *options):
        try:
            await ctx.message.delete()
        except:
            pass
        
        if len(options) < 2:
            await ctx.send("Please provide at least 2 options for the poll.", delete_after=5)
            return
        
        if len(options) > 10:
            await ctx.send("Maximum 10 options allowed.", delete_after=5)
            return
        
        number_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        
        description = ""
        for i, option in enumerate(options):
            description += f"{number_emojis[i]} {option}\n\n"
        
        embed = create_embed(
            title=f"📊 Poll: {question}",
            description=description,
            color=Config.EMBED_COLOR
        )
        embed.set_author(name=f"Poll by {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url if ctx.author.display_avatar else None)
        embed.set_footer(text="React to vote!")
        
        poll_message = await ctx.send(embed=embed)
        
        for i in range(len(options)):
            await poll_message.add_reaction(number_emojis[i])
    
    @commands.command(name="giveaway")
    @commands.has_permissions(administrator=True)
    async def create_giveaway(self, ctx: commands.Context, duration: str, winners: int, *, prize: str):
        try:
            await ctx.message.delete()
        except:
            pass
        
        seconds = parse_duration(duration)
        if not seconds:
            await ctx.send("Invalid duration format. Use: 30m, 1h, 1d, etc.", delete_after=5)
            return
        
        end_time = datetime.utcnow() + timedelta(seconds=seconds)
        
        embed = create_embed(
            title="🎉 GIVEAWAY 🎉",
            description=f"**Prize:** {prize}\n\nReact with 🎉 to enter!\n\n**Winners:** {winners}\n**Ends:** {format_timestamp(end_time)}",
            color=0xFF69B4
        )
        embed.set_author(name=f"Hosted by {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url if ctx.author.display_avatar else None)
        embed.set_footer(text=f"Ends at")
        embed.timestamp = end_time
        
        giveaway_msg = await ctx.send(embed=embed)
        await giveaway_msg.add_reaction("🎉")
        
        await db_service.create_reminder(
            guild_id=ctx.guild.id,
            user_discord_id=ctx.author.id,
            channel_id=ctx.channel.id,
            message=f"GIVEAWAY_END|{giveaway_msg.id}|{winners}|{prize}",
            scheduled_at=end_time
        )
    
    @commands.command(name="embed")
    @commands.has_permissions(manage_messages=True)
    async def create_embed(self, ctx: commands.Context, title: str, *, content: str):
        try:
            await ctx.message.delete()
        except:
            pass
        
        parts = content.split("|")
        description = parts[0].strip()
        
        color = Config.EMBED_COLOR
        if len(parts) > 1:
            try:
                color = int(parts[1].strip().replace("#", ""), 16)
            except:
                pass
        
        embed = create_embed(
            title=title,
            description=description,
            color=color
        )
        
        if len(parts) > 2:
            footer = parts[2].strip()
            embed.set_footer(text=footer)
        
        await ctx.send(embed=embed)
    
    @commands.command(name="say")
    @commands.has_permissions(manage_messages=True)
    async def say(self, ctx: commands.Context, *, message: str):
        try:
            await ctx.message.delete()
        except:
            pass
        await ctx.send(message)
    
    @commands.command(name="editmessage")
    @commands.has_permissions(manage_messages=True)
    async def edit_message(self, ctx: commands.Context, message_id: int, *, new_content: str):
        try:
            await ctx.message.delete()
        except:
            pass
        
        try:
            message = await ctx.channel.fetch_message(message_id)
            
            if message.author != self.bot.user:
                await ctx.send("I can only edit my own messages.", delete_after=5)
                return
            
            await message.edit(content=new_content)
            
            confirm = await ctx.send("Message edited successfully!")
            await confirm.delete(delay=3)
            
        except discord.NotFound:
            await ctx.send("Message not found.", delete_after=5)
        except Exception as e:
            await ctx.send(f"Error: {str(e)}", delete_after=5)

async def setup(bot: commands.Bot):
    await bot.add_cog(AnnouncementsCog(bot))
