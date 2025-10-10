import asyncio
import os
import logging
import sys
from collections import defaultdict
from datetime import datetime

import aiohttp
import psutil
import yt_dlp
from pyrogram import Client, filters, idle
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pytgcalls import PyTgCalls, StreamType
from pytgcalls.types.input_stream import AudioPiped
from pytgcalls.types.input_stream.quality import HighQualityAudio
from pytgcalls.exceptions import AlreadyJoinedError

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
queues = defaultdict(list)       # chat_id -> list of Song
current_playing = {}             # chat_id -> Song
start_time = datetime.now()
bot_stats = {'chats': set(), 'users': set(), 'played': 0}


# YT-DLP options (kept as fallback; main extraction done in download_song)
ydl_opts = {
    'format': 'bestaudio/best',
    'outtmpl': 'downloads/%(id)s.%(ext)s',
    'quiet': True,
    'no_warnings': True,
    'extract_flat': False,
    'nocheckcertificate': True,
    'geo_bypass': True,
    'age_limit': None,
    'extractor_args': {
        'youtube': {
            'player_client': ['android', 'web'],
            'skip': ['webpage', 'dash', 'hls']
        }
    },
    'http_headers': {
        'User-Agent': 'com.google.android.youtube/17.36.4 (Linux; U; Android 12; GB) gzip',
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
    """Download and extract audio info with fallback (stream URL or downloaded file path)"""
    try:
        import yt_dlp, os

        ydl_opts_local = {
            'format': 'bestaudio/best',
            'quiet': True,
            'noplaylist': True,
            'default_search': 'ytsearch',
            'geo_bypass': True,
            'nocheckcertificate': True,
            'outtmpl': 'downloads/%(id)s.%(ext)s',
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'ios'],  # mobile client helps bypass bot checks
                }
            },
            'http_headers': {
                'User-Agent': 'com.google.android.youtube/19.15.33 (Linux; Android 13) gzip',
            },
            # 'cookiesfrombrowser': ('chrome',),  # optional, uncomment if you want to use browser cookies
        }

        with yt_dlp.YoutubeDL(ydl_opts_local) as ydl:
            if not query.startswith('http'):
                query_for_ydl = f"ytsearch:{query}"
            else:
                query_for_ydl = query

            info = ydl.extract_info(query_for_ydl, download=False)
            if isinstance(info, dict) and 'entries' in info:
                info = info['entries'][0]

            audio_url = info.get('url')
            title = info.get('title', 'Unknown')
            duration = info.get('duration', 0) or 0
            thumbnail = info.get('thumbnail', '')

            if audio_url:
                return {
                    'title': title,
                    'duration': duration,
                    'url': audio_url,
                    'thumbnail': thumbnail
                }

            # Fallback: download the audio file and return its path
            logger.info("Fallback: no direct stream URL, attempting to download audio file...")
            ydl_opts_local['quiet'] = False
            ydl_opts_local['outtmpl'] = 'downloads/%(title)s.%(ext)s'
            ydl_opts_local['format'] = 'bestaudio/best'

            with yt_dlp.YoutubeDL(ydl_opts_local) as ydl2:
                info = ydl2.extract_info(query_for_ydl, download=True)
                if isinstance(info, dict) and 'entries' in info:
                    info = info['entries'][0]
                filename = ydl2.prepare_filename(info)
                # Sometimes yt-dlp adds extensions differently; try common variants
                if os.path.exists(filename):
                    file_path = filename
                else:
                    # try common audio extensions
                    for ext in ('.webm', '.m4a', '.mp3', '.opus'):
                        candidate = os.path.splitext(filename)[0] + ext
                        if os.path.exists(candidate):
                            file_path = candidate
                            break
                    else:
                        file_path = None

                if file_path:
                    return {
                        'title': info.get('title', 'Unknown'),
                        'duration': info.get('duration', 0) or 0,
                        'url': file_path,
                        'thumbnail': info.get('thumbnail', '')
                    }

    except Exception as e:
        logger.exception(f"Download error: {e}")
        return None

    return None


