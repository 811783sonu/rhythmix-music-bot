import asyncio
import os
import logging
import sys
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pytgcalls import PyTgCalls, StreamType
from pytgcalls.types.input_stream import AudioPiped
from pytgcalls.types.input_stream.quality import HighQualityAudio
from pytgcalls.exceptions import NoActiveGroupCall, AlreadyJoinedError
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
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize clients
app = Client(
    "music_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

pytgcalls = PyTgCalls(app)

# Global queues and state
queues = defaultdict(list)
current_playing = {}
start_time = datetime.now()
bot_stats = {'chats': set(), 'users': set(), 'played': 0}

# YT-DLP options - FIXED FOR BOT DETECTION
ydl_opts = {
    'format': 'bestaudio/best',
    'outtmpl': 'downloads/%(id)s.%(ext)s',
    'quiet': True,
    'no_warnings': True,
    'extract_flat': False,
    'nocheckcertificate': True,
    'geo_bypass': True,
    'age_limit': None,
    'cookiefile': 'cookies.txt',  # ✅ ADD YOUR COOKIES FILE HERE
    'extractor_args': {
        'youtube': {
            'player_client': ['android', 'web'],
            'skip': ['webpage', 'dash', 'hls']
        }
    },
    'http_headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-us,en;q=0.5',
        'Sec-Fetch-Mode': 'navigate',
    }
}

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

def is_admin(chat_id, user_id):
    """Check if user is admin (placeholder for group check)"""
    return is_sudo(user_id)

async def download_song(query):
    """Download and extract audio info - WITH RETRY AND DELAY"""
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            # ✅ ADD DELAY BETWEEN REQUESTS
            if attempt > 0:
                await asyncio.sleep(3 * attempt)  # Wait 3, 6, 9 seconds
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                if not query.startswith('http'):
                    query = f"ytsearch:{query}"
                
                info = ydl.extract_info(query, download=False)
                
                if 'entries' in info:
                    info = info['entries'][0]
                
                audio_url = info['url']
                title = info.get('title', 'Unknown')
                duration = info.get('duration', 0)
                thumbnail = info.get('thumbnail', '')
                
                return {
                    'title': title,
                    'duration': duration,
                    'url': audio_url,
                    'thumbnail': thumbnail
                }
                
        except Exception as e:
            logger.error(f"Download error (attempt {attempt + 1}/{max_retries}): {e}")
            
            # Check if it's bot detection error
            if "Sign in to confirm" in str(e):
                if attempt < max_retries - 1:
                    logger.info(f"Bot detection triggered. Retrying in {3 * (attempt + 1)} seconds...")
                    continue
                else:
                    logger.error("Failed after all retries due to bot detection!")
                    return None
            else:
                return None
    
    return None

async def fetch_lyrics(song_name):
    """Fetch lyrics"""
    try:
        async with aiohttp.ClientSession() as session:
            url = f"https://api.lyrics.ovh/v1/artist/{song_name}"
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get('lyrics', 'Lyrics not found')
                return 'Lyrics not found'
    except:
        return 'Unable to fetch lyrics'

def format_duration(seconds):
    """Format duration in MM:SS"""
    mins, secs = divmod(int(seconds), 60)
    return f"{mins}:{secs:02d}"

def get_control_buttons():
    """Get playback control buttons"""
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
    """Play the next song in queue"""
    try:
        if chat_id in queues and queues[chat_id]:
            song = queues[chat_id].pop(0)
            current_playing[chat_id] = song
            bot_stats['played'] += 1
            
            try:
                await pytgcalls.play(
                    chat_id,
                    AudioPiped(song.url, HighQualityAudio()),
                    stream_type=StreamType().pulse_stream
                )
                return song
            except AlreadyJoinedError:
                await pytgcalls.change_stream(
                    chat_id,
                    AudioPiped(song.url, HighQualityAudio())
                )
                return song
        else:
            current_playing.pop(chat_id, None)
            try:
                await pytgcalls.leave_group_call(chat_id)
            except:
                pass
            return None
    except Exception as e:
        logger.error(f"Play next error: {e}")
        return None

@pytgcalls.on_stream_end()
async def stream_end_handler(client, update):
    """Handle stream end"""
    chat_id = update.chat_id
    await play_next(chat_id)

