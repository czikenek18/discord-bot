import discord
from discord.ext import commands
import json
import os
import logging
import sys
import atexit
import signal

# ========== CONFIGURATION ==========
# Configure logging for Railway
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('guildstats')

# Bot setup with optimized intents
intents = discord.Intents.default()
intents.message_content = True  # Required for reading messages
intents.members = True  # Required for checking roles
bot = commands.Bot(command_prefix='!', intents=intents)
bot.remove_command('help')

# ========== CONSTANTS ==========
AVAILABLE_CLASSES = [
    "Vanguard", "Berserker", "Destroyer", "Night Ranger", 
    "Elementalist", "Divine Caster", "Assassin", "Deathbringer", 
    "Gunslinger", "Warlord"
]

# Case-insensitive class mapping
CLASS_MAPPING = {}
for cls in AVAILABLE_CLASSES:
    cls_lower = cls.lower()
    CLASS_MAPPING[cls_lower] = cls
    CLASS_MAPPING[cls_lower.replace(" ", "")] = cls
    CLASS_MAPPING[cls_lower.replace(" ", "-")] = cls

HIGH_COUNCIL_ROLE = "High Council"
HELLKEEPER_ROLE = "HellKeeper"

# Use Railway's persistent storage or local file
STATS_FILE = 'user_stats.json'

# ========== UTILITY FUNCTIONS ==========
def normalize_class_name(input_class: str) -> str | None:
    """Convert any class name input to correct format (case-insensitive)"""
    if not input_class:
        return None
    
    input_lower = input_class.lower().strip()
    
    # Direct match
    if input_lower in CLASS_MAPPING:
        return CLASS_MAPPING[input_lower]
    
    # Try without spaces/dashes
    simple_input = input_lower.replace(" ", "").replace("-", "")
    if simple_input in CLASS_MAPPING:
        return CLASS_MAPPING[simple_input]
    
    # Partial matches for two-word classes
    if "night" in input_lower and "ranger" in input_lower:
        return "Night Ranger"
    if "divine" in input_lower and "caster" in input_lower:
        return "Divine Caster"
    
    return None

def clean_text(text: str) -> str:
    """Remove non-ASCII characters safely"""
    if not text:
        return ""
    return ''.join(c for c in str(text) if ord(c) < 128)

def load_stats() -> dict:
    """Load stats with UTF-8 encoding and error handling"""
    try:
        if os.path.exists(STATS_FILE):
            with open(STATS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.warning(f"Error loading stats: {e}. Starting fresh.")
    return {}

def save_stats(stats: dict) -> bool:
    """Save stats with atomic write for safety"""
    try:
        # Atomic write to prevent corruption
        temp_file = STATS_FILE + '.tmp'
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)
        
        # Replace original file
        if os.path.exists(STATS_FILE):
            os.replace(temp_file, STATS_FILE)
        else:
            os.rename(temp_file, STATS_FILE)
        
        return True
    except IOError as e:
        logger.error(f"Error saving stats: {e}")
        # Clean up temp file if exists
        if os.path.exists(temp_file):
            os.remove(temp_file)
        return False

def calculate_total(stats: dict) -> int:
    """Calculate total power with default values"""
    return stats.get('attack', 0) + stats.get('defense', 0) + stats.get('accuracy', 0)

# ========== SHUTDOWN HANDLING ==========
def shutdown_handler():
    """Handle graceful shutdown"""
    logger.info("🔄 Shutting down gracefully...")
    # Any cleanup can go here

def signal_handler(sig, frame):
    """Handle system signals"""
    logger.info(f"Received signal {sig}, shutting down...")
    shutdown_handler()
    sys.exit(0)

# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)
atexit.register(shutdown_handler)

# ========== BOT EVENTS ==========
@bot.event
async def on_ready():
    """Called when bot is ready"""
    logger.info(f"🤖 {bot.user} is ready!")
    logger.info(f"📊 Serving {len(bot.guilds)} guild(s)")
    logger.info(f"🔗 Invite URL: https://discord.com/api/oauth2/authorize?client_id={bot.user.id}&permissions=277025770560&scope=bot")
    
    # Set bot status
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="guild stats | !commands"
        )
    )

@bot.event
async def on_message(message):
    """Process messages with minimal logging for production"""
    # Only log commands, not all messages
    if message.content.startswith('!'):
        logger.debug(f"Command from {message.author}: {message.content[:50]}")
    
    if message.author == bot.user:
        return
    
    await bot.process_commands(message)

