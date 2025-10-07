# 🔧 Troubleshooting Guide

Complete guide to solve common issues with Rhythmix X Bot.

---

## 🚨 Bot Won't Start

### Issue: Bot crashes immediately on startup

**Symptoms:**
- Process exits within seconds
- Error: "Could not initialize bot"
- No response from bot

**Solutions:**

1. **Check credentials**
   ```bash
   # Verify your .env file
   cat .env
   
   # Ensure no extra spaces
   API_ID=20550203  ✅ Correct
   API_ID = 20550203  ❌ Wrong (spaces around =)
   ```

2. **Verify Bot Token**
   ```bash
   # Test token validity
   curl https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getMe
   ```

3. **Check Python version**
   ```bash
   python3 --version
   # Should be 3.9 or higher
   ```

4. **Reinstall dependencies**
   ```bash
   pip install --force-reinstall -r requirements.txt
   ```

---

## 🎵 Music Playback Issues

### Issue: Songs won't play in voice chat

**Symptoms:**
- Bot joins VC but no audio
- "Failed to play" error
- Audio cuts out immediately

**Solutions:**

1. **Check FFmpeg installation**
   ```bash
   ffmpeg -version
   
   # If not installed:
   # Ubuntu/Debian
   sudo apt install ffmpeg
   
   # macOS
   brew install ffmpeg
   ```

2. **Update yt-dlp**
   ```bash
   pip install -U yt-dlp
   ```

3. **Test download manually**
   ```bash
   yt-dlp -f bestaudio "https://youtu.be/dQw4w9WgXcQ"
   ```

4. **Check PyTgCalls version**
   ```bash
   pip show py-tgcalls
   # Should be 0.9.7 or compatible
   ```

---

### Issue: Bot can't join voice chat

**Symptoms:**
- "No active group call" error
- Bot doesn't appear in VC
- Permission denied errors

**Solutions:**

1. **Make bot admin**
   - Group Settings → Administrators
   - Add bot with these permissions:
     - ✅ Manage Voice Chats
     - ✅ Delete Messages
     - ✅ Invite Users

2. **Start voice chat first**
   - Voice chat must be active before /play
   - Check if VC is visible in group

3. **Rejoin the bot**
   ```bash
   /stop  # Leave VC
   /play test  # Rejoin
   ```

4. **Check bot logs**
   ```bash
   # Look for PyTgCalls errors
   grep "pytgcalls" logs.txt
   ```

---

### Issue: Audio quality is poor

**Solutions:**

1. **Check yt-dlp format selection**
   ```python
   # In main.py, verify ydl_opts
   'format': 'bestaudio/best',  # Should select best quality
   ```

2. **Increase bitrate**
   ```python
   # Use HighQualityAudio in PyTgCalls
   from pytgcalls.types.input_stream.quality import HighQualityAudio
   ```

3. **Check internet speed**
   ```bash
   speedtest-cli
   # Need at least 1 Mbps upload
   ```

---

## 📥 Download Errors

### Issue: Songs fail to download

**Symptoms:**
- "Could not find the song" error
- Download timeout
- Invalid URL errors

**Solutions:**

1. **Update yt-dlp**
   ```bash
   pip install -U yt-dlp
   # YouTube changes APIs frequently
   ```

2. **Check URL format**
   ```
   ✅ https://youtu.be/dQw4w9WgXcQ
   ✅ https://www.youtube.com/watch?v=dQw4w9WgXcQ
   ❌ youtube.com/watch?v=dQw4w9WgXcQ  (missing https://)
   ```

3. **Test different sources**
   ```
   /play song name  # Search instead of URL
   ```

4. **Check disk space**
   ```bash
   df -h
   # Need at least 1GB free in downloads/
   ```

5. **Clear downloads folder**
   ```bash
   rm -rf downloads/*
   mkdir downloads
   ```

---

### Issue: Spotify links don't work

**Solution:**

Currently, Spotify requires additional setup:
```python
# Need Spotify API credentials
# Get from: https://developer.spotify.com/dashboard

# Add to config.py:
SPOTIFY_CLIENT_ID = "your_client_id"
SPOTIFY_CLIENT_SECRET = "your_secret"
```

**Workaround:**
- Search by song name instead
- Bot will find on YouTube

---

## 🔄 Queue & Playback Control

### Issue: Queue doesn't advance automatically

**Symptoms:**
- Song ends but next doesn't play
- Bot leaves VC after one song
- Queue shows items but doesn't play

**Solutions:**

1. **Check stream_end handler**
   ```python
   # Verify in main.py
   @pytgcalls.on_stream_end()
   async def stream_end_handler(client, update):
       await play_next(update.chat_id)
   ```

2. **Restart bot**
   ```bash
   # Sometimes event handlers need reset
   sudo systemctl restart musicbot  # VPS
   # Or redeploy on Render/Railway
   ```

3. **Check logs for errors**
   ```bash
   tail -f logs/bot.log
   # Look for "stream_end" errors
   ```

---

### Issue: Skip command doesn't work

**Solutions:**

1. **Ensure song is playing**
   ```
   /nowplaying  # Check current status
   ```

2. **Check if queue has items**
   ```
   /queue  # Must have songs queued
   ```

3. **Use stop then play**
   ```
   /stop
   /play next song
   ```

---

## 💾 Memory & Performance

### Issue: Bot crashes with "Out of Memory"

**Symptoms:**
- Sudden disconnects
- Platform shows high memory usage
- "Killed" in logs

**Solutions:**

1. **Clear downloads regularly**
   ```bash
   # Add to crontab
   0 */6 * * * rm -rf /app/downloads/*
   ```

2. **Limit queue size**
   ```python
   # In config.py
   MAX_QUEUE_SIZE = 20  # Reduce from 50
   ```

