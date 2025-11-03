import asyncio
import os
import logging
import sys
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pytgcalls import PyTgCalls
from pytgcalls.types.input_stream import AudioPiped
from pytgcalls.types.input_stream.quality import HighQualityAudio
from pytgcalls.exceptions import NoActiveGroupCall, AlreadyJoinedError, NotInGroupCallError, NotInGroupCallError
import yt_dlp
import aiohttp
from collections import defaultdict
from datetime import datetime
import psutil
from config import API_ID, API_HASH, BOT_TOKEN, BOT_NAME, SUDO_USERS
from health_server import health_server 
# NOTE: Ensure 'config.py' and 'health_server.py' are present in your environment.
# 🚨 CRITICAL: Ensure FFmpeg is installed and accessible on your server for streaming!

# --- Configuration and Initialization ---

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
    """Get YT-DLP options with optional cookies and stability features"""
    opts = {
        'format': 'bestaudio/best',
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,
        'noplaylist': True, # Prevents long delays from accidentally extracting playlists
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
            # Use a robust User-Agent to help get stable direct stream URLs
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
    """Check if user is admin or authorized user"""
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
    """Download and extract audio info with error handling"""
    max_retries = 2
    
    for attempt in range(max_retries):
        try:
            if attempt > 0:
                logger.info(f"Retry attempt {attempt + 1}/{max_retries} for query: {query}")
                await asyncio.sleep(2)
            
            ydl_opts = get_ydl_opts()
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                if not query.startswith(('http', 'https')):
                    query = f"ytsearch1:{query}"
                
                logger.info(f"Extracting info for: {query}")
                info = ydl.extract_info(query, download=False)
                
                if not info:
                    logger.warning("YT-DLP extracted no information.")
                    continue
                
                if 'entries' in info:
                    if not info['entries']:
                        logger.warning("YT-DLP search returned no entries.")
                        continue
                    info = info['entries'][0]
                
                audio_url = info.get('url')
                
                if not audio_url:
                    logger.error("No audio URL found in extracted info.")
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
            logger.error(f"Download/Extraction error for {query} (Attempt {attempt + 1}): {e}", exc_info=True)
            if attempt == max_retries - 1:
                return None
    
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
    """Play next song in the queue with error handling"""
    try:
        if chat_id in queues and queues[chat_id]:
            song = queues[chat_id].pop(0)
            current_playing[chat_id] = song
            bot_stats['played'] += 1
            
            logger.info(f"Attempting to play: {song.title} in {chat_id}")
            
            # Create audio stream (relies on FFmpeg)
            audio_stream = AudioPiped(
                song.url,
                HighQualityAudio()
            )
            
            try:
                # Try to join and play
                await pytgcalls.play(chat_id, audio_stream)
                logger.info(f"Successfully started playing {song.title} in {chat_id}")
                return song
                
            except AlreadyJoinedError:
                # Bot is already in call, change stream
                await pytgcalls.change_stream(chat_id, audio_stream)
                logger.info(f"Changed stream to {song.title} in {chat_id}")
                return song
                
            except NoActiveGroupCall:
                logger.error(f"No active voice chat found in {chat_id}. Cannot play.")
                # Put the song back and stop attempting to play
                queues[chat_id].insert(0, song)
                current_playing.pop(chat_id, None)
                return None
                
            except Exception as e:
                # Catch streaming/FFmpeg errors
                logger.error(f"Critical PyTgCalls play/change_stream error in {chat_id}: {e}", exc_info=True)
                current_playing.pop(chat_id, None)
                return None
        else:
            # Queue empty, leave VC
            current_playing.pop(chat_id, None)
            logger.info(f"Queue empty in {chat_id}. Leaving voice chat.")
            try:
                await pytgcalls.leave_group_call(chat_id)
            except NotInGroupCallError:
                 logger.warning(f"Tried to leave {chat_id} but bot was not in call.")
            except Exception as e:
                logger.error(f"Error leaving group call in {chat_id}: {e}")
            return None
            
    except Exception as e:
        logger.critical(f"Unexpected error in play_next function for {chat_id}: {e}", exc_info=True)
        return None

# --- PyTgCalls Handler ---

@pytgcalls.on_stream_end()
async def stream_end_handler(client, update):
    """Handle stream end to play the next song"""
    chat_id = update.chat_id
    logger.info(f"Stream ended in {chat_id}. Playing next...")
    song = await play_next(chat_id)
    
    if song:
        try:
            await app.send_message(
                chat_id,
                f"🎵 **Now Playing:**\n📀 {song.title}",
                reply_markup=get_control_buttons()
            )
        except Exception as e:
             logger.error(f"Error sending 'Now Playing' message in {chat_id}: {e}")

# --- Pyrogram Command Handlers ---

@app.on_message(filters.command("start"))
async def start_command(client, message: Message):
    """Start command (Resso removed)"""
    bot_stats['users'].add(message.from_user.id)
    if message.chat.type != "private":
        bot_stats['chats'].add(message.chat.id)
    
    start_text = f"""
🎵 **THIS IS {BOT_NAME.upper()}!**

🎧 **A FAST & POWERFUL TELEGRAM MUSIC PLAYER BOT WITH SOME AWESOME FEATURES.**

**Supported Platforms:** **YouTube, Spotify, Apple Music and SoundCloud.**

⚡ **CLICK ON THE HELP BUTTON TO GET INFORMATION ABOUT MY MODULES AND COMMANDS.**
"""
    
    bot_username = (await client.get_me()).username
    
    await message.reply_text(
        start_text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Add Me In Your Group", url=f"https://t.me/{bot_username}?startgroup=true")],
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
    status_msg = await message.reply_text("🔍 **Searching and Preparing Stream...**")
    
    try:
        song_info = await download_song(query)
        
        if not song_info:
            await status_msg.edit_text(
                "❌ **Could not find or process the song!**\n\n"
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
        
        is_playing = chat_id in current_playing
        queues[chat_id].append(song)
        
        if not is_playing:
            await status_msg.edit_text("🎵 **Joining Voice Chat and Starting Playback...**")
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
        logger.error(f"Play command final error: {e}", exc_info=True)
        await status_msg.edit_text(
            f"❌ **An unexpected error occurred!**\n\n"
            f"Error: `{str(e)[:150]}`\n\n"
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
        await message.reply_text(f"❌ **Error pausing:** {str(e)}")

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
        await message.reply_text(f"❌ **Error resuming:** {str(e)}")

@app.on_message(filters.command(["skip", "next"]) & ~filters.private)
async def skip_command(client, message: Message):
    """Skip"""
    if not await is_admin(message.chat.id, message.from_user.id):
        await message.reply_text("❌ **Only admins!**")
        return
    chat_id = message.chat.id
    if chat_id in current_playing:
        await message.reply_text("⏭ **Skipping to next song...**")
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
        await message.reply_text("⏹ **Stopped and cleared queue!**")
    except Exception as e:
        await message.reply_text(f"❌ **Error stopping:** {str(e)}")

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
        text += f"▶️ **Playing:**\n`{song.title}`\n\n"
    if queues[chat_id]:
        text += "**Next:**\n"
        for i, song in enumerate(queues[chat_id][:10], 1):
            text += f"{i}. `{song.title}`\n"
        if len(queues[chat_id]) > 10:
             text += f"*{len(queues[chat_id]) - 10} more songs in queue...*"
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
        f"⚡ `{ms:.2f}ms`\n"
        f"⏰ Uptime: `{str(datetime.now() - start_time).split('.')[0]}`"
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

# Callback handler
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
                [InlineKeyboardButton("Admin", callback_data="help_admin")],
                [InlineKeyboardButton("🔙 Back", callback_data="start_back")]
            ])
        )
    elif data == "help_admin":
        await callback_query.message.edit_text(
            "**👑 Admin Commands:**\n\n"
            "• `/auth <user>` - Add user to admin list\n"
            "• `/unauth <user>` - Remove user from admin list\n"
            "• `/maint <on|off>` - Maintenance mode (Sudo only)",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="help_main")]])
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
    
    # Inline Control Buttons Logic
    elif data in ["pause", "resume", "skip", "stop"]:
        if not await is_admin(chat_id, user_id):
            await callback_query.answer("❌ Admins only!", show_alert=True)
            return

        try:
            if data == "pause":
                await pytgcalls.pause_stream(chat_id)
                await callback_query.answer("⏸ Paused!")
            elif data == "resume":
                await pytgcalls.resume_stream(chat_id)
                await callback_query.answer("▶️ Resumed!")
            elif data == "skip":
                song = await play_next(chat_id)
                if song:
                    await callback_query.message.edit_text(
                        f"⏭ **Skipped!**\n\n🎵 {song.title}",
                        reply_markup=get_control_buttons()
                    )
                    await callback_query.answer("⏭ Skipped!")
                else:
                    await callback_query.answer("✅ Queue finished!", show_alert=True)
            elif data == "stop":
                await pytgcalls.leave_group_call(chat_id)
                queues[chat_id].clear()
                current_playing.pop(chat_id, None)
                await callback_query.message.edit_text("⏹ **Stopped!**")
                await callback_query.answer("⏹ Stopped!")
        except Exception as e:
             logger.error(f"Callback error for {data} in {chat_id}: {e}")
             await callback_query.answer(f"❌ Error: {str(e)[:50]}", show_alert=True)
    
    elif data == "queue":
        await callback_query.answer("Opening Queue...", show_alert=False)
        await queue_command(client, callback_query.message)


async def main():
    """Main function to start clients"""
    os.makedirs("downloads", exist_ok=True)
    
    await health_server.start() # Start custom health server
    await pytgcalls.start()
    await app.start() # Start Pyrogram client
    
    logger.info(f"{BOT_NAME} started!")
    
    await asyncio.Event().wait()

if __name__ == "__main__":
    app.run(main())
    
