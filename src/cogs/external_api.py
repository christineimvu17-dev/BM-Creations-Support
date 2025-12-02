import discord
from discord.ext import commands
import aiohttp
import json
from typing import Optional, Dict, Any

from src.utils.helpers import create_embed
from src.config import Config

class ExternalAPICog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def cog_load(self):
        self.session = aiohttp.ClientSession()
    
    async def cog_unload(self):
        if self.session:
            await self.session.close()
    
    async def fetch_json(self, url: str, headers: Dict = None) -> Optional[Dict]:
        try:
            async with self.session.get(url, headers=headers) as response:
                if response.status == 200:
                    return await response.json()
                return None
        except Exception as e:
            print(f"API fetch error: {e}")
            return None
    
    async def post_json(self, url: str, data: Dict, headers: Dict = None) -> Optional[Dict]:
        try:
            async with self.session.post(url, json=data, headers=headers) as response:
                if response.status in [200, 201]:
                    return await response.json()
                return None
        except Exception as e:
            print(f"API post error: {e}")
            return None
    
    @commands.command(name="weather")
    async def get_weather(self, ctx: commands.Context, *, city: str):
        data = await self.fetch_json(
            f"https://wttr.in/{city}?format=j1"
        )
        
        if not data:
            await ctx.send("Could not fetch weather data. Please try again.", delete_after=5)
            return
        
        try:
            current = data.get("current_condition", [{}])[0]
            location = data.get("nearest_area", [{}])[0]
            
            temp_c = current.get("temp_C", "N/A")
            temp_f = current.get("temp_F", "N/A")
            feels_like = current.get("FeelsLikeC", "N/A")
            humidity = current.get("humidity", "N/A")
            desc = current.get("weatherDesc", [{}])[0].get("value", "Unknown")
            wind = current.get("windspeedKmph", "N/A")
            
            city_name = location.get("areaName", [{}])[0].get("value", city)
            country = location.get("country", [{}])[0].get("value", "")
            
            embed = create_embed(
                title=f"Weather in {city_name}, {country}",
                description=f"**{desc}**",
                color=Config.EMBED_COLOR
            )
            
            embed.add_field(name="Temperature", value=f"{temp_c}C / {temp_f}F", inline=True)
            embed.add_field(name="Feels Like", value=f"{feels_like}C", inline=True)
            embed.add_field(name="Humidity", value=f"{humidity}%", inline=True)
            embed.add_field(name="Wind Speed", value=f"{wind} km/h", inline=True)
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"Error parsing weather data.", delete_after=5)
    
    @commands.command(name="joke")
    async def get_joke(self, ctx: commands.Context):
        data = await self.fetch_json(
            "https://official-joke-api.appspot.com/random_joke"
        )
        
        if not data:
            await ctx.send("Could not fetch a joke. Please try again.", delete_after=5)
            return
        
        embed = create_embed(
            title=data.get("setup", "Here's a joke!"),
            description=f"||{data.get('punchline', 'No punchline!')}||",
            color=Config.EMBED_COLOR
        )
        embed.set_footer(text="Click the spoiler to reveal the punchline!")
        
        await ctx.send(embed=embed)
    
    @commands.command(name="quote")
    async def get_quote(self, ctx: commands.Context):
        data = await self.fetch_json(
            "https://api.quotable.io/random"
        )
        
        if not data:
            await ctx.send("Could not fetch a quote. Please try again.", delete_after=5)
            return
        
        embed = create_embed(
            title="Inspirational Quote",
            description=f'"{data.get("content", "No quote available")}"',
            color=Config.EMBED_COLOR
        )
        embed.set_footer(text=f"- {data.get('author', 'Unknown')}")
        
        await ctx.send(embed=embed)
    
    @commands.command(name="catfact")
    async def get_cat_fact(self, ctx: commands.Context):
        data = await self.fetch_json(
            "https://catfact.ninja/fact"
        )
        
        if not data:
            await ctx.send("Could not fetch a cat fact. Please try again.", delete_after=5)
            return
        
        embed = create_embed(
            title="Cat Fact",
            description=data.get("fact", "Cats are awesome!"),
            color=Config.EMBED_COLOR
        )
        
        await ctx.send(embed=embed)
    
    @commands.command(name="crypto")
    async def get_crypto_price(self, ctx: commands.Context, symbol: str = "bitcoin"):
        data = await self.fetch_json(
            f"https://api.coingecko.com/api/v3/simple/price?ids={symbol.lower()}&vs_currencies=usd,eur,gbp&include_24hr_change=true"
        )
        
        if not data or symbol.lower() not in data:
            await ctx.send(f"Could not find crypto: {symbol}. Try: bitcoin, ethereum, etc.", delete_after=5)
            return
        
        coin_data = data[symbol.lower()]
        
        embed = create_embed(
            title=f"{symbol.upper()} Price",
            color=Config.EMBED_COLOR
        )
        
        embed.add_field(name="USD", value=f"${coin_data.get('usd', 'N/A'):,.2f}", inline=True)
        embed.add_field(name="EUR", value=f"{coin_data.get('eur', 'N/A'):,.2f}", inline=True)
        embed.add_field(name="GBP", value=f"{coin_data.get('gbp', 'N/A'):,.2f}", inline=True)
        
        change = coin_data.get('usd_24h_change', 0)
        change_emoji = "" if change >= 0 else ""
        embed.add_field(name="24h Change", value=f"{change_emoji} {change:.2f}%", inline=True)
        
        await ctx.send(embed=embed)
    
    @commands.command(name="github")
    async def get_github_user(self, ctx: commands.Context, username: str):
        data = await self.fetch_json(
            f"https://api.github.com/users/{username}"
        )
        
        if not data or "message" in data:
            await ctx.send(f"GitHub user '{username}' not found.", delete_after=5)
            return
        
        embed = create_embed(
            title=f"GitHub: {data.get('login', username)}",
            description=data.get("bio", "No bio available"),
            color=Config.EMBED_COLOR,
            thumbnail_url=data.get("avatar_url")
        )
        
        embed.add_field(name="Name", value=data.get("name", "N/A"), inline=True)
        embed.add_field(name="Public Repos", value=str(data.get("public_repos", 0)), inline=True)
        embed.add_field(name="Followers", value=str(data.get("followers", 0)), inline=True)
        embed.add_field(name="Following", value=str(data.get("following", 0)), inline=True)
        embed.add_field(name="Location", value=data.get("location", "N/A"), inline=True)
        embed.add_field(name="Company", value=data.get("company", "N/A"), inline=True)
        
        if data.get("html_url"):
            embed.add_field(name="Profile", value=f"[View Profile]({data['html_url']})", inline=False)
        
        await ctx.send(embed=embed)
    
    @commands.command(name="define")
    async def define_word(self, ctx: commands.Context, word: str):
        data = await self.fetch_json(
            f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
        )
        
        if not data or isinstance(data, dict):
            await ctx.send(f"Could not find definition for '{word}'.", delete_after=5)
            return
        
        try:
            entry = data[0]
            meanings = entry.get("meanings", [])
            
            embed = create_embed(
                title=f"Definition: {word.capitalize()}",
                color=Config.EMBED_COLOR
            )
            
            if entry.get("phonetic"):
                embed.description = f"Pronunciation: {entry['phonetic']}"
            
            for meaning in meanings[:3]:
                part_of_speech = meaning.get("partOfSpeech", "unknown")
                definitions = meaning.get("definitions", [])[:2]
                
                def_text = "\n".join([f"- {d.get('definition', '')}" for d in definitions])
                embed.add_field(name=part_of_speech.capitalize(), value=def_text[:1024], inline=False)
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"Error parsing definition.", delete_after=5)
    
    @commands.command(name="translate")
    async def translate_text(self, ctx: commands.Context, target_lang: str, *, text: str):
        data = await self.fetch_json(
            f"https://api.mymemory.translated.net/get?q={text[:500]}&langpair=en|{target_lang}"
        )
        
        if not data or data.get("responseStatus") != 200:
            await ctx.send("Translation failed. Try a different language code (es, fr, de, etc.).", delete_after=5)
            return
        
        translated = data.get("responseData", {}).get("translatedText", "Translation unavailable")
        
        embed = create_embed(
            title="Translation",
            color=Config.EMBED_COLOR
        )
        
        embed.add_field(name="Original (EN)", value=text[:1024], inline=False)
        embed.add_field(name=f"Translated ({target_lang.upper()})", value=translated[:1024], inline=False)
        
        await ctx.send(embed=embed)
    
    @commands.command(name="apistatus")
    @commands.has_permissions(administrator=True)
    async def api_status(self, ctx: commands.Context):
        apis = {
            "Weather (wttr.in)": "https://wttr.in/London?format=j1",
            "Jokes": "https://official-joke-api.appspot.com/random_joke",
            "Cat Facts": "https://catfact.ninja/fact",
            "Crypto (CoinGecko)": "https://api.coingecko.com/api/v3/ping",
            "GitHub": "https://api.github.com",
            "Dictionary": "https://api.dictionaryapi.dev/api/v2/entries/en/hello",
            "Translation": "https://api.mymemory.translated.net/get?q=Hello&langpair=en|es"
        }
        
        embed = create_embed(
            title="External API Status",
            description="Checking status of integrated APIs...",
            color=Config.EMBED_COLOR
        )
        
        for name, url in apis.items():
            try:
                async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                    status = "" if response.status == 200 else ""
                    embed.add_field(name=name, value=f"{status} {response.status}", inline=True)
            except Exception as e:
                embed.add_field(name=name, value=" Timeout/Error", inline=True)
        
        await ctx.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(ExternalAPICog(bot))
