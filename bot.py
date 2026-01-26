import discord
from discord.ext import commands
import json
import os
import logging
import sys
import atexit
import signal
import asyncio
import threading
import shutil
from datetime import datetime
from aiohttp import web

# ========== HEALTH CHECK SERVER (for Railway) ==========
def run_health_server():
    """Simple HTTP server to keep Railway happy"""
    async def handle_health(request):
        return web.Response(text="OK")
    
    async def start_server():
        app = web.Application()
        app.router.add_get('/', handle_health)
        app.router.add_get('/health', handle_health)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', 8080)
        await site.start()
        print("✅ Health server running on port 8080")
        await asyncio.Event().wait()
    
    asyncio.run(start_server())

# Start health server in background
health_thread = threading.Thread(target=run_health_server, daemon=True)
health_thread.start()

# ========== CONFIGURATION ==========
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger('guildstats')

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)
bot.remove_command('help')

# ========== CONSTANTS ==========
AVAILABLE_CLASSES = [
    "Vanguard", "Berserker", "Destroyer", "Night Ranger", 
    "Elementalist", "Divine Caster", "Assassin", "Deathbringer", 
    "Gunslinger", "Warlord"
]

CLASS_MAPPING = {}
for cls in AVAILABLE_CLASSES:
    cls_lower = cls.lower()
    CLASS_MAPPING[cls_lower] = cls
    CLASS_MAPPING[cls_lower.replace(" ", "")] = cls
    CLASS_MAPPING[cls_lower.replace(" ", "-")] = cls

# ========== PERSISTENT STORAGE ==========
def get_storage_path():
    """Get persistent storage path (Railway Volume first)"""
    if os.path.exists('/data'):
        return '/data/user_stats.json'
    return './user_stats.json'

STATS_FILE = get_storage_path()
logger.info(f"💾 Persistent storage: {STATS_FILE}")

def load_stats():
    """Load stats from persistent storage"""
    try:
        if os.path.exists(STATS_FILE):
            with open(STATS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                logger.info(f"📂 Loaded {len(data)} players")
                return data
    except Exception as e:
        logger.warning(f"Load error: {e}")
    return {}

def save_stats(stats):
    """Save stats with backup"""
    try:
        # Create directory if needed
        os.makedirs(os.path.dirname(STATS_FILE), exist_ok=True)
        
        # Backup old file
        if os.path.exists(STATS_FILE):
            shutil.copy2(STATS_FILE, STATS_FILE + '.backup')
        
        # Atomic write
        temp_file = STATS_FILE + '.tmp'
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)
        os.replace(temp_file, STATS_FILE)
        
        logger.info(f"💾 Saved {len(stats)} players")
        return True
    except Exception as e:
        logger.error(f"Save error: {e}")
        return False

def calculate_total(stats):
    return stats.get('attack', 0) + stats.get('defense', 0) + stats.get('accuracy', 0)

# ========== SHUTDOWN HANDLING ==========
def shutdown_handler():
    logger.info("🔄 Graceful shutdown")

def signal_handler(sig, frame):
    logger.info(f"Signal {sig}, shutting down...")
    shutdown_handler()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)
atexit.register(shutdown_handler)

# ========== BOT EVENTS ==========
@bot.event
async def on_ready():
    stats = load_stats()
    total_power = sum(calculate_total(s) for s in stats.values())
    
    logger.info(f"🤖 {bot.user} is ready!")
    logger.info(f"📊 {len(bot.guilds)} guilds | {len(stats)} players | 💪 {total_power:,} power")
    
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name=f"{len(stats)} players | !commands"
        )
    )

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    await bot.process_commands(message)

