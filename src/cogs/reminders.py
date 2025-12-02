import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta
import pytz

from src.services.database import db_service
from src.utils.helpers import create_embed, format_timestamp, get_eastern_time, parse_duration
from src.utils.translations import get_text
from src.config import Config

class RemindersCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.check_reminders.start()
        self.check_announcements.start()
    
    def cog_unload(self):
        self.check_reminders.cancel()
        self.check_announcements.cancel()
    
    @tasks.loop(seconds=30)
    async def check_reminders(self):
        try:
            await db_service.ensure_initialized()
            reminders = await db_service.get_pending_reminders()
            
            for reminder in reminders:
                channel = self.bot.get_channel(reminder.channel_id)
                if channel:
                    if reminder.message.startswith("GIVEAWAY_END|"):
                        parts = reminder.message.split("|")
                        if len(parts) >= 4:
                            message_id = int(parts[1])
                            winners_count = int(parts[2])
                            prize = parts[3]
                            
                            try:
                                giveaway_msg = await channel.fetch_message(message_id)
                                
                                reaction = discord.utils.get(giveaway_msg.reactions, emoji="🎉")
                                if reaction:
                                    users = []
                                    async for user in reaction.users():
                                        if not user.bot:
                                            users.append(user)
                                    
                                    import random
                                    winners = random.sample(users, min(winners_count, len(users)))
                                    
                                    if winners:
                                        winners_text = ", ".join([w.mention for w in winners])
                                        embed = create_embed(
                                            title="🎉 GIVEAWAY ENDED 🎉",
                                            description=f"**Prize:** {prize}\n\n**Winners:** {winners_text}\n\nCongratulations!",
                                            color=0xFF69B4
                                        )
                                        await channel.send(embed=embed)
                                    else:
                                        await channel.send("Giveaway ended but no valid entries were found.")
                            except:
                                pass
                    else:
                        user = self.bot.get_user(reminder.user_discord_id)
                        if user:
                            embed = create_embed(
                                title="⏰ Reminder",
                                description=reminder.message,
                                color=Config.EMBED_COLOR
                            )
                            
                            try:
                                await user.send(embed=embed)
                            except:
                                await channel.send(f"{user.mention}", embed=embed)
                
                await db_service.mark_reminder_sent(reminder.id)
                
        except Exception as e:
            print(f"Error checking reminders: {e}")
    
    @check_reminders.before_loop
    async def before_check_reminders(self):
        await self.bot.wait_until_ready()
    
    @tasks.loop(minutes=1)
    async def check_announcements(self):
        try:
            await db_service.ensure_initialized()
            announcements = await db_service.get_pending_announcements()
            
            for announcement in announcements:
                embed = create_embed(
                    title=announcement.title,
                    description=announcement.content,
                    color=Config.EMBED_COLOR
                )
                embed.set_footer(text=format_timestamp(get_eastern_time()))
                
                for channel_id in announcement.channel_ids:
                    channel = self.bot.get_channel(channel_id)
                    if channel:
                        try:
                            await channel.send(embed=embed)
                        except:
                            pass
                
                await db_service.mark_announcement_sent(announcement.id)
                
        except Exception as e:
            print(f"Error checking announcements: {e}")
    
    @check_announcements.before_loop
    async def before_check_announcements(self):
        await self.bot.wait_until_ready()
    
    @commands.command(name="remind", aliases=["remindme"])
    async def set_reminder(self, ctx: commands.Context, time: str, *, message: str):
        user = await db_service.get_or_create_user(ctx.author.id, ctx.guild.id)
        lang = user.language
        
        seconds = parse_duration(time)
        if not seconds:
            await ctx.send("Invalid time format. Use: 30m, 1h, 1d, 1w, etc.", delete_after=5)
            return
        
        scheduled_time = datetime.utcnow() + timedelta(seconds=seconds)
        
        reminder = await db_service.create_reminder(
            guild_id=ctx.guild.id,
            user_discord_id=ctx.author.id,
            channel_id=ctx.channel.id,
            message=message,
            scheduled_at=scheduled_time
        )
        
        embed = create_embed(
            title="⏰ Reminder Set",
            description=get_text("reminder_set", lang, time=format_timestamp(scheduled_time)),
            color=Config.SUCCESS_COLOR
        )
        embed.add_field(name="Message", value=message[:1024], inline=False)
        embed.add_field(name="When", value=format_timestamp(scheduled_time), inline=True)
        
        await ctx.send(embed=embed)
    
    @commands.command(name="myreminders")
    async def view_reminders(self, ctx: commands.Context):
        async with db_service.session_factory() as session:
            from sqlalchemy import select
            from src.models.database import Reminder
            
            result = await session.execute(
                select(Reminder).where(
                    Reminder.user_discord_id == ctx.author.id,
                    Reminder.guild_id == ctx.guild.id,
                    Reminder.is_sent == False
                ).order_by(Reminder.scheduled_at.asc())
            )
            reminders = result.scalars().all()
        
        if not reminders:
            await ctx.send("You have no pending reminders.", delete_after=5)
            return
        
        embed = create_embed(
            title="Your Reminders",
            description=f"You have {len(reminders)} pending reminder(s)",
            color=Config.EMBED_COLOR
        )
        
        for i, reminder in enumerate(reminders[:10], 1):
            embed.add_field(
                name=f"#{i} - {format_timestamp(reminder.scheduled_at, '%m/%d %H:%M')}",
                value=reminder.message[:100] + "..." if len(reminder.message) > 100 else reminder.message,
                inline=False
            )
        
        await ctx.send(embed=embed)
    
    @commands.command(name="cancelreminder")
    async def cancel_reminder(self, ctx: commands.Context, reminder_num: int):
        async with db_service.session_factory() as session:
            from sqlalchemy import select, delete
            from src.models.database import Reminder
            
            result = await session.execute(
                select(Reminder).where(
                    Reminder.user_discord_id == ctx.author.id,
                    Reminder.guild_id == ctx.guild.id,
                    Reminder.is_sent == False
                ).order_by(Reminder.scheduled_at.asc())
            )
            reminders = result.scalars().all()
            
            if not reminders or reminder_num < 1 or reminder_num > len(reminders):
                await ctx.send("Invalid reminder number.", delete_after=5)
                return
            
            reminder = reminders[reminder_num - 1]
            
            await session.execute(
                delete(Reminder).where(Reminder.id == reminder.id)
            )
            await session.commit()
        
        embed = create_embed(
            title="Reminder Cancelled",
            description=f"Reminder #{reminder_num} has been cancelled.",
            color=Config.SUCCESS_COLOR
        )
        await ctx.send(embed=embed)
    
    @commands.command(name="daily")
    async def set_daily_reminder(self, ctx: commands.Context, time: str, *, message: str):
        try:
            hour, minute = map(int, time.split(":"))
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                raise ValueError()
        except:
            await ctx.send("Invalid time format. Use HH:MM (24-hour format).", delete_after=5)
            return
        
        us_eastern = pytz.timezone('America/New_York')
        now = datetime.now(us_eastern)
        scheduled_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        if scheduled_time <= now:
            scheduled_time += timedelta(days=1)
        
        scheduled_time_utc = scheduled_time.astimezone(pytz.UTC).replace(tzinfo=None)
        
        await db_service.create_reminder(
            guild_id=ctx.guild.id,
            user_discord_id=ctx.author.id,
            channel_id=ctx.channel.id,
            message=message,
            scheduled_at=scheduled_time_utc,
            is_recurring=True,
            pattern="daily"
        )
        
        embed = create_embed(
            title="⏰ Daily Reminder Set",
            description=f"I'll remind you every day at {time} EST.",
            color=Config.SUCCESS_COLOR
        )
        embed.add_field(name="Message", value=message[:1024], inline=False)
        
        await ctx.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(RemindersCog(bot))