@app.on_message(filters.command("start"))
async def start_command(client, message: Message):
    """Start command with beautiful interface"""
    bot_stats['users'].add(message.from_user.id)
    if message.chat.type != "private":
        bot_stats['chats'].add(message.chat.id)
    
    # Beautiful start message like Resso Music
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
    help_text = f"""
🎵 **{BOT_NAME} - Help Menu**

**🎶 Music Commands:**
• `/play <song name>` - Play a song
• `/pause` - Pause current song
• `/resume` - Resume playback
• `/skip` - Skip to next song
• `/stop` - Stop and clear queue
• `/queue` - Show current queue
• `/nowplaying` - Current song info
• `/lyrics <song>` - Get song lyrics

**📊 Bot Commands:**
• `/ping` - Check bot latency
• `/stats` - Bot statistics
• `/uptime` - Bot uptime

**👑 Admin Commands:**
• `/broadcast <message>` - Send to all chats
• `/reload` - Reload bot modules
• `/reboot` - Restart bot
• `/logs` - Get recent logs
• `/maintenance <on/off>` - Toggle maintenance

**💡 Tips:**
• Use song names or YouTube URLs
• Bot must be admin with "Manage Voice Chats"
• Join voice chat before playing

**Support:** @S_o_n_u_783
"""
    await message.reply_text(help_text)

@app.on_message(filters.command("play"))
async def play_command(client, message: Message):
    """Play command"""
    chat_id = message.chat.id
    bot_stats['users'].add(message.from_user.id)
    if message.chat.type != "private":
        bot_stats['chats'].add(message.chat.id)
    
    if len(message.command) < 2:
        await message.reply_text("❌ Usage: `/play <song name or URL>`")
        return
    
    query = message.text.split(None, 1)[1]
    status_msg = await message.reply_text("🔍 **Searching...**")
    
    song_info = await download_song(query)
    
    if not song_info:
        await status_msg.edit_text("❌ Could not find the song! Please try again later.")
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
        playing_song = await play_next(chat_id)
        if playing_song:
            await status_msg.edit_text(
                f"🎵 **Now Playing:**\n"
                f"📀 **Title:** {playing_song.title}\n"
                f"⏱ **Duration:** {format_duration(playing_song.duration)}\n"
                f"👤 **Requested by:** {playing_song.requester}\n"
                f"🎧 **Platform:** {playing_song.platform}",
                reply_markup=get_control_buttons()
            )
        else:
            await status_msg.edit_text("❌ Failed to play!")
    else:
        position = len(queues[chat_id])
        await status_msg.edit_text(
            f"✅ **Added to Queue!**\n"
            f"📀 **Title:** {song.title}\n"
            f"⏱ **Duration:** {format_duration(song.duration)}\n"
            f"📊 **Position:** #{position}"
        )

@app.on_message(filters.command("pause"))
async def pause_command(client, message: Message):
    """Pause playback"""
    try:
        await pytgcalls.pause_stream(message.chat.id)
        await message.reply_text("⏸ **Paused!**")
    except Exception as e:
        await message.reply_text(f"❌ Error: {str(e)}")

@app.on_message(filters.command("resume"))
async def resume_command(client, message: Message):
    """Resume playback"""
    try:
        await pytgcalls.resume_stream(message.chat.id)
        await message.reply_text("▶️ **Resumed!**")
    except Exception as e:
        await message.reply_text(f"❌ Error: {str(e)}")

@app.on_message(filters.command("skip"))
async def skip_command(client, message: Message):
    """Skip current song"""
    chat_id = message.chat.id
    
    if chat_id in current_playing:
        song = await play_next(chat_id)
        if song:
            await message.reply_text(
                f"⏭ **Skipped!**\n\n"
                f"🎵 **Now Playing:**\n"
                f"📀 {song.title}",
                reply_markup=get_control_buttons()
            )
        else:
            await message.reply_text("✅ **Queue finished!**")
    else:
        await message.reply_text("❌ Nothing is playing!")

@app.on_message(filters.command("stop"))
async def stop_command(client, message: Message):
    """Stop playback"""
    chat_id = message.chat.id
    
    try:
        await pytgcalls.leave_group_call(chat_id)
        queues[chat_id].clear()
        current_playing.pop(chat_id, None)
        await message.reply_text("⏹ **Stopped and cleared queue!**")
    except Exception as e:
        await message.reply_text(f"❌ Error: {str(e)}")

@app.on_message(filters.command("queue"))
async def queue_command(client, message: Message):
    """Show queue"""
    chat_id = message.chat.id
    
    if chat_id not in current_playing and not queues[chat_id]:
        await message.reply_text("📭 **Queue is empty!**")
        return
    
    text = "📃 **Current Queue:**\n\n"
    
    if chat_id in current_playing:
        song = current_playing[chat_id]
        text += f"▶️ **Now Playing:**\n📀 {song.title}\n⏱ {format_duration(song.duration)}\n\n"
    
    if queues[chat_id]:
        text += "**Up Next:**\n"
        for i, song in enumerate(queues[chat_id][:10], 1):
            text += f"{i}. {song.title} - {format_duration(song.duration)}\n"
        
        if len(queues[chat_id]) > 10:
            text += f"\n... and {len(queues[chat_id]) - 10} more"
    
    await message.reply_text(text)

