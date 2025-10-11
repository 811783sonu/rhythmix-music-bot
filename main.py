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

# YT-DLP options - FIXED FOR BOT DETECTION
ydl_opts = {
    'format': 'bestaudio/best',
    'outtmpl': 'downloads/%(id)s.%(ext)s',
    'quiet': True,
    'no_warnings': True,
    'extract_flat': False,
    'nocheckcertificate': True,
    'geo_bypass': True,
    'cookiefile': 'cookies.txt',
    'extractor_args': {
        'youtube': {
            'player_client': ['android', 'web'],
        }
    },
    'http_headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-us,en;q=0.5',
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
    """Download and extract audio info with retry"""
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            if attempt > 0:
                await asyncio.sleep(3 * attempt)
            
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
            if "Sign in to confirm" in str(e):
                if attempt < max_retries - 1:
                    continue
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
    """Play next song"""
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
            ]
        ])
    )

# ============= MUSIC COMMANDS =============

@app.on_message(filters.command(["play", "p"]) & ~filters.private)
async def play_command(client, message: Message):
    """Play music"""
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    # Check maintenance
    if maintenance_mode and not is_sudo(user_id):
        await message.reply_text("🔧 **Bot is under maintenance!**\nPlease try again later.")
        return
    
    # Check blocked
    if user_id in blocked_users:
        return
    if chat_id in blocked_chats:
        await app.leave_chat(chat_id)
        return
    
    bot_stats['users'].add(user_id)
    bot_stats['chats'].add(chat_id)
    
    if len(message.command) < 2 and not message.reply_to_message:
        await message.reply_text("❌ **Usage:** `/play <song name or URL>`")
        return
    
    query = message.text.split(None, 1)[1] if len(message.command) > 1 else "audio"
    status_msg = await message.reply_text("🔍 **Searching...**")
    
    try:
        song_info = await download_song(query)
        
        if not song_info:
            await status_msg.edit_text("❌ **Could not find the song!**\nPlease try again or use a different query.")
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
                    f"🎵 **Now Playing:**\n\n"
                    f"📀 **Title:** {playing_song.title}\n"
                    f"⏱ **Duration:** {format_duration(playing_song.duration)}\n"
                    f"👤 **Requested by:** {playing_song.requester}\n"
                    f"🎧 **Platform:** {playing_song.platform}",
                    reply_markup=get_control_buttons(),
                    disable_web_page_preview=True
                )
            else:
                await status_msg.edit_text("❌ **Failed to play!**\nMake sure bot is admin and voice chat is active.")
        else:
            position = len(queues[chat_id])
            await status_msg.edit_text(
                f"✅ **Added to Queue!**\n\n"
                f"📀 **Title:** {song.title}\n"
                f"⏱ **Duration:** {format_duration(song.duration)}\n"
                f"📊 **Position:** #{position}",
                disable_web_page_preview=True
            )
    except Exception as e:
        logger.error(f"Play error: {e}")
        await status_msg.edit_text(f"❌ **Error:** {str(e)}")

@app.on_message(filters.command("pause") & ~filters.private)
async def pause_command(client, message: Message):
    """Pause playback"""
    if not await is_admin(message.chat.id, message.from_user.id):
        await message.reply_text("❌ **Only admins can use this!**")
        return
    
    try:
        await pytgcalls.pause_stream(message.chat.id)
        await message.reply_text("⏸ **Paused!**")
    except Exception as e:
        await message.reply_text(f"❌ **Error:** {str(e)}")

@app.on_message(filters.command("resume") & ~filters.private)
async def resume_command(client, message: Message):
    """Resume playback"""
    if not await is_admin(message.chat.id, message.from_user.id):
        await message.reply_text("❌ **Only admins can use this!**")
        return
    
    try:
        await pytgcalls.resume_stream(message.chat.id)
        await message.reply_text("▶️ **Resumed!**")
    except Exception as e:
        await message.reply_text(f"❌ **Error:** {str(e)}")