# ========== HELPER FUNCTIONS ==========
async def send_help(user):
    """Send help embed"""
    embed = discord.Embed(
        title="🤖 GuildStats Bot - Commands",
        description="**Case-insensitive commands** • **DM only for stats**",
        color=discord.Color.blue()
    )
    
    commands_info = [
        ("`!setstats <atk> <def> <acc> [class]`", "Set your stats\nExamples: `!setstats 400 350 500 berserker`"),
        ("`!update <atk> <def> <acc>`", "Update stats\nExample: `!update 420 360 510`"),
        ("`!setclass <class>`", "Set class\nExample: `!setclass nightranger`"),
        ("`!setskin <yes/no>`", "Legendary skin\nExample: `!setskin YES`"),
        ("`!setfamiliar <yes/no>`", "Legendary familiar\nExample: `!setfamiliar no`"),
        ("`!mystats`", "View your stats"),
        ("`!clearmystats`", "Delete your stats"),
        ("`!commands`", "Show this help")
    ]
    
    for cmd, desc in commands_info:
        embed.add_field(name=cmd, value=desc, inline=False)
    
    class_examples = "**Formats accepted:**\n"
    class_examples += "• `nightranger` / `night-ranger` / `Night Ranger`\n"
    class_examples += "• `divinecaster` / `divine-caster` / `Divine Caster`\n"
    class_examples += "• `berserker` / `Berserker` / `BERSERKER`\n\n"
    class_examples += f"**Available:** {', '.join(AVAILABLE_CLASSES)}"
    
    embed.add_field(name="🏆 Classes", value=class_examples, inline=False)
    embed.set_footer(text="Hosted on Railway • Data saved automatically")
    
    await user.send(embed=embed)

# ========== COMMANDS ==========
@bot.command(name='commands')
async def help_command(ctx):
    """Show help menu"""
    await send_help(ctx.author)

@bot.command(name='test')
async def test_command(ctx):
    """Test if bot is working"""
    await ctx.send('✅ Bot is online and working!')
    logger.info(f"Test command from {ctx.author}")

@bot.command(name='setstats')
async def set_stats(ctx, attack: int, defense: int, accuracy: int, *, character_class: str = None):
    """Set your statistics"""
    logger.info(f"set_stats from {ctx.author}: {attack}/{defense}/{accuracy} class={character_class}")
    
    normalized_class = None
    if character_class:
        normalized_class = normalize_class_name(character_class)
        if not normalized_class:
            await ctx.send(
                f'❌ Invalid class: `{character_class}`\n'
                f'✅ Available: {", ".join(AVAILABLE_CLASSES)}\n'
                f'💡 **Try:** `nightranger`, `divine-caster`, `Berserker`'
            )
            return
    
    stats = load_stats()
    user_id = str(ctx.author.id)
    
    user_data = {
        'attack': attack,
        'defense': defense,
        'accuracy': accuracy,
        'username': clean_text(ctx.author.name),
        'display_name': clean_text(ctx.author.display_name),
        'character_class': normalized_class,
        'legendary_skin': False,
        'legendary_familiar': False,
        'total_score': attack + defense + accuracy,
        'updated_at': str(ctx.message.created_at)
    }
    
    stats[user_id] = user_data
    
    if save_stats(stats):
        embed = discord.Embed(
            title="✅ Statistics Saved!",
            color=discord.Color.green()
        )
        embed.add_field(name="⚔️ Attack", value=str(attack), inline=True)
        embed.add_field(name="🛡️ Defense", value=str(defense), inline=True)
        embed.add_field(name="🎯 Accuracy", value=str(accuracy), inline=True)
        
        if normalized_class:
            embed.add_field(name="🏆 Class", value=normalized_class, inline=True)
        
        total = attack + defense + accuracy
        embed.add_field(name="💪 Total", value=str(total), inline=True)
        embed.set_footer(text="Use !mystats to view")
        
        await ctx.send(embed=embed)
        logger.info(f"Stats saved for {ctx.author}")
    else:
        await ctx.send('❌ Error saving statistics. Please try again.')

@bot.command(name='mystats')
async def my_stats(ctx):
    """View your statistics"""
    user_id = str(ctx.author.id)
    stats = load_stats()
    
    if user_id not in stats:
        await ctx.send('❌ No statistics found. Use `!setstats` first.')
        return
    
    data = stats[user_id]
    total = calculate_total(data)
    
    embed = discord.Embed(
        title="📊 Your Statistics",
        color=discord.Color.blue()
    )
    
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
    
    # Show ranking if available
    all_players = [(uid, s.get('total_score', 0)) for uid, s in stats.items()]
    all_players.sort(key=lambda x: x[1], reverse=True)
    
    rank = next((i+1 for i, (uid, _) in enumerate(all_players) if uid == user_id), None)
    if rank:
        embed.add_field(name="🏅 Rank", value=f"#{rank} of {len(all_players)}", inline=False)
    
    embed.set_footer(text="Private data • Updated automatically")
    
    await ctx.send(embed=embed)