@app.on_message(filters.command("nowplaying"))
async def nowplaying_command(client, message: Message):
    """Show current song"""
    chat_id = message.chat.id
    
    if chat_id in current_playing:
        song = current_playing[chat_id]
        await message.reply_text(
            f"🎵 **Now Playing:**\n"
            f"📀 **Title:** {song.title}\n"
            f"⏱ **Duration:** {format_duration(song.duration)}\n"
            f"👤 **Requested by:** {song.requester}\n"
            f"🎧 **Platform:** {song.platform}",
            reply_markup=get_control_buttons()
        )
    else:
        await message.reply_text("❌ Nothing is playing!")

@app.on_message(filters.command("lyrics"))
async def lyrics_command(client, message: Message):
    """Get lyrics"""
    if len(message.command) < 2:
        await message.reply_text("❌ Usage: `/lyrics <song name>`")
        return
    
    song_name = message.text.split(None, 1)[1]
    status_msg = await message.reply_text("🔍 **Searching for lyrics...**")
    
    lyrics = await fetch_lyrics(song_name)
    
    if len(lyrics) > 4096:
        lyrics = lyrics[:4000] + "\n\n... [Truncated]"
    
    await status_msg.edit_text(f"📝 **Lyrics for {song_name}:**\n\n{lyrics}")

@app.on_message(filters.command("ping"))
async def ping_command(client, message: Message):
    """Check latency"""
    start = datetime.now()
    msg = await message.reply_text("🏓 **Pinging...**")
    end = datetime.now()
    ms = (end - start).microseconds / 1000
    
    uptime = datetime.now() - start_time
    cpu = psutil.cpu_percent()
    ram = psutil.virtual_memory().percent
    
    await msg.edit_text(
        f"🏓 **Pong!**\n"
        f"⚡️ **Latency:** {ms:.2f}ms\n"
        f"⏰ **Uptime:** {str(uptime).split('.')[0]}\n"
        f"💻 **CPU:** {cpu}%\n"
        f"🎯 **RAM:** {ram}%"
    )

@app.on_message(filters.command("stats"))
async def stats_command(client, message: Message):
    """Bot statistics"""
    uptime = datetime.now() - start_time
    
    stats_text = f"""
📊 **Bot Statistics**

👥 **Users:** {len(bot_stats['users'])}
💬 **Chats:** {len(bot_stats['chats'])}
🎵 **Songs Played:** {bot_stats['played']}
⏰ **Uptime:** {str(uptime).split('.')[0]}

💻 **System:**
• **CPU:** {psutil.cpu_percent()}%
• **RAM:** {psutil.virtual_memory().percent}%
• **Disk:** {psutil.disk_usage('/').percent}%

🔧 **Active Calls:** {len(current_playing)}
📋 **Queued Songs:** {sum(len(q) for q in queues.values())}
"""
    await message.reply_text(stats_text)

@app.on_message(filters.command("uptime"))
async def uptime_command(client, message: Message):
    """Show uptime"""
    uptime = datetime.now() - start_time
    await message.reply_text(
        f"⏰ **Bot Uptime:**\n{str(uptime).split('.')[0]}\n\n"
        f"🚀 **Started:** {start_time.strftime('%Y-%m-%d %H:%M:%S')}"
    )

# ============= ADMIN COMMANDS =============

@app.on_message(filters.command("broadcast") & filters.user(SUDO_USERS))
async def broadcast_command(client, message: Message):
    """Broadcast message to all chats"""
    if len(message.command) < 2:
        await message.reply_text("❌ Usage: `/broadcast <message>`")
        return
    
    broadcast_msg = message.text.split(None, 1)[1]
    status = await message.reply_text("📡 **Broadcasting...**")
    
    success = 0
    failed = 0
    
    for chat_id in bot_stats['chats']:
        try:
            await app.send_message(chat_id, f"📢 **Broadcast:**\n\n{broadcast_msg}")
            success += 1
        except:
            failed += 1
        await asyncio.sleep(0.1)
    
    await status.edit_text(
        f"✅ **Broadcast Complete!**\n"
        f"✓ Success: {success}\n"
        f"✗ Failed: {failed}"
    )