# ========== HELPER FUNCTIONS ==========
async def send_help(user):
    embed = discord.Embed(
        title="🤖 GuildStats Bot - Commands",
        description="**DM only for privacy**",
        color=discord.Color.blue()
    )
    
    commands_list = [
        ("`!setstats <atk> <def> <acc> [class]`", "Set your stats"),
        ("`!update <atk> <def> <acc>`", "Update stats"),
        ("`!setclass <class>`", "Set character class"),
        ("`!setskin <yes/no>`", "Legendary skin"),
        ("`!setfamiliar <yes/no>`", "Legendary familiar"),
        ("`!mystats`", "View your stats"),
        ("`!clearmystats`", "Delete your stats"),
        ("`!commands`", "Show this help"),
        ("`!test`", "Check if bot is online"),
        ("`!status`", "Bot status and stats"),
        ("`!storage`", "Storage information"),
        ("`!backup`", "Create manual backup"),
        ("`!list <page>`", "Player ranking with pagination")
    ]
    
    for cmd, desc in commands_list:
        embed.add_field(name=cmd, value=desc, inline=False)
    
    await user.send(embed=embed)

def normalize_class_name(input_class):
    if not input_class:
        return None
    
    input_lower = input_class.lower().strip()
    
    if input_lower in CLASS_MAPPING:
        return CLASS_MAPPING[input_lower]
    
    simple_input = input_lower.replace(" ", "").replace("-", "")
    if simple_input in CLASS_MAPPING:
        return CLASS_MAPPING[simple_input]
    
    if "night" in input_lower and "ranger" in input_lower:
        return "Night Ranger"
    if "divine" in input_lower and "caster" in input_lower:
        return "Divine Caster"
    
    return None

# ========== COMMANDS ==========
@bot.command(name='commands')
async def help_command(ctx):
    await send_help(ctx.author)

@bot.command(name='test')
async def test_command(ctx):
    await ctx.send('✅ Bot is online and working!')

@bot.command(name='status')
async def status_command(ctx):
    stats = load_stats()
    
    embed = discord.Embed(
        title="🤖 Bot Status",
        color=discord.Color.green()
    )
    
    embed.add_field(name="🏓 Ping", value=f"{round(bot.latency * 1000)}ms", inline=True)
    embed.add_field(name="📊 Players", value=str(len(stats)), inline=True)
    embed.add_field(name="💾 Storage", value="Railway Volume" if '/data' in STATS_FILE else "Local", inline=True)
    
    total_power = sum(calculate_total(s) for s in stats.values())
    if stats:
        avg_power = total_power / len(stats)
        embed.add_field(name="⚡ Total Power", value=f"{total_power:,}", inline=True)
        embed.add_field(name="📈 Average", value=f"{avg_power:,.1f}", inline=True)
    
    embed.set_footer(text="Hosted on Railway • Data is persistent")
    await ctx.send(embed=embed)

@bot.command(name='setstats')
async def set_stats(ctx, attack: int, defense: int, accuracy: int, *, character_class: str = None):
    normalized_class = normalize_class_name(character_class)
    if character_class and not normalized_class:
        await ctx.send(f'❌ Invalid class. Available: {", ".join(AVAILABLE_CLASSES)}')
        return
    
    stats = load_stats()
    user_id = str(ctx.author.id)
    
    user_data = {
        'attack': attack,
        'defense': defense,
        'accuracy': accuracy,
        'character_class': normalized_class,
        'legendary_skin': False,
        'legendary_familiar': False,
        'total_score': attack + defense + accuracy,
        'updated_at': datetime.now().isoformat()
    }
    
    stats[user_id] = user_data
    
    if save_stats(stats):
        embed = discord.Embed(title="✅ Statistics Saved!", color=discord.Color.green())
        embed.add_field(name="⚔️ Attack", value=str(attack), inline=True)
        embed.add_field(name="🛡️ Defense", value=str(defense), inline=True)
        embed.add_field(name="🎯 Accuracy", value=str(accuracy), inline=True)
        
        if normalized_class:
            embed.add_field(name="🏆 Class", value=normalized_class, inline=True)
        
        total = attack + defense + accuracy
        embed.add_field(name="💪 Total", value=str(total), inline=True)
        embed.set_footer(text="Use !mystats to view")
        
        await ctx.send(embed=embed)
    else:
        await ctx.send('❌ Error saving. Try again.')