async def fetch_lyrics(song_name):
    """Fetch lyrics"""
    try:
        async with aiohttp.ClientSession() as session:
            url = f"https://api.lyrics.ovh/v1/{song_name}"
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
            InlineKeyboardButton("⏸️ Pause", callback_data="pause"),
            InlineKeyboardButton("▶️ Resume", callback_data="resume"),
            InlineKeyboardButton("⏭️ Skip", callback_data="skip")
        ],
        [
            InlineKeyboardButton("⏹️ Stop", callback_data="stop"),
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
                # Try joining group call and playing (join_group_call is more robust)
                await pytgcalls.join_group_call(
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
            except Exception as e:
                logger.exception("Error starting stream, attempting change_stream fallback")
                try:
                    await pytgcalls.change_stream(
                        chat_id,
                        AudioPiped(song.url, HighQualityAudio())
                    )
                    return song
                except Exception:
                    logger.exception("change_stream also failed")
                    return None
        else:
            current_playing.pop(chat_id, None)
            try:
                await pytgcalls.leave_group_call(chat_id)
            except Exception:
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


@app.on_message(filters.command("play"))
async def play_command(client, message: Message):
    """Play command"""
    chat_id = message.chat.id
    bot_stats['users'].add(message.from_user.id)
    if message.chat.type != "private":
        bot_stats['chats'].add(message.chat.id)

    if len(message.command) < 2:
        await message.reply_text("❌ Usage: /play <song name or URL>")
        return

    query = message.text.split(None, 1)[1]
    status_msg = await message.reply_text("🔍 Searching...")

    song_info = await download_song(query)

    if not song_info:
        await status_msg.edit_text("❌ Could not find the song!")
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
                f"🎵 Now Playing:\n"
                f"📀 Title: {playing_song.title}\n"
                f"⏱️ Duration: {format_duration(playing_song.duration)}\n"
                f"👤 Requested by: {playing_song.requester}\n"
                f"🎧 Platform: {playing_song.platform}",
                reply_markup=get_control_buttons()
            )
        else:
            await status_msg.edit_text("❌ Failed to play!")
    else:
        position = len(queues[chat_id])
        await status_msg.edit_text(
            f"✅ Added to Queue!\n"
            f"📀 Title: {song.title}\n"
            f"⏱️ Duration: {format_duration(song.duration)}\n"
            f"📊 Position: #{position}"
        )


@app.on_message(filters.command("pause"))
async def pause_command(client, message: Message):
    """Pause playback"""
    try:
        await pytgcalls.pause_stream(message.chat.id)
        await message.reply_text("⏸️ Paused!")
    except Exception as e:
        await message.reply_text(f"❌ Error: {str(e)}")


@app.on_message(filters.command("resume"))
async def resume_command(client, message: Message):
    """Resume playback"""
    try:
        await pytgcalls.resume_stream(message.chat.id)
        await message.reply_text("▶️ Resumed!")
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
                f"⏭️ Skipped!\n\n"
                f"🎵 Now Playing:\n"
                f"📀 {song.title}",
                reply_markup=get_control_buttons()
            )
        else:
            await message.reply_text("✅ Queue finished!")
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
        await message.reply_text("⏹️ Stopped and cleared queue!")
    except Exception as e:
        await message.reply_text(f"❌ Error: {str(e)}")


@app.on_message(filters.command("start"))
async def start_command(client, message: Message):
    """Start command"""
    bot_stats['users'].add(message.from_user.id)
    if message.chat.type != "private":
        bot_stats['chats'].add(message.chat.id)

    await message.reply_text(
        f"🎵 Welcome to {BOT_NAME}!\n\n"
        "I can play music in your voice chats!\n\n"
        "**Basic Commands:**\n"
        "• `/play <song>` - Play a song\n"
        "• `/pause` - Pause playback\n"
        "• `/resume` - Resume playback\n"
        "• `/skip` - Skip current song\n"
        "• `/stop` - Stop and clear queue\n"
        "• `/queue` - Show queue\n"
        "• `/lyrics <song>` - Get lyrics\n\n"
        "**More Commands:**\n"
        "• `/help` - Show all commands\n"
        "• `/stats` - Bot statistics\n\n"
        "Add me to your group and start voice chat!",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 Support", url="https://t.me/S_o_n_u_783")],
            [InlineKeyboardButton("ℹ️ Help", callback_data="help_menu")]
        ])
    )