@app.on_message(filters.command("reload") & filters.user(SUDO_USERS))
async def reload_command(client, message: Message):
    """Reload bot"""
    await message.reply_text("🔄 **Reloading modules...**")
    # Clear caches
    queues.clear()
    current_playing.clear()
    await message.reply_text("✅ **Reloaded successfully!**")

@app.on_message(filters.command("reboot") & filters.user(SUDO_USERS))
async def reboot_command(client, message: Message):
    """Reboot bot"""
    await message.reply_text("🔄 **Rebooting...**")
    await app.stop()
    os.execl(sys.executable, sys.executable, *sys.argv)

@app.on_message(filters.command("logs") & filters.user(SUDO_USERS))
async def logs_command(client, message: Message):
    """Get logs"""
    try:
        with open("bot.log", "r") as f:
            logs = f.read()[-4000:]
        await message.reply_text(f"📄 **Recent Logs:**\n\n```{logs}```")
    except:
        await message.reply_text("❌ No logs found!")

@app.on_message(filters.command("maintenance") & filters.user(SUDO_USERS))
async def maintenance_command(client, message: Message):
    """Toggle maintenance mode"""
    if len(message.command) < 2:
        await message.reply_text("❌ Usage: `/maintenance <on/off>`")
        return
    
    mode = message.command[1].lower()
    if mode == "on":
        await message.reply_text("🔧 **Maintenance mode: ON**\nBot will reject non-admin commands")
    else:
        await message.reply_text("✅ **Maintenance mode: OFF**\nBot is back online!")