@app.on_message(filters.command(["skip", "next"]) & ~filters.private)
async def skip_command(client, message: Message):
    """Skip song"""
    if not await is_admin(message.chat.id, message.from_user.id):
        await message.reply_text("❌ **Only admins can use this!**")
        return
    
    chat_id = message.chat.id
    
    if chat_id in current_playing:
        song = await play_next(chat_id)
        if song:
            await message.reply_text(
                f"⏭ **Skipped!**\n\n"
                f"🎵 **Now Playing:** {song.title}",
                reply_markup=get_control_buttons()
            )
        else:
            await message.reply_text("✅ **Queue finished!**")
    else:
        await message.reply_text("❌ **Nothing is playing!**")

@app.on_message(filters.command(["stop", "end"]) & ~filters.private)
async def stop_command(client, message: Message):
    """Stop playback"""
    if not await is_admin(message.chat.id, message.from_user.id):
        await message.reply_text("❌ **Only admins can use this!**")
        return
    
    chat_id = message.chat.id
    
    try:
        await pytgcalls.leave_group_call(chat_id)
        queues[chat_id].clear()
        current_playing.pop(chat_id, None)
        await message.reply_text("⏹ **Stopped and cleared queue!**")
    except Exception as e:
        await message.reply_text(f"❌ **Error:** {str(e)}")

@app.on_message(filters.command("queue") & ~filters.private)
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

@app.on_message(filters.command(["nowplaying", "np"]) & ~filters.private)
async def nowplaying_command(client, message: Message):
    """Current song info"""
    chat_id = message.chat.id
    
    if chat_id in current_playing:
        song = current_playing[chat_id]
        await message.reply_text(
            f"🎵 **Now Playing:**\n\n"
            f"📀 **Title:** {song.title}\n"
            f"⏱ **Duration:** {format_duration(song.duration)}\n"
            f"👤 **Requested by:** {song.requester}\n"
            f"🎧 **Platform:** {song.platform}",
            reply_markup=get_control_buttons()
        )
    else:
        await message.reply_text("❌ **Nothing is playing!**")

@app.on_message(filters.command("lyrics"))
async def lyrics_command(client, message: Message):
    """Get lyrics"""
    if len(message.command) < 2:
        await message.reply_text("❌ **Usage:** `/lyrics <song name>`")
        return
    
    song_name = message.text.split(None, 1)[1]
    status_msg = await message.reply_text("🔍 **Searching for lyrics...**")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://api.lyrics.ovh/v1/artist/{song_name}") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    lyrics = data.get('lyrics', 'Lyrics not found')
                    if len(lyrics) > 4000:
                        lyrics = lyrics[:4000] + "\n\n... [Truncated]"
                    await status_msg.edit_text(f"📝 **Lyrics:**\n\n{lyrics}")
                else:
                    await status_msg.edit_text("❌ **Lyrics not found!**")
    except:
        await status_msg.edit_text("❌ **Unable to fetch lyrics!**")

# ============= AUTH COMMANDS =============

@app.on_message(filters.command("auth") & ~filters.private)
async def auth_command(client, message: Message):
    """Add auth user"""
    if not await is_admin(message.chat.id, message.from_user.id):
        await message.reply_text("❌ **Only admins can use this!**")
        return
    
    if message.reply_to_message:
        user_id = message.reply_to_message.from_user.id
        user_name = message.reply_to_message.from_user.mention
    elif len(message.command) > 1:
        try:
            user = await client.get_users(message.command[1])
            user_id = user.id
            user_name = user.mention
        except:
            await message.reply_text("❌ **User not found!**")
            return
    else:
        await message.reply_text("❌ **Reply to a user or provide username/ID!**")
        return
    
    auth_users[message.chat.id].add(user_id)
    await message.reply_text(f"✅ **{user_name} added to AUTH LIST!**")

