import asyncio
import os
import logging
import sys
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pytgcalls import PyTgCalls
from pytgcalls.types.input_stream import AudioPiped
from pytgcalls.types.input_stream.quality import HighQualityAudio
from pytgcalls.exceptions import NoActiveGroupCall, AlreadyJoinedError, NotInGroupCallError
import yt_dlp
import aiohttp
from collections import defaultdict
from datetime import datetime
import psutil
from config import API_ID, API_HASH, BOT_TOKEN, BOT_NAME, SUDO_USERS
from health_server import health_server

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize clients
app = Client(
    "music_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# Initialize PyTgCalls AFTER app
pytgcalls = PyTgCalls(app)

# Global state
queues = defaultdict(list)
current_playing = {}
start_time = datetime.now()
bot_stats = {'chats': set(), 'users': set(), 'played': 0}
auth_users = defaultdict(set)
maintenance_mode = False
blocked_users = set()
blocked_chats = set()
gbanned_users = set()

# YT-DLP options
def get_ydl_opts():
    """Get YT-DLP options with optional cookies"""
    opts = {
        'format': 'bestaudio/best',
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'nocheckcertificate': True,
        'geo_bypass': True,
        'ignoreerrors': True,
        'no_check_certificate': True,
        'prefer_ffmpeg': True,
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'web'],
                'skip': ['hls', 'dash']
            }
        },
        'http_headers': {
            'User-Agent': 'com.google.android.youtube/17.36.4 (Linux; U; Android 12; US) gzip',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-us,en;q=0.5',
        }
    }
    
    if os.path.exists('cookies.txt'):
        opts['cookiefile'] = 'cookies.txt'
        logger.info("Using cookies.txt")
    
    return opts

class Song:
    def __init__(self, title, duration, url, thumbnail, requester, platform="YouTube"):
        self.title = title
        self.duration = duration
        self.url = url
        self.thumbnail = thumbnail
        self.requester = requester
        self.platform = platform

def is_sudo(user_id):
    """Check if user is sudo"""
    return user_id in SUDO_USERS

async def is_admin(chat_id, user_id):
    """Check if user is admin"""
    if is_sudo(user_id):
        return True
    if user_id in auth_users[chat_id]:
        return True
    try:
        member = await app.get_chat_member(chat_id, user_id)
        return member.status in ["creator", "administrator"]
    except:
        return False

async def download_song(query):
    """Download and extract audio info"""
    max_retries = 2
    
    for attempt in range(max_retries):
        try:
            if attempt > 0:
                logger.info(f"Retry attempt {attempt + 1}/{max_retries}")
                await asyncio.sleep(2)
            
            ydl_opts = get_ydl_opts()
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                if not query.startswith('http'):
                    query = f"ytsearch1:{query}"
                
                logger.info(f"Extracting: {query}")
                info = ydl.extract_info(query, download=False)
                
                if not info:
                    continue
                
                if 'entries' in info:
                    if not info['entries']:
                        continue
                    info = info['entries'][0]
                
                # Get the best audio URL
                audio_url = None
                if 'url' in info:
                    audio_url = info['url']
                elif 'formats' in info:
                    for fmt in info['formats']:
                        if fmt.get('acodec') != 'none' and fmt.get('vcodec') == 'none':
                            audio_url = fmt['url']
                            break
                
                if not audio_url:
                    logger.error("No audio URL found")
                    continue
                
                title = info.get('title', 'Unknown')
                duration = info.get('duration', 0)
                thumbnail = info.get('thumbnail', '')
                
                logger.info(f"Extracted: {title}")
                
                return {
                    'title': title,
                    'duration': duration,
                    'url': audio_url,
                    'thumbnail': thumbnail
                }
                
        except Exception as e:
            logger.error(f"Download error: {e}")
            if attempt < max_retries - 1:
                continue
    
    return None

def format_duration(seconds):
    """Format duration"""
    if not seconds:
        return "Live"
    mins, secs = divmod(int(seconds), 60)
    hours, mins = divmod(mins, 60)
    if hours:
        return f"{hours}:{mins:02d}:{secs:02d}"
    return f"{mins}:{secs:02d}"

def get_control_buttons():
    """Get control buttons"""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⏸ Pause", callback_data="pause"),
            InlineKeyboardButton("▶️ Resume", callback_data="resume"),
            InlineKeyboardButton("⏭ Skip", callback_data="skip")
        ],
        [
            InlineKeyboardButton("⏹ Stop", callback_data="stop"),
            InlineKeyboardButton("🔄 Queue", callback_data="queue")
        ]
    ])

