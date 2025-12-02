import discord
from datetime import datetime
import pytz
from typing import Optional, List
import re

def get_eastern_time() -> datetime:
    us_eastern = pytz.timezone('America/New_York')
    return datetime.now(us_eastern)

def format_timestamp(dt: datetime, format_str: str = "%B %d, %Y at %I:%M %p EST") -> str:
    if dt.tzinfo is None:
        us_eastern = pytz.timezone('America/New_York')
        dt = us_eastern.localize(dt)
    return dt.strftime(format_str)

def create_embed(
    title: str = None,
    description: str = None,
    color: int = 0x5865F2,
    fields: List[tuple] = None,
    footer: str = None,
    thumbnail_url: str = None,
    image_url: str = None,
    author_name: str = None,
    author_icon_url: str = None
) -> discord.Embed:
    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=datetime.utcnow()
    )
    
    if fields:
        for name, value, inline in fields:
            embed.add_field(name=name, value=value, inline=inline)
    
    if footer:
        embed.set_footer(text=footer)
    
    if thumbnail_url:
        embed.set_thumbnail(url=thumbnail_url)
    
    if image_url:
        embed.set_image(url=image_url)
    
    if author_name:
        embed.set_author(name=author_name, icon_url=author_icon_url)
    
    return embed

def is_staff(member: discord.Member, staff_role_names: List[str] = None) -> bool:
    if member.guild_permissions.administrator:
        return True
    
    if not staff_role_names:
        staff_role_names = ["Staff", "Moderator", "Admin", "Owner"]
    
    for role in member.roles:
        if role.name in staff_role_names:
            return True
    
    return False

def is_ticket_channel(channel: discord.TextChannel) -> bool:
    if channel.category:
        return "ticket" in channel.category.name.lower()
    return "ticket" in channel.name.lower()

def parse_duration(duration_str: str) -> Optional[int]:
    pattern = r'(\d+)\s*([smhdw])'
    match = re.match(pattern, duration_str.lower())
    
    if not match:
        return None
    
    amount = int(match.group(1))
    unit = match.group(2)
    
    multipliers = {
        's': 1,
        'm': 60,
        'h': 3600,
        'd': 86400,
        'w': 604800
    }
    
    return amount * multipliers.get(unit, 1)

def truncate_text(text: str, max_length: int = 1024) -> str:
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."

def extract_keywords(text: str) -> List[str]:
    words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
    stop_words = {'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 
                  'can', 'her', 'was', 'one', 'our', 'out', 'has', 'have'}
    return [w for w in words if w not in stop_words]

def format_price(price: float, currency: str = "$") -> str:
    return f"{currency}{price:.2f}"

def get_status_emoji(status: str) -> str:
    status_emojis = {
        "open": "🟢",
        "in_progress": "🟡",
        "pending": "🟠",
        "resolved": "🟢",
        "closed": "⚫",
        "pending": "🟡",
        "confirmed": "🔵",
        "processing": "🟠",
        "shipped": "📦",
        "delivered": "✅",
        "cancelled": "❌",
        "refunded": "💰"
    }
    return status_emojis.get(status.lower(), "⚪")

def create_progress_bar(current: int, total: int, length: int = 10) -> str:
    if total == 0:
        return "▱" * length
    
    progress = int((current / total) * length)
    filled = "▰" * progress
    empty = "▱" * (length - progress)
    
    return filled + empty