@app.on_message(filters.command("unauth") & ~filters.private)
async def unauth_command(client, message: Message):
    """Remove auth user"""
    if not await is_admin(message.chat.id, message.from_user.id):
        await message.reply_text("❌ **Only admins can use this!**")
        return
    
    if message.reply_to_message:
        user_id = message.reply_to_message.from_user.id
        user_name = message.reply_to_message.from_user.mention
    elif len(message.command) > 1:
        try:
            user = await client.get_users(message.command[1])
            user_id = user.id
            user_name = user.mention
        except:
            await message.reply_text("❌ **User not found!**")
            return
    else:
        await message.reply_text("❌ **Reply to a user or provide username/ID!**")
        return
    
    if user_id in auth_users[message.chat.id]:
        auth_users[message.chat.id].remove(user_id)
        await message.reply_text(f"✅ **{user_name} removed from AUTH LIST!**")
    else:
        await message.reply_text("❌ **User not in AUTH LIST!**")

@app.on_message(filters.command("authusers") & ~filters.private)
async def authusers_command(client, message: Message):
    """List auth users"""
    if not auth_users[message.chat.id]:
        await message.reply_text("📭 **No auth users in this chat!**")
        return
    
    text = "👥 **Auth Users:**\n\n"
    for i, user_id in enumerate(auth_users[message.chat.id], 1):
        try:
            user = await client.get_users(user_id)
            text += f"{i}. {user.mention} (`{user_id}`)\n"
        except:
            text += f"{i}. User ID: `{user_id}`\n"
    
    await message.reply_text(text)

# ============= SUDO COMMANDS =============

@app.on_message(filters.command("broadcast") & filters.user(SUDO_USERS))
async def broadcast_command(client, message: Message):
    """Broadcast message"""
    if len(message.command) < 2 and not message.reply_to_message:
        await message.reply_text("❌ **Usage:** `/broadcast <message>` or reply to a message")
        return
    
    broadcast_msg = message.text.split(None, 1)[1] if len(message.command) > 1 else message.reply_to_message.text
    status = await message.reply_text("📡 **Broadcasting...**")
    
    success = 0
    failed = 0
    
    for chat_id in list(bot_stats['chats']):
        try:
            await app.send_message(chat_id, f"📢 **Broadcast Message:**\n\n{broadcast_msg}")
            success += 1
        except Exception as e:
            logger.error(f"Broadcast failed for {chat_id}: {e}")
            failed += 1
        await asyncio.sleep(0.1)
    
    await status.edit_text(
        f"✅ **Broadcast Complete!**\n\n"
        f"✓ **Success:** {success}\n"
        f"✗ **Failed:** {failed}"
    )

@app.on_message(filters.command("gban") & filters.user(SUDO_USERS))
async def gban_command(client, message: Message):
    """Global ban user"""
    if message.reply_to_message:
        user_id = message.reply_to_message.from_user.id
        user_name = message.reply_to_message.from_user.mention
    elif len(message.command) > 1:
        try:
            user = await client.get_users(message.command[1])
            user_id = user.id
            user_name = user.mention
        except:
            await message.reply_text("❌ **User not found!**")
            return
    else:
        await message.reply_text("❌ **Reply to a user or provide username/ID!**")
        return
    
    if user_id in SUDO_USERS:
        await message.reply_text("❌ **Cannot ban sudo users!**")
        return
    
    gbanned_users.add(user_id)
    await message.reply_text(f"✅ **{user_name} has been globally banned!**")

@app.on_message(filters.command("ungban") & filters.user(SUDO_USERS))
async def ungban_command(client, message: Message):
    """Remove global ban"""
    if message.reply_to_message:
        user_id = message.reply_to_message.from_user.id
        user_name = message.reply_to_message.from_user.mention
    elif len(message.command) > 1:
        try:
            user = await client.get_users(message.command[1])
            user_id = user.id
            user_name = user.mention
        except:
            await message.reply_text("❌ **User not found!**")
            return
    else:
        await message.reply_text("❌ **Reply to a user or provide username/ID!**")
        return
    
    if user_id in gbanned_users:
        gbanned_users.remove(user_id)
        await message.reply_text(f"✅ **{user_name} has been ungbanned!**")
    else:
        await message.reply_text("❌ **User not gbanned!**")