@bot.command(name='mystats')
async def my_stats(ctx):
    user_id = str(ctx.author.id)
    stats = load_stats()
    
    if user_id not in stats:
        await ctx.send('❌ No statistics. Use `!setstats` first.')
        return
    
    data = stats[user_id]
    total = calculate_total(data)
    
    embed = discord.Embed(title="📊 Your Statistics", color=discord.Color.blue())
    embed.add_field(name="⚔️ Attack", value=str(data['attack']), inline=True)
    embed.add_field(name="🛡️ Defense", value=str(data['defense']), inline=True)
    embed.add_field(name="🎯 Accuracy", value=str(data['accuracy']), inline=True)
    embed.add_field(name="💪 Total", value=str(total), inline=True)
    
    if data.get('character_class'):
        embed.add_field(name="🏆 Class", value=data['character_class'], inline=True)
    
    skin = "✅" if data.get('legendary_skin') else "❌"
    familiar = "✅" if data.get('legendary_familiar') else "❌"
    embed.add_field(name="✨ Skin", value=skin, inline=True)
    embed.add_field(name="🐉 Familiar", value=familiar, inline=True)
    
    await ctx.send(embed=embed)

@bot.command(name='setskin')
async def set_skin(ctx, has_skin: str = None):
    if not has_skin:
        await ctx.send('❌ Usage: `!setskin yes` or `!setskin no`')
        return
    
    has_skin_lower = has_skin.lower()
    if has_skin_lower not in ['yes', 'no', 'tak', 'nie']:
        await ctx.send('❌ Use: `!setskin yes` or `!setskin no`')
        return
    
    skin_bool = has_skin_lower in ['yes', 'tak']
    user_id = str(ctx.author.id)
    stats = load_stats()
    
    if user_id not in stats:
        await ctx.send('❌ First use `!setstats`')
        return
    
    stats[user_id]['legendary_skin'] = skin_bool
    
    if save_stats(stats):
        message = "✅ You have" if skin_bool else "❌ You don't have"
        await ctx.send(f'{message} **Legendary Skin**')
    else:
        await ctx.send('❌ Error saving.')

@bot.command(name='setfamiliar')
async def set_familiar(ctx, has_familiar: str = None):
    if not has_familiar:
        await ctx.send('❌ Usage: `!setfamiliar yes` or `!setfamiliar no`')
        return
    
    has_familiar_lower = has_familiar.lower()
    if has_familiar_lower not in ['yes', 'no', 'tak', 'nie']:
        await ctx.send('❌ Use: `!setfamiliar yes` or `!setfamiliar no`')
        return
    
    familiar_bool = has_familiar_lower in ['yes', 'tak']
    user_id = str(ctx.author.id)
    stats = load_stats()
    
    if user_id not in stats:
        await ctx.send('❌ First use `!setstats`')
        return
    
    stats[user_id]['legendary_familiar'] = familiar_bool
    
    if save_stats(stats):
        message = "✅ You have" if familiar_bool else "❌ You don't have"
        await ctx.send(f'{message} **Legendary Familiar**')
    else:
        await ctx.send('❌ Error saving.')

@bot.command(name='setclass')
async def set_class(ctx, *, character_class: str = None):
    if not character_class:
        await ctx.send(f'❌ Usage: `!setclass <class>`\n✅ Available: {", ".join(AVAILABLE_CLASSES)}')
        return
    
    normalized_class = normalize_class_name(character_class)
    if not normalized_class:
        await ctx.send(f'❌ Invalid class. Available: {", ".join(AVAILABLE_CLASSES)}')
        return
    
    user_id = str(ctx.author.id)
    stats = load_stats()
    
    if user_id not in stats:
        await ctx.send('❌ First use `!setstats`')
        return
    
    stats[user_id]['character_class'] = normalized_class
    
    if save_stats(stats):
        await ctx.send(f'✅ Class set to: **{normalized_class}**')
    else:
        await ctx.send('❌ Error saving.')