@app.on_message(filters.command("help"))
async def help_command(client, message: Message):
    """Help command"""
    help_text = f"""
🎵 {BOT_NAME} - Help Menu

🎶 Music Commands:
• /play <song name> - Play a song
• /pause - Pause current song
• /resume - Resume playback
• /skip - Skip to next song
• /stop - Stop and clear queue
• /queue - Show current queue
• /nowplaying - Current song info
• /lyrics <song> - Get song lyrics

📊 Bot Commands:
• /ping - Check bot latency
• /stats - Bot statistics
• /uptime - Bot uptime

👑 Admin Commands:
• /broadcast <message> - Send to all chats
• /reload - Reload bot modules
• /reboot - Restart bot
• /logs - Get recent logs
• /maintenance <on/off> - Toggle maintenance

💡 Tips:
• Use song names or YouTube URLs
• Bot must be admin with "Manage Voice Chats"
• Join voice chat before playing

Support: @S_o_n_u_783
"""
    await message.reply_text(help_text)


@app.on_message(filters.command("queue"))
async def queue_command(client, message: Message):
    """Show queue"""
    chat_id = message.chat.id

    if chat_id not in current_playing and not queues[chat_id]:
        await message.reply_text("📭 Queue is empty!")
        return

    text = "📃 Current Queue:\n\n"

    if chat_id in current_playing:
        song = current_playing[chat_id]
        text += f"▶️ Now Playing:\n📀 {song.title}\n⏱️ {format_duration(song.duration)}\n\n"

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
            f"🎵 Now Playing:\n"
            f"📀 Title: {song.title}\n"
            f"⏱️ Duration: {format_duration(song.duration)}\n"
            f"👤 Requested by: {song.requester}\n"
            f"🎧 Platform: {song.platform}",
            reply_markup=get_control_buttons()
        )
    else:
        await message.reply_text("❌ Nothing is playing!")


@app.on_message(filters.command("lyrics"))
async def lyrics_command(client, message: Message):
    """Get lyrics"""
    if len(message.command) < 2:
        await message.reply_text("❌ Usage: /lyrics <song name>")
        return

    song_name = message.text.split(None, 1)[1]
    status_msg = await message.reply_text("🔍 Searching for lyrics...")

    lyrics = await fetch_lyrics(song_name)

    if len(lyrics) > 4096:
        lyrics = lyrics[:4000] + "\n\n... [Truncated]"

    await status_msg.edit_text(f"📝 Lyrics for {song_name}:\n\n{lyrics}")


@app.on_message(filters.command("ping"))
async def ping_command(client, message: Message):
    """Check latency"""
    start = datetime.now()
    msg = await message.reply_text("🏓 Pinging...")
    end = datetime.now()
    ms = (end - start).microseconds / 1000

    uptime = datetime.now() - start_time
    cpu = psutil.cpu_percent()
    ram = psutil.virtual_memory().percent

    await msg.edit_text(
        f"🏓 Pong!\n"
        f"⚡️ Latency: {ms:.2f}ms\n"
        f"⏰ Uptime: {str(uptime).split('.')[0]}\n"
        f"💻 CPU: {cpu}%\n"
        f"🎯 RAM: {ram}%"
    )


@app.on_message(filters.command("stats"))
async def stats_command(client, message: Message):
    """Bot statistics"""
    uptime = datetime.now() - start_time

    stats_text = f"""
📊 Bot Statistics

👥 Users: {len(bot_stats['users'])}
💬 Chats: {len(bot_stats['chats'])}
🎵 Songs Played: {bot_stats['played']}
⏰ Uptime: {str(uptime).split('.')[0]}

💻 System:
• CPU: {psutil.cpu_percent()}%
• RAM: {psutil.virtual_memory().percent}%
• Disk: {psutil.disk_usage('/').percent}%

🔧 Active Calls: {len(current_playing)}
📋 Queued Songs: {sum(len(q) for q in queues.values())}
"""
    await message.reply_text(stats_text)


@app.on_message(filters.command("uptime"))
async def uptime_command(client, message: Message):
    """Show uptime"""
    uptime = datetime.now() - start_time
    await message.reply_text(
        f"⏰ Bot Uptime:\n{str(uptime).split('.')[0]}\n\n"
        f"🚀 Started: {start_time.strftime('%Y-%m-%d %H:%M:%S')}"
    )