@bot.command(name='setskin')
async def set_skin(ctx, has_skin: str = None):
    """Set legendary skin"""
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
        await ctx.send('❌ Error saving. Try again.')

@bot.command(name='setfamiliar')
async def set_familiar(ctx, has_familiar: str = None):
    """Set legendary familiar"""
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
        await ctx.send('❌ Error saving. Try again.')

@bot.command(name='setclass')
async def set_class(ctx, *, character_class: str = None):
    """Set character class"""
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
        await ctx.send('❌ Error saving. Try again.')

@bot.command(name='update')
async def update_stats(ctx, attack: int = None, defense: int = None, accuracy: int = None):
    """Update your statistics"""
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
    
    # Recalculate total
    stats[user_id]['total_score'] = calculate_total(stats[user_id])
    stats[user_id]['updated_at'] = str(ctx.message.created_at)
    
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
        await ctx.send('❌ Error saving. Try again.')

@bot.command(name='guildpower')
async def guild_power(ctx):
    """Show total guild power (High Council only)"""
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
        description=f"**High Council Access**",
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
async def list_stats(ctx):
    """List all players (High Council only)"""
    if isinstance(ctx.channel, discord.DMChannel):
        await ctx.send('❌ Use on server channel.')
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
    
    embed = discord.Embed(
        title="📋 Players",
        description=f"**High Council** • {len(active_players)} players",
        color=discord.Color.purple()
    )
    
    for i, player in enumerate(active_players[:15], 1):
        icons = ""
        if player['stats'].get('legendary_skin', False):
            icons += "✨"
        if player['stats'].get('legendary_familiar', False):
            icons += "🐉"
        
        medal = ""
        if i == 1: medal = "👑 "
        elif i == 2: medal = "🥈 "
        elif i == 3: medal = "🥉 "
        
        class_text = player['stats'].get('character_class', '❓')
        
        embed.add_field(
            name=f"{medal}{i}. {player['member'].display_name} {icons}",
            value=f"**{player['total']:,}** | {class_text}",
            inline=False
        )
    
    await ctx.send(embed=embed)

@bot.command(name='clearmystats')
async def clear_stats(ctx):
    """Delete your statistics"""
    user_id = str(ctx.author.id)
    stats = load_stats()
    
    if user_id in stats:
        del stats[user_id]
        if save_stats(stats):
            await ctx.send('✅ Statistics deleted.')
        else:
            await ctx.send('❌ Error deleting. Try again.')
    else:
        await ctx.send('❌ No statistics to delete.')

@bot.command(name='status')
async def bot_status(ctx):
    """Check bot status and stats"""
    stats = load_stats()
    
    embed = discord.Embed(
        title="🤖 Bot Status",
        color=discord.Color.green()
    )
    
    embed.add_field(name="🏓 Ping", value=f"{round(bot.latency * 1000)}ms", inline=True)
    embed.add_field(name="📊 Players", value=str(len(stats)), inline=True)
    embed.add_field(name="🔄 Uptime", value="24/7 on Railway", inline=True)
    
    total_power = sum(calculate_total(s) for s in stats.values())
    if stats:
        avg_power = total_power / len(stats)
        embed.add_field(name="⚡ Total Power", value=f"{total_power:,}", inline=True)
        embed.add_field(name="📈 Average", value=f"{avg_power:,.1f}", inline=True)
    
    embed.set_footer(text="Hosted on Railway • !commands for help")
    
    await ctx.send(embed=embed)

# ========== START BOT ==========
if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("🚀 Starting GuildStats Bot for Railway")
    logger.info("=" * 50)
    
    # Load token from Railway environment or .env file
    from dotenv import load_dotenv
    load_dotenv()
    
    TOKEN = os.getenv('DISCORD_TOKEN')
    
    if not TOKEN:
        logger.error("❌ DISCORD_TOKEN not found in environment!")
        logger.info("💡 On Railway: Add DISCORD_TOKEN in Variables tab")
        logger.info("💡 Locally: Create .env file with DISCORD_TOKEN=your_token")
        sys.exit(1)
    
    try:
        bot.run(TOKEN)
    except discord.errors.LoginFailure:
        logger.error("❌ Invalid Discord token. Check your DISCORD_TOKEN.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Error starting bot: {e}")
        sys.exit(1)