async def play_next(chat_id):
    """Play next song"""
    try:
        if chat_id in queues and queues[chat_id]:
            song = queues[chat_id].pop(0)
            current_playing[chat_id] = song
            bot_stats['played'] += 1
            
            logger.info(f"Playing: {song.title} in {chat_id}")
            
            # Create audio stream
            audio_stream = AudioPiped(
                song.url,
                HighQualityAudio()
            )
            
            try:
                # Try to play
                await pytgcalls.play(
                    chat_id,
                    audio_stream
                )
                logger.info(f"Successfully started playing in {chat_id}")
                return song
                
            except AlreadyJoinedError:
                # Already in call, change stream
                logger.info(f"Already in call, changing stream")
                await pytgcalls.change_stream(
                    chat_id,
                    audio_stream
                )
                return song
                
            except NoActiveGroupCall:
                logger.error(f"No active voice chat in {chat_id}")
                return None
                
            except Exception as e:
                logger.error(f"Play error: {e}", exc_info=True)
                return None
        else:
            # Queue empty
            current_playing.pop(chat_id, None)
            try:
                await pytgcalls.leave_group_call(chat_id)
            except:
                pass
            return None
            
    except Exception as e:
        logger.error(f"Play next error: {e}", exc_info=True)
        return None

@pytgcalls.on_stream_end()
async def stream_end_handler(client, update):
    """Handle stream end"""
    chat_id = update.chat_id
    logger.info(f"Stream ended in {chat_id}")
    song = await play_next(chat_id)
    
    if song:
        try:
            await app.send_message(
                chat_id,
                f"🎵 **Now Playing:**\n📀 {song.title}",
                reply_markup=get_control_buttons()
            )
        except:
            pass

# ============= BASIC COMMANDS =============

@app.on_message(filters.command("start"))
async def start_command(client, message: Message):
    """Start command"""
    bot_stats['users'].add(message.from_user.id)
    if message.chat.type != "private":
        bot_stats['chats'].add(message.chat.id)
    
    start_text = f"""
🎵 **THIS IS {BOT_NAME.upper()}!**

🎧 **A FAST & POWERFUL TELEGRAM MUSIC PLAYER BOT WITH SOME AWESOME FEATURES.**

**Supported Platforms:** YouTube, Spotify, Resso, Apple Music and SoundCloud.

⚡ **CLICK ON THE HELP BUTTON TO GET INFORMATION ABOUT MY MODULES AND COMMANDS.**
"""
    
    await message.reply_text(
        start_text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Add Me In Your Group", url=f"https://t.me/{(await client.get_me()).username}?startgroup=true")],
            [InlineKeyboardButton("📚 Help And Commands", callback_data="help_main")],
            [
                InlineKeyboardButton("👤 Owner", url="https://t.me/s_o_n_u_783"),
                InlineKeyboardButton("💬 Support", url="https://t.me/bot_hits")
            ],
            [InlineKeyboardButton("📢 Channel", url="https://t.me/rythmix_bot_updates")]
        ])
    )

@app.on_message(filters.command("help"))
async def help_command(client, message: Message):
    """Help command"""
    await message.reply_text(
        "**Choose The Category For Which You Wanna Get Help.**\n\n"
        "**Ask Your Doubts At Support Chat**\n\n"
        "**All Commands Can Be Used With : /**",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Play", callback_data="help_play"),
                InlineKeyboardButton("Admin", callback_data="help_admin"),
            ],
            [
                InlineKeyboardButton("Ping", callback_data="help_ping"),
                InlineKeyboardButton("Song", callback_data="help_song"),
            ]
        ])
    )

# ============= MUSIC COMMANDS =============

