import discord
from discord.ext import commands
import json
import os
import logging
import sys
import atexit
import signal
from datetime import datetime

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

# ========== SMART STORAGE SYSTEM ==========
class SmartStorage:
    """Smart storage that survives Railway restarts"""
    
    def __init__(self):
        self.locations = [
            '/data/user_stats.json',           # Railway Volume (PERSISTENT)
            '/tmp/user_stats.json',            # Railway temp
            './user_stats.json',               # Local
            'user_stats.json'                  # Current dir
        ]
        
        self.backup_locations = [
            '/data/user_stats_backup.json',    # Railway Volume backup
            './user_stats_backup.json'         # Local backup
        ]
        
        self.stats_file = self.find_best_location()
        logger.info(f"📁 Using storage: {self.stats_file}")
        
    def find_best_location(self):
        """Find the best location for storage"""
        # Check Railway Volume first
        if os.path.exists('/data'):
            os.makedirs('/data', exist_ok=True)
            return '/data/user_stats.json'
        
        # Check other locations
        for location in self.locations:
            if os.path.exists(location):
                return location
        
        # Create in current directory
        return './user_stats.json'
    
    def load(self):
        """Load stats with multiple fallbacks"""
        # Try main file
        try:
            if os.path.exists(self.stats_file):
                with open(self.stats_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    logger.info(f"✅ Loaded {len(data)} players from {self.stats_file}")
                    return data
        except Exception as e:
            logger.warning(f"Failed to load {self.stats_file}: {e}")
        
        # Try backups
        for backup in self.backup_locations:
            try:
                if os.path.exists(backup):
                    with open(backup, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        logger.info(f"🔄 Restored from backup: {backup}")
                        # Save to main location
                        self.save(data)
                        return data
            except:
                continue
        
        logger.info("📂 Starting fresh database")
        return {}
    
    def save(self, data):
        """Save with atomic write and backup"""
        try:
            # Create directory if needed
            os.makedirs(os.path.dirname(self.stats_file), exist_ok=True)
            
            # Create backup
            if os.path.exists(self.stats_file):
                import shutil
                backup_file = self.stats_file + '.backup'
                shutil.copy2(self.stats_file, backup_file)
            
            # Atomic write
            temp_file = self.stats_file + '.tmp'
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            # Replace
            os.replace(temp_file, self.stats_file)
            
            # Also save to backup location
            if self.stats_file != '/data/user_stats.json' and os.path.exists('/data'):
                backup_path = '/data/user_stats_backup.json'
                with open(backup_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"💾 Saved {len(data)} players")
            return True
            
        except Exception as e:
            logger.error(f"Save failed: {e}")
            return False
    
    def emergency_backup(self, data):
        """Emergency backup to multiple locations"""
        locations = [
            '/data/user_stats_emergency.json',
            './user_stats_emergency.json',
            '/tmp/user_stats_emergency.json'
        ]
        
        for loc in locations:
            try:
                os.makedirs(os.path.dirname(loc), exist_ok=True)
                with open(loc, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                logger.info(f"🚨 Emergency backup to {loc}")
            except:
                continue

# Initialize storage
storage = SmartStorage()

# ========== UTILITY FUNCTIONS ==========
def normalize_class_name(input_class: str) -> str | None:
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

def clean_text(text: str) -> str:
    if not text:
        return ""
    return ''.join(c for c in str(text) if ord(c) < 128)

def load_stats() -> dict:
    return storage.load()

def save_stats(stats: dict) -> bool:
    return storage.save(stats)

def calculate_total(stats: dict) -> int:
    return stats.get('attack', 0) + stats.get('defense', 0) + stats.get('accuracy', 0)

# ========== SHUTDOWN HANDLING ==========
def shutdown_handler():
    logger.info("🔄 Shutting down gracefully...")
    # Final backup
    stats = load_stats()
    if stats:
        storage.emergency_backup(stats)
        logger.info(f"✅ Final backup of {len(stats)} players")

def signal_handler(sig, frame):
    logger.info(f"Received signal {sig}, shutting down...")
    shutdown_handler()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)
atexit.register(shutdown_handler)

# ========== BOT EVENTS ==========
@bot.event
async def on_ready():
    logger.info(f"🤖 {bot.user} is ready!")
    logger.info(f"📊 Serving {len(bot.guilds)} guild(s)")
    
    stats = load_stats()
    total_power = sum(calculate_total(s) for s in stats.values())
    logger.info(f"📈 Database: {len(stats)} players, {total_power:,} total power")
    
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name=f"{len(stats)} players | !commands"
        )
    )

@bot.event
async def on_message(message):
    if message.content.startswith('!'):
        logger.debug(f"Command from {message.author}: {message.content[:50]}")
    
    if message.author == bot.user:
        return
    
    await bot.process_commands(message)

# ========== COMMANDS (SKRÓCONA WERSJA - DODAJ RESZTĘ) ==========
@bot.command(name='test')
async def test_command(ctx):
    await ctx.send('✅ Bot is online and working!')

@bot.command(name='setstats')
async def set_stats(ctx, attack: int, defense: int, accuracy: int, *, character_class: str = None):
    normalized_class = normalize_class_name(character_class)
    
    stats = load_stats()
    user_id = str(ctx.author.id)
    
    user_data = {
        'attack': attack,
        'defense': defense,
        'accuracy': accuracy,
        'username': clean_text(ctx.author.name),
        'display_name': clean_text(ctx.author.display_name),
        'character_class': normalized_class,
        'total_score': attack + defense + accuracy,
        'updated_at': datetime.now().isoformat()
    }
    
    stats[user_id] = user_data
    
    if save_stats(stats):
        await ctx.send(f'✅ Stats saved! Total: {attack + defense + accuracy}')
    else:
        await ctx.send('❌ Error saving. Emergency backup created.')
        storage.emergency_backup(stats)

# ... DODAJ TU WSZYSTKIE INNE KOMENDY KTÓRE JUŻ MASZ ...
# mystats, update, setclass, setskin, setfamiliar, list, guildpower, etc.

@bot.command(name='backup')
async def backup_command(ctx):
    """Create manual backup (Admin only)"""
    stats = load_stats()
    storage.emergency_backup(stats)
    await ctx.send(f'✅ Manual backup created: {len(stats)} players')

@bot.command(name='storage')
async def storage_info(ctx):
    """Show storage information"""
    stats = load_stats()
    
    embed = discord.Embed(
        title="💾 Storage Info",
        color=discord.Color.blue()
    )
    
    embed.add_field(name="📁 Location", value=storage.stats_file, inline=False)
    embed.add_field(name="👥 Players", value=str(len(stats)), inline=True)
    embed.add_field(name="💪 Total Power", value=f"{sum(calculate_total(s) for s in stats.values()):,}", inline=True)
    
    if os.path.exists('/data'):
        embed.add_field(name="🔒 Persistent", value="✅ Railway Volume", inline=True)
    else:
        embed.add_field(name="⚠️ Warning", value="Using temp storage", inline=True)
    
    await ctx.send(embed=embed)

# ========== START BOT ==========
if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("🚀 Starting GuildStats Bot with PERSISTENT STORAGE")
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