@bot.command(name='update')
async def update_stats(ctx, attack: int = None, defense: int = None, accuracy: int = None):
    user_id = str(ctx.author.id)
    stats = load_stats()
    
    if user_id not in stats:
        await ctx.send('❌ No statistics. Use `!setstats` first.')
        return
    
    updated = False
    if attack is not None:
        stats[user_id]['attack'] = attack
        updated = True
    if defense is not None:
        stats[user_id]['defense'] = defense
        updated = True
    if accuracy is not None:
        stats[user_id]['accuracy'] = accuracy
        updated = True
    
    if not updated:
        await ctx.send('❌ No changes provided.')
        return
    
    stats[user_id]['total_score'] = calculate_total(stats[user_id])
    stats[user_id]['updated_at'] = datetime.now().isoformat()
    
    if save_stats(stats):
        embed = discord.Embed(title="✅ Updated", color=discord.Color.green())
        if attack is not None:
            embed.add_field(name="⚔️ Attack", value=str(attack), inline=True)
        if defense is not None:
            embed.add_field(name="🛡️ Defense", value=str(defense), inline=True)
        if accuracy is not None:
            embed.add_field(name="🎯 Accuracy", value=str(accuracy), inline=True)
        
        total = calculate_total(stats[user_id])
        embed.add_field(name="💪 New Total", value=str(total), inline=False)
        await ctx.send(embed=embed)
    else:
        await ctx.send('❌ Error saving.')

@bot.command(name='guildpower')
async def guild_power(ctx):
    if isinstance(ctx.channel, discord.DMChannel):
        await ctx.send('❌ Use on server channel.')
        return
    
    stats = load_stats()
    
    if not stats:
        await ctx.send('📊 No statistics yet.')
        return
    
    total_power = 0
    member_count = 0
    
    for user_id, user_stats in stats.items():
        member = ctx.guild.get_member(int(user_id))
        if member:
            total_power += calculate_total(user_stats)
            member_count += 1
    
    if member_count == 0:
        await ctx.send('📊 No active members.')
        return
    
    avg_power = total_power / member_count
    
    embed = discord.Embed(
        title="💪 Guild Power",
        description="**High Council Access**",
        color=discord.Color.red()
    )
    
    embed.add_field(name="👥 Members", value=str(member_count), inline=True)
    embed.add_field(name="⚡ Total", value=f"{total_power:,}", inline=True)
    embed.add_field(name="📊 Average", value=f"{avg_power:,.1f}", inline=True)
    
    skin_count = sum(1 for data in stats.values() if data.get('legendary_skin', False))
    familiar_count = sum(1 for data in stats.values() if data.get('legendary_familiar', False))
    
    embed.add_field(name="✨ Skins", value=str(skin_count), inline=True)
    embed.add_field(name="🐉 Familiars", value=str(familiar_count), inline=True)
    embed.set_footer(text="High Council command")
    
    await ctx.send(embed=embed)