@app.on_message(filters.command(["play", "p"]) & ~filters.private)
async def play_command(client, message: Message):
    """Play music"""
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    if maintenance_mode and not is_sudo(user_id):
        await message.reply_text("🔧 **Bot is under maintenance!**")
        return
    
    if user_id in blocked_users or chat_id in blocked_chats:
        return
    
    bot_stats['users'].add(user_id)
    bot_stats['chats'].add(chat_id)
    
    if len(message.command) < 2:
        await message.reply_text(
            "❌ **Usage:** `/play <song name>`\n\n"
            "**Example:** `/play faded`\n\n"
            "**Important:**\n"
            "1️⃣ Start voice chat first\n"
            "2️⃣ Make bot admin\n"
            "3️⃣ Then use /play"
        )
        return
    
    query = message.text.split(None, 1)[1]
    status_msg = await message.reply_text("🔍 **Searching...**")
    
    try:
        song_info = await download_song(query)
        
        if not song_info:
            await status_msg.edit_text(
                "❌ **Could not find the song!**\n\n"
                "**Try:**\n"
                "• Different song name\n"
                "• YouTube URL\n"
                "• Check spelling"
            )
            return
        
        song = Song(
            title=song_info['title'],
            duration=song_info['duration'],
            url=song_info['url'],
            thumbnail=song_info['thumbnail'],
            requester=message.from_user.mention
        )
        
        queues[chat_id].append(song)
        
        if chat_id not in current_playing:
            await status_msg.edit_text("🎵 **Processing...**")
            playing_song = await play_next(chat_id)
            
            if playing_song:
                await status_msg.edit_text(
                    f"🎵 **Now Playing:**\n\n"
                    f"📀 {playing_song.title}\n"
                    f"⏱ {format_duration(playing_song.duration)}\n"
                    f"👤 {playing_song.requester}",
                    reply_markup=get_control_buttons()
                )
            else:
                await status_msg.edit_text(
                    "❌ **Failed to play!**\n\n"
                    "**Checklist:**\n"
                    "✅ Voice chat started?\n"
                    "✅ Bot is admin?\n"
                    "✅ 'Manage Voice Chats' permission?\n\n"
                    "Fix these and try again!"
                )
        else:
            await status_msg.edit_text(
                f"✅ **Added to Queue!**\n\n"
                f"📀 {song.title}\n"
                f"⏱ {format_duration(song.duration)}\n"
                f"📊 Position: #{len(queues[chat_id])}"
            )
            
    except Exception as e:
        logger.error(f"Play error: {e}", exc_info=True)
        await status_msg.edit_text(
            f"❌ **Error!**\n\n"
            f"{str(e)[:150]}\n\n"
            "Contact support if this persists."
        )

@app.on_message(filters.command("pause") & ~filters.private)
async def pause_command(client, message: Message):
    """Pause"""
    if not await is_admin(message.chat.id, message.from_user.id):
        await message.reply_text("❌ **Only admins!**")
        return
    
    try:
        await pytgcalls.pause_stream(message.chat.id)
        await message.reply_text("⏸ **Paused!**")
    except Exception as e:
        await message.reply_text(f"❌ {str(e)}")

@app.on_message(filters.command("resume") & ~filters.private)
async def resume_command(client, message: Message):
    """Resume"""
    if not await is_admin(message.chat.id, message.from_user.id):
        await message.reply_text("❌ **Only admins!**")
        return
    
    try:
        await pytgcalls.resume_stream(message.chat.id)
        await message.reply_text("▶️ **Resumed!**")
    except Exception as e:
        await message.reply_text(f"❌ {str(e)}")

@app.on_message(filters.command(["skip", "next"]) & ~filters.private)
async def skip_command(client, message: Message):
    """Skip"""
    if not await is_admin(message.chat.id, message.from_user.id):
        await message.reply_text("❌ **Only admins!**")
        return
    
    chat_id = message.chat.id
    
    if chat_id in current_playing:
        song = await play_next(chat_id)
        if song:
            await message.reply_text(
                f"⏭ **Skipped!**\n\n🎵 {song.title}",
                reply_markup=get_control_buttons()
            )
        else:
            await message.reply_text("✅ **Queue finished!**")
    else:
        await message.reply_text("❌ **Nothing playing!**")

@app.on_message(filters.command(["stop", "end"]) & ~filters.private)
async def stop_command(client, message: Message):
    """Stop"""
    if not await is_admin(message.chat.id, message.from_user.id):
        await message.reply_text("❌ **Only admins!**")
        return
    
    chat_id = message.chat.id
    
    try:
        await pytgcalls.leave_group_call(chat_id)
        queues[chat_id].clear()
        current_playing.pop(chat_id, None)
        await message.reply_text("⏹ **Stopped!**")
    except Exception as e:
        await message.reply_text(f"❌ {str(e)}")

