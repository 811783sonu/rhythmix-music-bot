import asyncio
import os
import logging
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pytgcalls import PyTgCalls, StreamType
from pytgcalls.types.input_stream import AudioPiped
from pytgcalls.types.input_stream.quality import HighQualityAudio
from pytgcalls.exceptions import NoActiveGroupCall, AlreadyJoinedError
import yt_dlp
import aiohttp
import re
from collections import defaultdict
from datetime import datetime
from config import API_ID, API_HASH, BOT_TOKEN, BOT_NAME
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

# YT-DLP options with better YouTube handling
ydl_opts = {
    'format': 'bestaudio/best',
    'outtmpl': 'downloads/%(id)s.%(ext)s',
    'quiet': True,
    'no_warnings': True,
    'extract_flat': False,
    'nocheckcertificate': True,
    'geo_bypass': True,
    'extractor_args': {'youtube': {'player_client': ['android', 'web']}},
    'cookiefile': None,
    'http_headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-us,en;q=0.5',
    },
}

class Song:
    def __init__(self, title, duration, url, thumbnail, requester, platform="YouTube"):
        self.title = title
        self.duration = duration
        self.url = url
        self.thumbnail = thumbnail
        self.requester = requester
        self.platform = platform

async def download_song(query):
    """Download and extract audio info from YouTube/Spotify/SoundCloud"""
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Check if it's a URL or search query
            if not query.startswith('http'):
                query = f"ytsearch:{query}"
            
            info = ydl.extract_info(query, download=False)
            
            # Handle playlist or search results
            if 'entries' in info:
                info = info['entries'][0]
            
            # Download the audio
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
        logger.error(f"Download error: {e}")
        return None

async def fetch_lyrics(song_name):
    """Fetch lyrics from Genius API (simplified)"""
    try:
        async with aiohttp.ClientSession() as session:
            # Using a free lyrics API
            url = f"https://api.lyrics.ovh/v1/artist/{song_name}"
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get('lyrics', 'Lyrics not found')
                return 'Lyrics not found'
    except:
        return 'Unable to fetch lyrics at the moment'

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
            
            # Join and play
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
            # No more songs, leave VC
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
    """Handle stream end - play next song"""
    chat_id = update.chat_id
    await play_next(chat_id)

@app.on_message(filters.command("start"))
async def start_command(client, message: Message):
    """Start command handler"""
    await message.reply_text(
        f"🎵 **Welcome to {BOT_NAME}!**\n\n"
        "I can play music in your voice chats!\n\n"
        "**Commands:**\n"
        "• `/play <song name>` - Play a song\n"
        "• `/pause` - Pause playback\n"
        "• `/resume` - Resume playback\n"
        "• `/skip` - Skip current song\n"
        "• `/stop` - Stop and clear queue\n"
        "• `/queue` - Show current queue\n"
        "• `/nowplaying` - Current song info\n"
        "• `/lyrics <song>` - Get lyrics\n\n"
        "Add me to your group and start the voice chat!",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 Support", url="https://t.me/example")]
        ])
    )

@app.on_message(filters.command("play"))
async def play_command(client, message: Message):
    """Play command handler"""
    chat_id = message.chat.id
    
    # Check if user is in VC (for groups)
    if message.chat.type != "private":
        try:
            member = await app.get_chat_member(chat_id, message.from_user.id)
        except:
            await message.reply_text("❌ Join voice chat first!")
            return
    
    if len(message.command) < 2:
        await message.reply_text("❌ Usage: `/play <song name or URL>`")
        return
    
    query = message.text.split(None, 1)[1]
    status_msg = await message.reply_text("🔍 **Searching...**")
    
    # Download song info
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
    
    # Add to queue
    queues[chat_id].append(song)
    
    # If nothing is playing, start playing
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
    chat_id = message.chat.id
    
    try:
        await pytgcalls.pause_stream(chat_id)
        await message.reply_text("⏸ **Paused!**")
    except Exception as e:
        await message.reply_text(f"❌ Error: {str(e)}")

@app.on_message(filters.command("resume"))
async def resume_command(client, message: Message):
    """Resume playback"""
    chat_id = message.chat.id
    
    try:
        await pytgcalls.resume_stream(chat_id)
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
    """Stop playback and clear queue"""
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
    """Show current queue"""
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
    """Show current playing song"""
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
    """Get song lyrics"""
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
    """Check bot latency"""
    start = datetime.now()
    msg = await message.reply_text("🏓 **Pinging...**")
    end = datetime.now()
    ms = (end - start).microseconds / 1000
    
    uptime = datetime.now() - start_time
    await msg.edit_text(
        f"🏓 **Pong!**\n"
        f"⚡️ **Latency:** {ms:.2f}ms\n"
        f"⏰ **Uptime:** {str(uptime).split('.')[0]}"
    )

@app.on_callback_query()
async def callback_handler(client, callback_query: CallbackQuery):
    """Handle button callbacks"""
    data = callback_query.data
    chat_id = callback_query.message.chat.id
    
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
                    f"⏭ **Skipped!**\n\n"
                    f"🎵 **Now Playing:**\n"
                    f"📀 {song.title}",
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
        
        text = "📃 **Current Queue:**\n\n"
        
        if chat_id in current_playing:
            song = current_playing[chat_id]
            text += f"▶️ {song.title}\n\n"
        
        if queues[chat_id]:
            text += "**Up Next:**\n"
            for i, song in enumerate(queues[chat_id][:5], 1):
                text += f"{i}. {song.title}\n"
        
        await callback_query.answer(text, show_alert=True)

async def main():
    """Main function"""
    # Create downloads directory
    os.makedirs("downloads", exist_ok=True)
    
    # Start health check server
    await health_server.start()
    
    # Start PyTgCalls (this also starts the Pyrogram client)
    await pytgcalls.start()
    logger.info("PyTgCalls started!")
    logger.info(f"{BOT_NAME} started successfully!")
    
    # Keep running
    await asyncio.Event().wait()

if __name__ == "__main__":
    app.run(main())