@bot.command(name='list', aliases=['l'])
async def list_stats(ctx, page: str = "1"):
    """List all players with pagination (High Council only)"""
    if isinstance(ctx.channel, discord.DMChannel):
        await ctx.send('❌ Use on server channel.')
        return
    
    # Convert page to int with error handling
    try:
        page_num = int(page)
    except ValueError:
        await ctx.send('❌ Invalid page number. Use: `!list <page>` or `!list`')
        return
    
    stats = load_stats()
    
    if not stats:
        await ctx.send('📊 No statistics.')
        return
    
    active_players = []
    for user_id, user_data in stats.items():
        member = ctx.guild.get_member(int(user_id))
        if member:
            active_players.append({
                'member': member,
                'stats': user_data,
                'total': calculate_total(user_data)
            })
    
    if not active_players:
        await ctx.send('📊 No active players.')
        return
    
    active_players.sort(key=lambda x: x['total'], reverse=True)
    
    # Pagination settings
    PLAYERS_PER_PAGE = 15
    total_pages = max(1, (len(active_players) + PLAYERS_PER_PAGE - 1) // PLAYERS_PER_PAGE)
    page_num = max(1, min(page_num, total_pages))
    
    start_idx = (page_num - 1) * PLAYERS_PER_PAGE
    end_idx = min(start_idx + PLAYERS_PER_PAGE, len(active_players))
    
    # Calculate guild totals
    total_guild_power = sum(player['total'] for player in active_players)
    avg_power = total_guild_power / len(active_players) if active_players else 0
    
    embed = discord.Embed(
        title=f"📋 Player Ranking - Page {page_num}/{total_pages}",
        description=f"**{len(active_players)} players** • Total: **{total_guild_power:,}** • Avg: **{avg_power:,.0f}**",
        color=discord.Color.purple()
    )
    
    for i in range(start_idx, end_idx):
        player = active_players[i]
        rank = i + 1
        
        icons = ""
        if player['stats'].get('legendary_skin', False):
            icons += "✨"
        if player['stats'].get('legendary_familiar', False):
            icons += "🐉"
        
        medal = ""
        if rank == 1: medal = "👑 "
        elif rank == 2: medal = "🥈 "
        elif rank == 3: medal = "🥉 "
        
        class_text = player['stats'].get('character_class', '❓')
        atk = player['stats'].get('attack', 0)
        df = player['stats'].get('defense', 0)
        acc = player['stats'].get('accuracy', 0)
        
        embed.add_field(
            name=f"{medal}{rank}. {player['member'].display_name} {icons}",
            value=f"**{player['total']:,}** ({atk}/{df}/{acc}) | {class_text}",
            inline=False
        )
    
    # Add statistics footer
    skin_count = sum(1 for p in active_players if p['stats'].get('legendary_skin', False))
    familiar_count = sum(1 for p in active_players if p['stats'].get('legendary_familiar', False))
    
    footer_parts = []
    footer_parts.append(f"✨ {skin_count} skins")
    footer_parts.append(f"🐉 {familiar_count} familiars")
    
    if total_pages > 1:
        footer_parts.append(f"Page {page_num}/{total_pages}")
        footer_parts.append("Use !list <page>")
    
    embed.set_footer(text=" • ".join(footer_parts))
    
    await ctx.send(embed=embed)

@bot.command(name='clearmystats')
async def clear_stats(ctx):
    user_id = str(ctx.author.id)
    stats = load_stats()
    
    if user_id in stats:
        del stats[user_id]
        if save_stats(stats):
            await ctx.send('✅ Statistics deleted.')
        else:
            await ctx.send('❌ Error deleting.')
    else:
        await ctx.send('❌ No statistics to delete.')

@bot.command(name='storage')
async def storage_command(ctx):
    stats = load_stats()
    
    embed = discord.Embed(
        title="💾 Storage Information",
        color=discord.Color.blue()
    )
    
    embed.add_field(name="📍 Path", value=STATS_FILE, inline=False)
    embed.add_field(name="👥 Players", value=str(len(stats)), inline=True)
    embed.add_field(name="💪 Total Power", value=f"{sum(calculate_total(s) for s in stats.values()):,}", inline=True)
    
    if '/data' in STATS_FILE:
        embed.add_field(name="✅ Type", value="Railway Volume (Persistent)", inline=True)
    else:
        embed.add_field(name="⚠️ Type", value="Local file", inline=True)
    
    if os.path.exists(STATS_FILE):
        size = os.path.getsize(STATS_FILE)
        embed.add_field(name="📁 File Size", value=f"{size:,} bytes", inline=True)
    
    await ctx.send(embed=embed)

@bot.command(name='backup')
async def backup_command(ctx):
    stats = load_stats()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = f'backup_{timestamp}.json'
    
    with open(backup_file, 'w', encoding='utf-8') as f:
        json.dump({
            'backup_date': datetime.now().isoformat(),
            'player_count': len(stats),
            'data': stats
        }, f, indent=2)
    
    await ctx.send(f'✅ Backup created: `{backup_file}` with {len(stats)} players')

# ========== START BOT ==========
if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("🚀 FINAL VERSION: GuildStats Bot with PERSISTENT STORAGE & PAGINATION")
    logger.info("=" * 50)
    
    from dotenv import load_dotenv
    load_dotenv()
    
    TOKEN = os.getenv('DISCORD_TOKEN')
    
    if not TOKEN:
        logger.error("❌ DISCORD_TOKEN not found!")
        sys.exit(1)
    
    try:
        bot.run(TOKEN)
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        sys.exit(1)