@app.on_message(filters.command("queue") & ~filters.private)
async def queue_command(client, message: Message):
    """Queue"""
    chat_id = message.chat.id
    
    if chat_id not in current_playing and not queues[chat_id]:
        await message.reply_text("📭 **Queue empty!**")
        return
    
    text = "📃 **Queue:**\n\n"
    
    if chat_id in current_playing:
        song = current_playing[chat_id]
        text += f"▶️ **Playing:**\n{song.title}\n\n"
    
    if queues[chat_id]:
        text += "**Next:**\n"
        for i, song in enumerate(queues[chat_id][:10], 1):
            text += f"{i}. {song.title}\n"
    
    await message.reply_text(text)

@app.on_message(filters.command("ping"))
async def ping_command(client, message: Message):
    """Ping"""
    start = datetime.now()
    msg = await message.reply_text("🏓 Pinging...")
    end = datetime.now()
    ms = (end - start).microseconds / 1000
    
    await msg.edit_text(
        f"🏓 **Pong!**\n"
        f"⚡ {ms:.2f}ms\n"
        f"⏰ Uptime: {str(datetime.now() - start_time).split('.')[0]}"
    )

@app.on_message(filters.command("stats"))
async def stats_command(client, message: Message):
    """Stats"""
    await message.reply_text(
        f"📊 **Stats:**\n\n"
        f"👥 Users: {len(bot_stats['users'])}\n"
        f"💬 Chats: {len(bot_stats['chats'])}\n"
        f"🎵 Played: {bot_stats['played']}\n"
        f"🔧 Active: {len(current_playing)}"
    )

# Callback handler (simplified)
@app.on_callback_query()
async def callback_handler(client, callback_query: CallbackQuery):
    """Handle callbacks"""
    data = callback_query.data
    chat_id = callback_query.message.chat.id
    user_id = callback_query.from_user.id
    
    if data == "help_main":
        await callback_query.message.edit_text(
            "**Choose Category:**",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Play", callback_data="help_play")],
                [InlineKeyboardButton("🔙 Back", callback_data="start_back")]
            ])
        )
    elif data == "start_back":
        await start_command(client, callback_query.message)
    elif data == "help_play":
        await callback_query.message.edit_text(
            "**🎵 Play Commands:**\n\n"
            "• `/play <song>` - Play\n"
            "• `/pause` - Pause\n"
            "• `/resume` - Resume\n"
            "• `/skip` - Skip\n"
            "• `/stop` - Stop\n"
            "• `/queue` - Queue",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="help_main")]])
        )
    elif data == "pause":
        if await is_admin(chat_id, user_id):
            try:
                await pytgcalls.pause_stream(chat_id)
                await callback_query.answer("⏸ Paused!")
            except:
                await callback_query.answer("❌ Error!", show_alert=True)
        else:
            await callback_query.answer("❌ Admins only!", show_alert=True)
    
    elif data == "resume":
        if await is_admin(chat_id, user_id):
            try:
                await pytgcalls.resume_stream(chat_id)
                await callback_query.answer("▶️ Resumed!")
            except:
                await callback_query.answer("❌ Error!", show_alert=True)
        else:
            await callback_query.answer("❌ Admins only!", show_alert=True)
    
    elif data == "skip":
        if await is_admin(chat_id, user_id):
            if chat_id in current_playing:
                song = await play_next(chat_id)
                if song:
                    await callback_query.message.edit_text(
                        f"⏭ **Skipped!**\n\n🎵 {song.title}",
                        reply_markup=get_control_buttons()
                    )
                    await callback_query.answer()
                else:
                    await callback_query.answer("✅ Queue finished!", show_alert=True)
        else:
            await callback_query.answer("❌ Admins only!", show_alert=True)
    
    elif data == "stop":
        if await is_admin(chat_id, user_id):
            try:
                await pytgcalls.leave_group_call(chat_id)
                queues[chat_id].clear()
                current_playing.pop(chat_id, None)
                await callback_query.message.edit_text("⏹ **Stopped!**")
                await callback_query.answer()
            except:
                await callback_query.answer("❌ Error!", show_alert=True)
        else:
            await callback_query.answer("❌ Admins only!", show_alert=True)

async def main():
    """Main"""
    os.makedirs("downloads", exist_ok=True)
    
    await health_server.start()
    await pytgcalls.start()
    logger.info(f"{BOT_NAME} started!")
    
    await asyncio.Event().wait()

if __name__ == "__main__":
    app.run(main())