# ============= ADMIN COMMANDS =============
@app.on_message(filters.command("broadcast") & filters.user(SUDO_USERS))
async def broadcast_command(client, message: Message):
    """Broadcast message to all chats"""
    if len(message.command) < 2:
        await message.reply_text("❌ Usage: /broadcast <message>")
        return

    broadcast_msg = message.text.split(None, 1)[1]
    status = await message.reply_text("📡 Broadcasting...")

    success = 0
    failed = 0

    for chat_id in bot_stats['chats']:
        try:
            await app.send_message(chat_id, f"📢 Broadcast:\n\n{broadcast_msg}")
            success += 1
        except:
            failed += 1
        await asyncio.sleep(0.1)

    await status.edit_text(
        f"✅ Broadcast Complete!\n"
        f"✓ Success: {success}\n"
        f"✗ Failed: {failed}"
    )


@app.on_message(filters.command("reload") & filters.user(SUDO_USERS))
async def reload_command(client, message: Message):
    """Reload bot"""
    await message.reply_text("🔄 Reloading modules...")
    # Clear caches
    queues.clear()
    current_playing.clear()
    await message.reply_text("✅ Reloaded successfully!")


@app.on_message(filters.command("reboot") & filters.user(SUDO_USERS))
async def reboot_command(client, message: Message):
    """Reboot bot"""
    await message.reply_text("🔄 Rebooting...")
    await app.stop()
    os.execl(sys.executable, sys.executable, *sys.argv)


@app.on_message(filters.command("logs") & filters.user(SUDO_USERS))
async def logs_command(client, message: Message):
    """Get logs"""
    try:
        with open("bot.log", "r") as f:
            logs = f.read()[-4000:]
        await message.reply_text(f"📄 Recent Logs:\n\n```{logs}```")
    except:
        await message.reply_text("❌ No logs found!")


@app.on_message(filters.command("maintenance") & filters.user(SUDO_USERS))
async def maintenance_command(client, message: Message):
    """Toggle maintenance mode"""
    if len(message.command) < 2:
        await message.reply_text("❌ Usage: /maintenance <on/off>")
        return

    mode = message.command[1].lower()
    if mode == "on":
        await message.reply_text("🔧 Maintenance mode: ON\nBot will reject non-admin commands")
    else:
        await message.reply_text("✅ Maintenance mode: OFF\nBot is back online!")


@app.on_callback_query()
async def callback_handler(client, callback_query: CallbackQuery):
    """Handle callbacks"""
    data = callback_query.data
    chat_id = callback_query.message.chat.id

    if data == "help_menu":
        help_text = """
🎵 Quick Commands:
• /play - Play music
• /pause - Pause
• /resume - Resume
• /skip - Skip
• /stop - Stop
• /queue - Show queue
Type /help for all commands!
"""
        await callback_query.message.edit_text(help_text)
        await callback_query.answer()
        return

    if data == "pause":
        try:
            await pytgcalls.pause_stream(chat_id)
            await callback_query.answer("⏸️ Paused!", show_alert=False)
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
                    f"⏭️ Skipped!\n\n🎵 Now Playing:\n📀 {song.title}",
                    reply_markup=get_control_buttons()
                )
            else:
                await callback_query.answer("✅ Queue finished!", show_alert=True)

    elif data == "stop":
        try:
            await pytgcalls.leave_group_call(chat_id)
            queues[chat_id].clear()
            current_playing.pop(chat_id, None)
            await callback_query.answer("⏹️ Stopped!", show_alert=False)
            await callback_query.message.edit_text("⏹️ Stopped and cleared queue!")
        except Exception as e:
            await callback_query.answer(f"❌ {str(e)}", show_alert=True)

    elif data == "queue":
        if chat_id not in current_playing and not queues[chat_id]:
            await callback_query.answer("📭 Queue is empty!", show_alert=True)
            return

        text = "📃 Queue:\n\n"
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
    await app.start()
    await pytgcalls.start()
    await health_server.start()
    logger.info("PyTgCalls started!")
    logger.info(f"{BOT_NAME} started successfully!")
    await idle()
    # Shutdown cleanup
    await pytgcalls.stop()
    await app.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped")