@app.on_message(filters.command("block") & filters.user(SUDO_USERS))
async def block_command(client, message: Message):
    """Block user"""
    if message.reply_to_message:
        user_id = message.reply_to_message.from_user.id
        user_name = message.reply_to_message.from_user.mention
    elif len(message.command) > 1:
        try:
            user = await client.get_users(message.command[1])
            user_id = user.id
            user_name = user.mention
        except:
            await message.reply_text("❌ **User not found!**")
            return
    else:
        await message.reply_text("❌ **Reply to a user or provide username/ID!**")
        return
    
    blocked_users.add(user_id)
    await message.reply_text(f"✅ **{user_name} has been blocked!**")

@app.on_message(filters.command("unblock") & filters.user(SUDO_USERS))
async def unblock_command(client, message: Message):
    """Unblock user"""
    if message.reply_to_message:
        user_id = message.reply_to_message.from_user.id
        user_name = message.reply_to_message.from_user.mention
    elif len(message.command) > 1:
        try:
            user = await client.get_users(message.command[1])
            user_id = user.id
            user_name = user.mention
        except:
            await message.reply_text("❌ **User not found!**")
            return
    else:
        await message.reply_text("❌ **Reply to a user or provide username/ID!**")
        return
    
    if user_id in blocked_users:
        blocked_users.remove(user_id)
        await message.reply_text(f"✅ **{user_name} has been unblocked!**")
    else:
        await message.reply_text("❌ **User not blocked!**")

@app.on_message(filters.command("blacklistchat") & filters.user(SUDO_USERS))
async def blacklist_chat_command(client, message: Message):
    """Blacklist chat"""
    if len(message.command) > 1:
        chat_id = int(message.command[1])
    else:
        chat_id = message.chat.id
    
    blocked_chats.add(chat_id)
    await message.reply_text(f"✅ **Chat `{chat_id}` has been blacklisted!**")
    try:
        await app.leave_chat(chat_id)
    except:
        pass

@app.on_message(filters.command("whitelistchat") & filters.user(SUDO_USERS))
async def whitelist_chat_command(client, message: Message):
    """Whitelist chat"""
    if len(message.command) > 1:
        chat_id = int(message.command[1])
    else:
        await message.reply_text("❌ **Provide chat ID!**")
        return
    
    if chat_id in blocked_chats:
        blocked_chats.remove(chat_id)
        await message.reply_text(f"✅ **Chat `{chat_id}` has been whitelisted!**")
    else:
        await message.reply_text("❌ **Chat not blacklisted!**")

@app.on_message(filters.command("maintenance") & filters.user(SUDO_USERS))
async def maintenance_command(client, message: Message):
    """Toggle maintenance"""
    global maintenance_mode
    
    if len(message.command) < 2:
        status = "ON" if maintenance_mode else "OFF"
        await message.reply_text(f"🔧 **Maintenance Mode:** {status}")
        return
    
    mode = message.command[1].lower()
    if mode == "on":
        maintenance_mode = True
        await message.reply_text("🔧 **Maintenance mode: ON**\nOnly sudo users can use the bot now.")
    elif mode == "off":
        maintenance_mode = False
        await message.reply_text("✅ **Maintenance mode: OFF**\nBot is back online for everyone!")
    else:
        await message.reply_text("❌ **Usage:** `/maintenance on/off`")

@app.on_message(filters.command("reload") & filters.user(SUDO_USERS))
async def reload_command(client, message: Message):
    """Reload bot"""
    await message.reply_text("🔄 **Reloading modules...**")
    queues.clear()
    current_playing.clear()
    auth_users.clear()
    await message.reply_text("✅ **Reloaded successfully!**")

@app.on_message(filters.command("reboot") & filters.user(SUDO_USERS))
async def reboot_command(client, message: Message):
    """Reboot bot"""
    await message.reply_text("🔄 **Rebooting bot...**\nBot will be back in a moment!")
    await app.stop()
    os.execl(sys.executable, sys.executable, *sys.argv)

@app.on_message(filters.command("logs") & filters.user(SUDO_USERS))
async def logs_command(client, message: Message):
    """Get logs"""
    try:
        if os.path.exists("bot.log"):
            await message.reply_document("bot.log", caption="📄 **Bot Logs**")
        else:
            await message.reply_text("❌ **No logs found!**")
    except Exception as e:
        await message.reply_text(f"❌ **Error:** {str(e)}")