3. **Upgrade hosting plan**
   - Render: Upgrade to Starter ($7/mo, 512MB → 2GB)
   - Railway: Add more resources
   - VPS: Upgrade RAM

4. **Monitor memory usage**
   ```bash
   # Add to health_server.py
   import psutil
   memory = psutil.virtual_memory()
   ```

---

### Issue: Bot is slow or laggy

**Solutions:**

1. **Check CPU usage**
   ```bash
   top  # or htop
   # Look for python process
   ```

2. **Reduce concurrent operations**
   ```python
   # Limit simultaneous downloads
   MAX_CONCURRENT_DOWNLOADS = 1
   ```

3. **Use faster audio source**
   ```python
   # Prefer direct URLs over search
   /play https://youtu.be/... 
   # Faster than
   /play song name
   ```

4. **Optimize yt-dlp**
   ```python
   ydl_opts = {
       'format': 'bestaudio',
       'concurrent_fragment_downloads': 1,
       'no_playlist': True,
   }
   ```

---

## 🌐 Network & Connection

### Issue: Bot keeps disconnecting

**Symptoms:**
- Frequent reconnects
- "Connection lost" in logs
- Intermittent responses

**Solutions:**

1. **Check internet stability**
   ```bash
   ping -c 100 telegram.org
   # Packet loss should be < 1%
   ```

2. **Enable auto-reconnect** (already in code)
   ```python
   # Verify in main.py
   restart: unless-stopped  # Docker
   Restart=always  # Systemd
   ```

3. **Use stable hosting**
   - Avoid free VPS with poor uptime
   - Render/Railway have better stability

4. **Increase timeouts**
   ```python
   # In config.py
   DOWNLOAD_TIMEOUT = 600  # Increase from 300
   ```

---

### Issue: "Rate limited" errors

**Symptoms:**
- "Too many requests" error
- Bot stops responding temporarily
- 429 errors in logs

**Solutions:**

1. **Implement request throttling**
   ```python
   import asyncio
   
   # Add delays between operations
   await asyncio.sleep(1)
   ```

2. **Reduce concurrent users**
   - Limit bot to fewer groups
   - Implement usage quotas

3. **Use user bot (advanced)**
   ```python
   # Add SESSION_STRING to .env
   # Generate with: python generate_session.py
   ```

---

## 🔐 Permission & Access

### Issue: "Forbidden: bot was blocked by the user"

**Solution:**
- User blocked the bot
- They need to unblock in Telegram settings
- /start again after unblocking

---

### Issue: "Not enough rights to manage voice chats"

**Solutions:**

1. **Verify bot is admin**
   - Must have "Manage Voice Chats" permission

2. **Re-add bot as admin**
   ```
   1. Remove bot from group
   2. Add bot back
   3. Make admin immediately
   ```

3. **Check group settings**
   - Some groups restrict VC to certain users
   - Admins can change in group settings

---

## 📱 Platform-Specific Issues

### Render

**Issue: "Application failed to respond"**

**Solutions:**
1. Check health endpoint working:
   ```bash
   curl https://your-app.onrender.com/health
   ```

2. Verify PORT environment variable:
   ```
   PORT=8000
   ```

3. Check build logs for errors

---

### Railway

**Issue: "Deployment failed"**

**Solutions:**
1. Check Dockerfile syntax
2. Verify all files present
3. Check deployment logs
4. Ensure PORT is set correctly

---

### Heroku

**Issue: "Boot timeout"**

**Solutions:**
1. Add Procfile correctly:
   ```
   worker: python main.py
   ```

2. Scale worker:
   ```bash
   heroku ps:scale worker=1
   ```

3. Check buildpacks order:
   ```bash
   heroku buildpacks
   # Should show ffmpeg first, then python
   ```

---

### VPS

**Issue: "Systemd service fails"**

**Solutions:**
1. Check service status:
   ```bash
   sudo systemctl status musicbot
   journalctl -u musicbot -n 50
   ```

2. Verify paths in service file
3. Check file permissions:
   ```bash
   chmod +x main.py
   ```

4. Test manually first:
   ```bash
   cd /path/to/bot
   source venv/bin/activate
   python main.py
   ```

---

## 🧪 Debugging Tips

### Enable debug logging

```python
# In config.py
LOG_LEVEL = "DEBUG"

# Or in code
logging.basicConfig(level=logging.DEBUG)
```

### Test individual components

```python
# Test yt-dlp
python -c "import yt_dlp; print('OK')"

# Test pyrogram
python -c "from pyrogram import Client; print('OK')"

# Test pytgcalls
python -c "from pytgcalls import PyTgCalls; print('OK')"
```

### Check versions

```bash
pip list | grep -E "pyrogram|pytgcalls|yt-dlp"
```

### Monitor in real-time

```bash
# Render/Railway: Dashboard logs
# VPS:
journalctl -u musicbot -f

# Docker:
docker logs -f rhythmix-bot
```

---

## 📞 Still Having Issues?

1. **Check bot logs** - Most issues show in logs
2. **Search GitHub Issues** - Someone may have solved it
3. **Create new issue** - Provide:
   - Error message
   - Bot logs (last 50 lines)
   - Platform (Render/Railway/VPS)
   - Python version
   - Steps to reproduce

4. **Join support group** - Get help from community

---

## ✅ Prevention Tips

1. **Regular updates**
   ```bash
   pip install -U -r requirements.txt
   ```

2. **Monitor resources**
   - Check memory/CPU weekly
   - Clear downloads folder

3. **Keep credentials secure**
   - Never commit .env
   - Rotate tokens periodically

4. **Test before deploying**
   - Run locally first
   - Test all commands

5. **Backup configuration**
   - Save .env securely
   - Document custom changes

---

**Happy debugging! 🔧**