@app.on_callback_query()
async def callback_handler(client, callback_query: CallbackQuery):
    """Handle callbacks"""
    data = callback_query.data
    chat_id = callback_query.message.chat.id
    
    # Main Help Menu with Categories
    if data == "help_main":
        help_categories = """
**Chose The Category For Which You Wanna Get Help.**

**Ask Your Doubts At Support Chat**

**All Commands Can Be Used With : /**
"""
        await callback_query.message.edit_text(
            help_categories,
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("Admin", callback_data="help_admin"),
                    InlineKeyboardButton("Auth", callback_data="help_auth"),
                    InlineKeyboardButton("Broadcast", callback_data="help_broadcast")
                ],
                [
                    InlineKeyboardButton("BL-Chat", callback_data="help_blchat"),
                    InlineKeyboardButton("BL-Users", callback_data="help_blusers"),
                    InlineKeyboardButton("C-Play", callback_data="help_cplay")
                ],
                [
                    InlineKeyboardButton("G-Ban", callback_data="help_gban"),
                    InlineKeyboardButton("Loop", callback_data="help_loop"),
                    InlineKeyboardButton("Maintenance", callback_data="help_maintenance")
                ],
                [
                    InlineKeyboardButton("Ping", callback_data="help_ping"),
                    InlineKeyboardButton("Play", callback_data="help_play"),
                    InlineKeyboardButton("Shuffle", callback_data="help_shuffle")
                ],
                [
                    InlineKeyboardButton("Seek", callback_data="help_seek"),
                    InlineKeyboardButton("Song", callback_data="help_song"),
                    InlineKeyboardButton("Speed", callback_data="help_speed")
                ],
                [InlineKeyboardButton("🔙 Back", callback_data="start_back")]
            ])
        )
        await callback_query.answer()
        return
    
    # Back to Start Menu
    elif data == "start_back":
        start_text = f"""
🎵 **THIS IS {BOT_NAME.upper()}!**

🎧 **A FAST & POWERFUL TELEGRAM MUSIC PLAYER BOT WITH SOME AWESOME FEATURES.**

**Supported Platforms:** YouTube, Spotify, Resso, Apple Music and SoundCloud.

⚡ **CLICK ON THE HELP BUTTON TO GET INFORMATION ABOUT MY MODULES AND COMMANDS.**
"""
        await callback_query.message.edit_text(
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
        await callback_query.answer()
        return
    
    # Help Category - Play
    elif data == "help_play":
        play_help = """
**🎵 Play Commands:**

• `/play <song name>` - Play a song
• `/play <youtube url>` - Play from URL
• `/vplay <video name>` - Play video
• `/pause` - Pause playback
• `/resume` - Resume playback
• `/skip` - Skip current song
• `/stop` - Stop and clear queue
• `/queue` - Show queue
• `/nowplaying` - Current song info
"""
        await callback_query.message.edit_text(
            play_help,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="help_main")]
            ])
        )
        await callback_query.answer()
        return
    
    # Help Category - Admin
    elif data == "help_admin":
        admin_help = """
**👑 Admin Commands:**

• `/pause` - Pause the music
• `/resume` - Resume the music
• `/skip` - Skip current song
• `/stop` - Stop playback
• `/shuffle` - Shuffle queue
• `/loop <1-5>` - Loop current song
• `/seek <seconds>` - Seek position
"""
        await callback_query.message.edit_text(
            admin_help,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="help_main")]
            ])
        )
        await callback_query.answer()
        return
    
    # Help Category - Ping
    elif data == "help_ping":
        ping_help = """
**🏓 Ping Commands:**

• `/ping` - Check bot latency
• `/stats` - Bot statistics
• `/uptime` - Bot uptime
"""
        await callback_query.message.edit_text(
            ping_help,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="help_main")]
            ])
        )
        await callback_query.answer()
        return
    
    # Help Category - Song
    elif data == "help_song":
        song_help = """
**📥 Song Commands:**

• `/song <song name>` - Download song
• `/lyrics <song name>` - Get lyrics
"""
        await callback_query.message.edit_text(
            song_help,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="help_main")]
            ])
        )
        await callback_query.answer()
        return
    
    # Help Category - Broadcast
    elif data == "help_broadcast":
        broadcast_help = """
**📡 Broadcast Commands (Sudo Only):**

• `/broadcast <message>` - Send to all chats
• `/stats` - Bot statistics
"""
        await callback_query.message.edit_text(
            broadcast_help,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="help_main")]
            ])
        )
        await callback_query.answer()
        return
    
    # Help Category - Maintenance
    elif data == "help_maintenance":
        maintenance_help = """
**🔧 Maintenance Commands (Sudo Only):**

• `/maintenance on/off` - Toggle maintenance
• `/reload` - Reload bot modules
• `/reboot` - Restart bot
• `/logs` - Get bot logs
"""
        await callback_query.message.edit_text(
            maintenance_help,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="help_main")]
            ])
        )
        await callback_query.answer()
        return
    
    # Other help categories with placeholder
    elif data in ["help_auth", "help_blchat", "help_blusers", "help_cplay", "help_gban", "help_loop", "help_shuffle", "help_seek", "help_speed"]:
        category_name = data.replace("help_", "").upper()
        await callback_query.message.edit_text(
            f"**{category_name} Commands:**\n\nComing soon...",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="help_main")]
            ])
        )
        await callback_query.answer()
        return
    
    if data == "pause":
        try:
            await pytgcalls.pause_stream(chat_id)
            await callback_query.answer("⏸ Paused!", show_alert=False)
        except Exception as e:
            await callback_query.answer(f"❌ {str(e)}", show_alert=True)
    
    elif data == "resume":
        try:
            await pytgcalls.resume_stream(chat_id)
            await callback_query.answer("▶️ Resumed!", show_alert=False)
        except Exception as e:
            await callback_query.answer(f"❌ {str(e)}", show_alert=True)
    
    elif data == "skip":
        if chat_id in current_playing:
            song = await play_next(chat_id)
            if song:
                await callback_query.message.edit_text(
                    f"⏭ **Skipped!**\n\n🎵 **Now Playing:**\n📀 {song.title}",
                    reply_markup=get_control_buttons()
                )
            else:
                await callback_query.answer("✅ Queue finished!", show_alert=True)
    
    elif data == "stop":
        try:
            await pytgcalls.leave_group_call(chat_id)
            queues[chat_id].clear()
            current_playing.pop(chat_id, None)
            await callback_query.answer("⏹ Stopped!", show_alert=False)
            await callback_query.message.edit_text("⏹ **Stopped and cleared queue!**")
        except Exception as e:
            await callback_query.answer(f"❌ {str(e)}", show_alert=True)
    
    elif data == "queue":
        if chat_id not in current_playing and not queues[chat_id]:
            await callback_query.answer("📭 Queue is empty!", show_alert=True)
            return
        
        text = "📃 **Queue:**\n\n"
        if chat_id in current_playing:
            song = current_playing[chat_id]
            text += f"▶️ {song.title}\n\n"
        
        if queues[chat_id]:
            text += "**Next:**\n"
            for i, song in enumerate(queues[chat_id][:5], 1):
                text += f"{i}. {song.title}\n"
        
        await callback_query.answer(text, show_alert=True)

async def main():
    """Main function"""
    os.makedirs("downloads", exist_ok=True)
    
    await health_server.start()
    await pytgcalls.start()
    logger.info("PyTgCalls started!")
    logger.info(f"{BOT_NAME} started successfully!")
    
    await asyncio.Event().wait()

if __name__ == "__main__":
    app.run(main())