# ============= INFO COMMANDS =============

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
        f"🏓 **Pong!**\n\n"
        f"⚡ **Latency:** {ms:.2f}ms\n"
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

# ============= CALLBACK HANDLERS =============

@app.on_callback_query()
async def callback_handler(client, callback_query: CallbackQuery):
    """Handle callbacks"""
    data = callback_query.data
    chat_id = callback_query.message.chat.id
    user_id = callback_query.from_user.id
    
    # Main Help Menu
    if data == "help_main":
        help_categories = """
**Choose The Category For Which You Wanna Get Help.**

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
    
    # Back to Start
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
    
    # Help Categories
    elif data == "help_admin":
        admin_help = """
**👑 ADMIN COMMANDS**

**Admin Commands in Group:**
• `/pause` - Pause the playing music
• `/resume` - Resume the paused music
• `/skip` - Skip the current playing music
• `/end` or `/stop` - Stop playing music
• `/queue` - Check the queue list

**Auth Users:**
• `/auth <username>` - Add user to AUTH LIST
• `/unauth <username>` - Remove from AUTH LIST
• `/authusers` - Check AUTH LIST
"""
        await callback_query.message.edit_text(admin_help, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="help_main")]]))
        await callback_query.answer()
        return
    
    elif data == "help_auth":
        auth_help = """
**👥 AUTH USERS COMMANDS**

**What is Auth Users?**
Auth users can use admin commands without admin rights.

**Commands:**
• `/auth <username>` - Add to AUTH LIST
• `/unauth <username>` - Remove from AUTH LIST
• `/authusers` - Check AUTH LIST
"""
        await callback_query.message.edit_text(auth_help, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="help_main")]]))
        await callback_query.answer()
        return
    
    elif data == "help_broadcast":
        broadcast_help = """
**📡 BROADCAST COMMANDS**

**Sudo Users Only:**
• `/broadcast <message>` - Broadcast to all chats
• `/stats` - Get bot statistics
"""
        await callback_query.message.edit_text(broadcast_help, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="help_main")]]))
        await callback_query.answer()
        return
    
    elif data == "help_blchat":
        blchat_help = """
**🚫 BLACKLIST CHAT COMMANDS**

**Sudo Users Only:**
• `/blacklistchat <chat_id>` - Blacklist a chat
• `/whitelistchat <chat_id>` - Remove from blacklist
"""
        await callback_query.message.edit_text(blchat_help, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="help_main")]]))
        await callback_query.answer()
        return
    
    elif data == "help_blusers":
        bluser_help = """
**🚫 BLACKLIST USERS COMMANDS**

**Sudo Users Only:**
• `/block <username>` - Block a user
• `/unblock <username>` - Unblock a user
"""
        await callback_query.message.edit_text(bluser_help, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="help_main")]]))
        await callback_query.answer()
        return
    
    elif data == "help_cplay":
        cplay_help = """
**📢 CHANNEL PLAY COMMANDS**

**Play in channel voice chat:**
• `/cplay <song>` - Play in channel
• `/cpause` - Pause channel music
• `/cresume` - Resume channel music
• `/cskip` - Skip channel music
"""
        await callback_query.message.edit_text(cplay_help, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="help_main")]]))
        await callback_query.answer()
        return
    
    elif data == "help_gban":
        gban_help = """
**🔨 GLOBAL BAN COMMANDS**

**Sudo Users Only:**
• `/gban <username>` - Globally ban a user
• `/ungban <username>` - Remove global ban
"""
        await callback_query.message.edit_text(gban_help, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="help_main")]]))
        await callback_query.answer()
        return
    
    elif data == "help_loop":
        loop_help = """
**🔁 LOOP COMMANDS**

**Enable/Disable looping:**
• `/loop` - Enable loop for current song
• `/loop disable` - Disable loop mode
"""
        await callback_query.message.edit_text(loop_help, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="help_main")]]))
        await callback_query.answer()
        return
    
    elif data == "help_maintenance":
        maintenance_help = """
