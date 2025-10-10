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

ydl_opts = {
    'format': 'bestaudio/best',
    'outtmpl': 'downloads/%(id)s.%(ext)s',
    'quiet': True,
    'no_warnings': True,
    'geo_bypass': True,
    'nocheckcertificate': True,
    'noplaylist': True,
    'default_search': 'ytsearch',
    'source_address': '0.0.0.0',
    'extract_flat': False,
    'age_limit': None,
    'cookiesfrombrowser': ('chrome',),  # optional if you have Chrome cookies
    'http_headers': {
        'User-Agent': 'com.google.android.youtube/18.29.38 (Linux; U; Android 14; en_US) gzip',
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.9',
    },
    'extractor_args': {
        'youtube': {
            'player_client': ['android', 'ios'],
        }
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
**👑 ADMIN COMMANDS**

**c** stands for channel play.

**Admin Commands in Group:**

• `/pause` - Pause the playing music.
• `/resume` - Resume the paused music.
• `/skip` - Skip the current playing music.
• `/end` or `/stop` - Stop playing music and clear queue.
• `/player` - Get a interactive player panel.
• `/queue` - Check the queue list.

**Specific Skip:**
• `/skip 2` - Skip music to a specific queued number.

**Loop Stream:**
• `/loop` - Enable/Disable loop for the playing music.

**Auth Users:**
Admin commands can be used by authorized users without admin rights.
• `/auth <username>` - Add a user to AUTH LIST.
• `/unauth <username>` - Remove user from AUTH LIST.
• `/authusers` - Check AUTH LIST of the group.
"""
        await callback_query.message.edit_text(
            admin_help,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="help_main")]
            ])
        )
        await callback_query.answer()
        return
    
    # Help Category - Auth
    elif data == "help_auth":
        auth_help = """
**👥 AUTH USERS COMMANDS**

**What is Auth Users?**
Auth users can use admin commands without admin rights in your chat.

**Admin Commands:**
• `/auth <username>` - Add a user to AUTH LIST.
• `/unauth <username>` - Remove user from AUTH LIST.
• `/authusers` - Check AUTH LIST of the group.

**Example:**
`/auth @username`
`/unauth @username`
"""
        await callback_query.message.edit_text(
            auth_help,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="help_main")]
            ])
        )
        await callback_query.answer()
        return
    
    # Help Category - Broadcast
    elif data == "help_broadcast":
        broadcast_help = """
**📡 BROADCAST COMMANDS**

**Sudo Users Only:**

• `/broadcast <message>` - Broadcast message to all served chats.
• `/broadcast -pin <message>` - Broadcast and pin message in all chats.
• `/broadcast -user <message>` - Broadcast to all users.
• `/broadcast -assistant` - Broadcast from assistant account.

**Statistics:**
• `/stats` - Get bot statistics.
• `/gstats` - Get global statistics.

**Note:** Only sudo users can use broadcast commands!
"""
        await callback_query.message.edit_text(
            broadcast_help,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="help_main")]
            ])
        )
        await callback_query.answer()
        return
    
    # Help Category - BL-Chat
    elif data == "help_blchat":
        blchat_help = """
**🚫 BLACKLIST CHAT COMMANDS**

**Sudo Users Only:**

• `/blacklistchat <chat_id>` - Blacklist a chat from using bot.
• `/whitelistchat <chat_id>` - Remove chat from blacklist.
• `/blacklistedchat` - Check all blacklisted chats.

**What happens when blacklisted?**
Bot will automatically leave the blacklisted chat and won't respond to any commands.

**Example:**
`/blacklistchat -1001234567890`
"""
        await callback_query.message.edit_text(
            blchat_help,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="help_main")]
            ])
        )
        await callback_query.answer()
        return
    
    # Help Category - BL-Users
    elif data == "help_blusers":
        bluser_help = """
**🚫 BLACKLIST USERS COMMANDS**

**Sudo Users Only:**

• `/block <username or user_id>` - Block a user from using bot.
• `/unblock <username or user_id>` - Unblock a user.
• `/blockedusers` - Check all blocked users.

**What happens when blocked?**
Blocked users cannot use any bot commands in any chat.

**Example:**
`/block @username`
`/block 123456789`
`/unblock @username`
"""
        await callback_query.message.edit_text(
            bluser_help,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="help_main")]
            ])
        )
        await callback_query.answer()
        return
    
    # Help Category - C-Play
    elif data == "help_cplay":
        cplay_help = """
**📢 CHANNEL PLAY COMMANDS**

**Play music in channel voice chat:**

• `/cplay <song name>` - Play song in linked channel.
• `/cplay <youtube url>` - Play from URL in channel.
• `/cpause` - Pause channel music.
• `/cresume` - Resume channel music.
• `/cskip` - Skip channel music.
• `/cend` - Stop channel music.

**Setup:**
1. Link your channel to group
2. Make bot admin in both
3. Use /cplay in the group

**Note:** Bot must be admin in both group and channel!
"""
        await callback_query.message.edit_text(
            cplay_help,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="help_main")]
            ])
        )
        await callback_query.answer()
        return
    
    # Help Category - G-Ban
    elif data == "help_gban":
        gban_help = """
**🔨 GLOBAL BAN COMMANDS**

**Sudo Users Only:**

• `/gban <username or user_id>` - Globally ban a user.
• `/ungban <username or user_id>` - Remove global ban.
• `/gbannedusers` - Check all globally banned users.

**What is Global Ban?**
Globally banned users will be automatically banned in all chats where bot is admin.

**Example:**
`/gban @username Reason: Spam`
`/gban 123456789 Reason: Abuse`
`/ungban @username`

**⚠️ Use with caution!**
"""
        await callback_query.message.edit_text(
            gban_help,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="help_main")]
            ])
        )
        await callback_query.answer()
        return
    
    # Help Category - Loop
    elif data == "help_loop":
        loop_help = """
**🔁 LOOP COMMANDS**

**Enable/Disable looping:**

• `/loop` - Enable loop for current playing music.
• `/loop disable` - Disable loop mode.
• `/loop 5` - Loop current song 5 times.

**Loop Types:**
🔂 Loop Current - Repeats current song
🔁 Loop Queue - Repeats entire queue

**Admin Command:**
Only admins and auth users can use loop commands.

**Example:**
`/loop` - Toggle loop
`/loop 3` - Loop 3 times
`/loop disable` - Stop loop
"""
        await callback_query.message.edit_text(
            loop_help,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="help_main")]
            ])
        )
        await callback_query.answer()
        return
    
    # Help Category - Maintenance
    elif data == "help_maintenance":
        maintenance_help = """
**🔧 MAINTENANCE COMMANDS**

**Sudo Users Only:**

• `/maintenance on` - Enable maintenance mode.
• `/maintenance off` - Disable maintenance mode.
• `/reload` - Reload bot modules.
• `/reboot` - Restart the bot.
• `/logs` - Get recent bot logs.
• `/update` - Update bot to latest version.

**What is Maintenance Mode?**
When enabled, only sudo users can use the bot. Normal users will see a maintenance message.

**System Commands:**
• `/sysinfo` - Get system information.
• `/status` - Check bot status.
"""
        await callback_query.message.edit_text(
            maintenance_help,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="help_main")]
            ])
        )
        await callback_query.answer()
        return
    
    # Help Category - Ping
    elif data == "help_ping":
        ping_help = """
**🏓 PING & STATS COMMANDS**

**Check Bot Performance:**

• `/ping` - Check bot ping and system stats.
• `/stats` - Get detailed bot statistics.
• `/uptime` - Check how long bot has been running.

**What you'll see:**
⚡ Bot Latency
💻 CPU Usage
🎯 RAM Usage
💾 Disk Usage
⏰ Uptime
👥 Total Users
💬 Total Chats
🎵 Songs Played

**Available for everyone!**
"""
        await callback_query.message.edit_text(
            ping_help,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="help_main")]
            ])
        )
        await callback_query.answer()
        return
    
    # Help Category - Play
    elif data == "help_play":
        play_help = """
**🎵 PLAY COMMANDS**

**Play Music in Voice Chat:**

• `/play <song name>` - Play song by name.
• `/play <youtube url>` - Play from YouTube URL.
• `/play <reply to audio>` - Play replied audio file.

**Platform Support:**
🎵 YouTube
🎧 Spotify
📱 Resso
🍎 Apple Music
☁️ SoundCloud

**Queue Management:**
• `/queue` - Show current queue.
• `/nowplaying` - Show current song details.

**Examples:**
`/play Faded`
`/play https://youtube.com/watch?v=xxxxx`

**Available for everyone!**
"""
        await callback_query.message.edit_text(
            play_help,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="help_main")]
            ])
        )
        await callback_query.answer()
        return
    
    # Help Category - Seek
    elif data == "help_seek":
        seek_help = """
**⏩ SEEK COMMANDS**

**Control playback position:**

• `/seek <seconds>` - Seek to specific time.
• `/seek 30` - Skip forward 30 seconds.
• `/seekback 15` - Go back 15 seconds.

**Time Format:**
You can use seconds, minutes, or MM:SS format.

**Examples:**
`/seek 45` - Go to 45 seconds
`/seek 1:30` - Go to 1 minute 30 seconds
`/seek 90` - Go to 1 minute 30 seconds
`/seekback 20` - Go back 20 seconds

**Admin Only Command**
Only admins and auth users can seek.
"""
        await callback_query.message.edit_text(
            seek_help,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="help_main")]
            ])
        )
        await callback_query.answer()
        return
    
    # Help Category - Shuffle
    elif data == "help_shuffle":
        shuffle_help = """
**🔀 SHUFFLE COMMANDS**

**Randomize your queue:**

• `/shuffle` - Shuffle the current queue.
• `/queue` - Check queue order after shuffle.

**How it works:**
The shuffle command will randomly reorder all songs in the queue. The currently playing song will not be affected.

**Perfect for:**
✨ Mix up your playlist
🎲 Random song order
🎉 Party mode

**Admin Only Command**
Only admins and auth users can shuffle the queue.
"""
        await callback_query.message.edit_text(
            shuffle_help,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="help_main")]
            ])
        )
        await callback_query.answer()
        return
    
    # Help Category - Song
    elif data == "help_song":
        song_help = """
**📥 SONG DOWNLOAD COMMANDS**

**Download Songs & Lyrics:**

• `/song <song name>` - Download song as audio file.
• `/video <song name>` - Download as video.
• `/lyrics <song name>` - Get song lyrics.

**Features:**
📥 High Quality Audio (320kbps)
🎬 HD Video Download
📝 Synchronized Lyrics
⚡ Fast Download Speed

**Examples:**
`/song Faded Alan Walker`
`/video Shape of You`
`/lyrics Believer Imagine Dragons`

**Available for everyone!**
Download limit: 5 per hour per user.
"""
        await callback_query.message.edit_text(
            song_help,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="help_main")]
            ])
        )
        await callback_query.answer()
        return
    
    # Help Category - Speed
    elif data == "help_speed":
        speed_help = """
**⚡ PLAYBACK SPEED COMMANDS**

**Control playback speed:**

• `/speed` - Check current playback speed.
• `/speed 1.5` - Set speed to 1.5x.
• `/speed 0.5` - Set speed to 0.5x (slow).
• `/speed 2` - Set speed to 2x (fast).

**Speed Range:**
• **0.5x** - Half speed (slow)
• **1.0x** - Normal speed (default)
• **1.5x** - 1.5x faster
• **2.0x** - Double speed

**Examples:**
`/speed 1.25` - Slightly faster
`/speed 0.75` - Slightly slower
`/speed 1` - Normal speed

**Admin Only Command**
"""
        await callback_query.message.edit_text(
            speed_help,
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
