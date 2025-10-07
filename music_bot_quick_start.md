# ⚡ Quick Start Guide - Rhythmix X Bot

Get your music bot running in **5 minutes**!

## 🚀 Fastest Deploy Methods

### Option 1: Render.com (Recommended - FREE)

1. **Fork Repository** → Click "Fork" on GitHub
2. **Go to [Render.com](https://render.com)** → Sign up with GitHub
3. **New Web Service** → Connect your forked repo
4. **Environment**: Select `Docker`
5. **Add these Environment Variables:**
   ```
   API_ID = 20550203
   API_HASH = 690778a70966c6f3f1fbacb96a49f360
   BOT_TOKEN = 8244422744:AAF0ZSEONT7YTpwKldhLGGpZO_tseXlnmYA
   BOT_NAME = Rhythmix X Bot
   ```
6. **Click Deploy** → Wait 5 minutes
7. **Done!** ✅ Your bot is live

### Option 2: Railway.app (FREE $5 Credit)

1. **Go to [Railway.app](https://railway.app)** → Sign in with GitHub
2. **New Project** → Deploy from GitHub repo
3. **Select forked repository**
4. **Add Variables** (same as above)
5. **Deploy** → Automatic!
6. **Done!** ✅

### Option 3: Local Testing (Quick)

```bash
# Clone repository
git clone <your-repo-url>
cd telegram-music-bot

# Make setup script executable
chmod +x setup.sh

# Run setup (installs everything)
./setup.sh

# Edit .env file with your credentials
nano .env

# Activate environment and run
source venv/bin/activate
python main.py
```

---

## 🎮 Using Your Bot

### Step 1: Add Bot to Group

1. Search for your bot: `@YourBotUsername`
2. Click "Add to Group"
3. Select your group

### Step 2: Make Bot Admin

1. Group Settings → Administrators
2. Add your bot
3. **Enable these permissions:**
   - ✅ Manage Voice Chats
   - ✅ Delete Messages
   - ✅ Invite Users via Link

### Step 3: Start Voice Chat

1. Open group chat
2. Click menu (⋮)
3. "Start Voice Chat"

### Step 4: Play Music!

```
/play Imagine Dragons Believer
/play https://youtu.be/dQw4w9WgXcQ
/play Spotify link
```

---

## 📱 Available Commands

### Music Playback
- `/play <song name or URL>` - Play music
- `/pause` - Pause playback
- `/resume` - Resume playback
- `/skip` - Skip to next song
- `/stop` - Stop and clear queue

### Information
- `/queue` - View playlist queue
- `/nowplaying` - Current song info
- `/lyrics <song name>` - Get lyrics
- `/ping` - Check bot status

### General
- `/start` - Bot introduction
- `/help` - Show help message

---

## 🎯 Quick Examples

### Play a Song
```
/play Shape of You Ed Sheeran
```

### Play from YouTube
```
/play https://youtu.be/kJQP7kiw5Fk
```

### Get Lyrics
```
/lyrics Bohemian Rhapsody
```

### Check Queue
```
/queue
```

---

## ⚙️ Configuration

### Your Credentials

Get these from:
- **API_ID & API_HASH**: [my.telegram.org/apps](https://my.telegram.org/apps)
- **BOT_TOKEN**: [@BotFather](https://t.me/BotFather) on Telegram

### Optional Settings

Edit `config.py` or add environment variables:

```python
# Enable/Disable platforms
ENABLE_SPOTIFY = True
ENABLE_SOUNDCLOUD = True

# Admin users (can control in any group)
SUDO_USERS = [123456789, 987654321]

# Max queue size
MAX_QUEUE_SIZE = 50
```

---

## 🔧 Troubleshooting

### Bot doesn't respond
```bash
# Check if bot is running
# Render: Check "Logs" tab
# Local: Check terminal output
```

### Can't join voice chat
1. ✅ Ensure bot is **admin** in group
2. ✅ Voice chat must be **started**
3. ✅ You must be **in the voice chat**

### Audio not playing
```bash
# Update yt-dlp
pip install -U yt-dlp

# Check FFmpeg
ffmpeg -version
```

### Bot keeps restarting
- Check your credentials are correct
- Monitor memory usage (upgrade if needed)
- Check logs for errors

---

## 📊 Platform Requirements

| Platform | RAM | Storage | Cost |
|----------|-----|---------|------|
| **Render** | 512MB | 1GB | FREE |
| **Railway** | 512MB | 1GB | $5/mo credit |
| **Heroku** | 512MB | 500MB | FREE* |
| **VPS** | 1GB+ | 10GB+ | From $5/mo |

*Free tier limited to 550 hours/month

---

## 🎨 Features

✅ **High-Quality Audio** - Crystal clear sound  
✅ **Multi-Platform** - YouTube, Spotify, SoundCloud  
✅ **Smart Queue** - Auto-play next tracks  
✅ **Lyrics Support** - Fetch any song lyrics  
✅ **Interactive UI** - Beautiful buttons and formatting  
✅ **Admin Controls** - Restricted commands in groups  
✅ **Auto-Reconnect** - Handles disconnections  
✅ **Private & Group** - Works everywhere  
✅ **Easy Deploy** - One-click deployment  
✅ **Production Ready** - Stable and optimized  

---

## 🆘 Need Help?

### Common Issues

**Q: Bot doesn't play in private chat**  
A: You need to be in a voice chat first (groups only for VC)

**Q: Songs fail to download**  
A: Try updating yt-dlp: `pip install -U yt-dlp`

**Q: Bot crashes frequently**  
A: Upgrade to a plan with more RAM (1GB recommended)

**Q: How to update the bot?**  
A: Push changes to GitHub, platforms auto-deploy

### Get Support

- 📧 **Issues**: GitHub Issues tab
- 💬 **Telegram**: @YourUsername
- 📚 **Docs**: README.md and DEPLOYMENT.md

---

## 🔐 Security Tips

1. **Never share** your BOT_TOKEN
2. **Don't commit** .env files to Git
3. **Use environment variables** on hosting platforms
4. **Regular updates** - Keep dependencies updated
5. **Monitor logs** - Check for suspicious activity

---

## 📈 Next Steps

### Customize Your Bot

Edit `main.py` to add:
- Custom commands
- Different music sources
- Enhanced UI
- Special features

### Scale Up

- Upgrade hosting plan for more users
- Add database for user preferences
- Implement playlists feature
- Add admin dashboard

### Contribute

- Fork and improve
- Submit pull requests
- Share with community
- Star the repository ⭐

---

## 🎉 You're All Set!

Your Telegram music bot is ready to rock! 🎸

**Start playing music now:**
```
/play your favorite song
```

Enjoy unlimited music streaming in your Telegram groups! 🎵

---

**Made with ❤️ for the Telegram community**

*Questions? Check DEPLOYMENT.md for detailed guides*