**🔧 MAINTENANCE COMMANDS**

**Sudo Users Only:**
• `/maintenance on/off` - Toggle maintenance
• `/reload` - Reload bot modules
• `/reboot` - Restart the bot
• `/logs` - Get bot logs
"""
        await callback_query.message.edit_text(maintenance_help, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="help_main")]]))
        await callback_query.answer()
        return
    
    elif data == "help_ping":
        ping_help = """
**🏓 PING & STATS COMMANDS**

**Check Bot Performance:**
• `/ping` - Check bot latency
• `/stats` - Bot statistics
• `/uptime` - Bot uptime
"""
        await callback_query.message.edit_text(ping_help, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="help_main")]]))
        await callback_query.answer()
        return
    
    elif data == "help_play":
        play_help = """
**🎵 PLAY COMMANDS**

**Play Music:**
• `/play <song name>` - Play song
• `/play <youtube url>` - Play from URL
• `/queue` - Show queue
• `/nowplaying` - Current song info
"""
        await callback_query.message.edit_text(play_help, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="help_main")]]))
        await callback_query.answer()
        return
    
    elif data == "help_seek":
        seek_help = """
**⏩ SEEK COMMANDS**

**Control playback position:**
• `/seek <seconds>` - Seek to specific time
"""
        await callback_query.message.edit_text(seek_help, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="help_main")]]))
        await callback_query.answer()
        return
    
    elif data == "help_shuffle":
        shuffle_help = """
**🔀 SHUFFLE COMMANDS**

**Randomize your queue:**
• `/shuffle` - Shuffle the queue
"""
        await callback_query.message.edit_text(shuffle_help, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="help_main")]]))
        await callback_query.answer()
        return
    
    elif data == "help_song":
        song_help = """
**📥 SONG COMMANDS**

**Download Songs:**
• `/song <song name>` - Download song
• `/lyrics <song name>` - Get lyrics
"""
        await callback_query.message.edit_text(song_help, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="help_main")]]))
        await callback_query.answer()
        return
    
    elif data == "help_speed":
        speed_help = """
**⚡ SPEED COMMANDS**

**Control playback speed:**
• `/speed <value>` - Set playback speed
• `/speed 1` - Normal speed
"""
        await callback_query.message.edit_text(speed_help, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="help_main")]]))
        await callback_query.answer()
        return
    
    # Playback Controls
    if data == "pause":
        if not await is_admin(chat_id, user_id):
            await callback_query.answer("❌ Only admins can use this!", show_alert=True)
            return
        try:
            await pytgcalls.pause_stream(chat_id)
            await callback_query.answer("⏸ Paused!")
        except Exception as e:
            await callback_query.answer(f"❌ {str(e)}", show_alert=True)
    
    elif data == "resume":
        if not await is_admin(chat_id, user_id):
            await callback_query.answer("❌ Only admins can use this!", show_alert=True)
            return
        try:
            await pytgcalls.resume_stream(chat_id)
            await callback_query.answer("▶️ Resumed!")
        except Exception as e:
            await callback_query.answer(f"❌ {str(e)}", show_alert=True)
    
    elif data == "skip":
        if not await is_admin(chat_id, user_id):
            await callback_query.answer("❌ Only admins can use this!", show_alert=True)
            return
        if chat_id in current_playing:
            song = await play_next(chat_id)
            if song:
                await callback_query.message.edit_text(
                    f"⏭ **Skipped!**\n\n🎵 **Now Playing:** {song.title}",
                    reply_markup=get_control_buttons()
                )
                await callback_query.answer("⏭ Skipped!")
            else:
                await callback_query.answer("✅ Queue finished!", show_alert=True)
    
    elif data == "stop":
        if not await is_admin(chat_id, user_id):
            await callback_query.answer("❌ Only admins can use this!", show_alert=True)
            return
        try:
            await pytgcalls.leave_group_call(chat_id)
            queues[chat_id].clear()
            current_playing.pop(chat_id, None)
            await callback_query.message.edit_text("⏹ **Stopped and cleared queue!**")
            await callback_query.answer("⏹ Stopped!")
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
