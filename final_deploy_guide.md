# 🚀 Complete Deployment Guide - Rhythmix X Bot
### Created by @S_o_n_u_783

---

## 📋 Prerequisites

Before starting, make sure you have:
- ✅ Telegram account
- ✅ GitHub account (free)
- ✅ Your bot credentials (already configured in code)

**Your Bot Credentials:**
```
API_ID: 20550203
API_HASH: 690778a70966c6f3f1fbacb96a49f360
BOT_TOKEN: 8244422744:AAF0ZSEONT7YTpwKldhLGGpZO_tseXlnmYA
BOT_NAME: Rhythmix X Bot
```

---

## 🌟 EASIEST METHOD: Render.com (FREE - Recommended)

### **Step 1: Download All Bot Files**

You need to save these files to your computer:

1. **main.py** - Main bot code
2. **config.py** - Configuration
3. **health_server.py** - Health check server
4. **requirements.txt** - Dependencies
5. **Dockerfile** - Docker config
6. **render.yaml** - Render configuration
7. **.gitignore** - Git exclusions
8. **.env.example** - Environment template

Create a folder called `rhythmix-bot` and save all files there.

---

### **Step 2: Upload to GitHub**

#### **Option A: Using GitHub Website (Easiest)**

1. **Go to [github.com](https://github.com)**
2. **Sign in** (or create account if you don't have)
3. **Click "+" button** (top right) → **"New repository"**
4. **Repository settings:**
   - Name: `rhythmix-music-bot`
   - Description: `Telegram Music Bot by @S_o_n_u_783`
   - Set to: **Public**
   - **Don't check** "Initialize with README"
5. **Click "Create repository"**
6. **Upload files:**
   - Click **"uploading an existing file"** link
   - Drag all 8 files into the upload area
   - Write commit message: "Initial commit"
   - Click **"Commit changes"**

#### **Option B: Using Git Commands**

```bash
# Create folder
mkdir rhythmix-bot
cd rhythmix-bot

# Copy all your bot files here

# Initialize git
git init
git add .
git commit -m "Initial commit by @S_o_n_u_783"
git branch -M main

# Replace YOUR_GITHUB_USERNAME with your actual username
git remote add origin https://github.com/YOUR_GITHUB_USERNAME/rhythmix-music-bot.git
git push -u origin main
```

---

### **Step 3: Deploy to Render**

1. **Go to [render.com](https://render.com)**

2. **Click "Get Started"**

3. **Sign up with GitHub** (click the GitHub button)
   - Authorize Render to access your GitHub

4. **Create New Web Service:**
   - Click **"New +"** button (top right)
   - Select **"Web Service"**

5. **Connect Repository:**
   - You'll see your repositories list
   - Find **"rhythmix-music-bot"**
   - Click **"Connect"**

6. **Configure Service:**

   Fill in these details:
   ```
   Name: rhythmix-music-bot
   Region: Oregon (US West) - or choose closest to you
   Branch: main
   Root Directory: (leave blank)
   Environment: Docker
   Instance Type: Free
   ```

7. **Add Environment Variables:**

   Click **"Advanced"** → **"Add Environment Variable"**
   
   Add these **exactly** as shown:

   ```
   API_ID = 20550203
   API_HASH = 690778a70966c6f3f1fbacb96a49f360
   BOT_TOKEN = 8244422744:AAF0ZSEONT7YTpwKldhLGGpZO_tseXlnmYA
   BOT_NAME = Rhythmix X Bot
   PORT = 8000
   ENABLE_HEALTH_CHECK = True
   ```

8. **Create Web Service:**
   - Scroll to bottom
   - Click **"Create Web Service"**

9. **Wait for Deployment:**
   - This takes 5-10 minutes
   - Watch the logs in real-time
   - Look for: **"Bot started successfully!"**
   - Status will change to **"Live"** with green dot

10. **Copy your bot URL:**
    - It will be something like: `https://rhythmix-music-bot.onrender.com`
    - Save this for monitoring

---

### **Step 4: Setup Your Telegram Bot**

1. **Open Telegram** (mobile or desktop)

2. **Search for your bot:**
   - Search: `@RhythmixXBot` (or whatever name you set)
   - Click on the bot

3. **Send `/start` command:**
   - You should get a welcome message
   - If yes, bot is working! ✅

4. **Add bot to your group:**
   - Click **"⋮"** (three dots) on bot chat
   - Select **"Add to Group or Channel"**
   - Choose your group
   - Click **"Add"**

5. **Make bot administrator:**
   - Go to your group
   - Click group name at top
   - Click **"Edit"**
   - Click **"Administrators"**
   - Click **"Add Administrator"**
   - Select your bot
   - **Enable these permissions:**
     - ✅ **Manage Voice Chats** (MOST IMPORTANT)
     - ✅ Delete Messages
     - ✅ Invite Users via Link
     - ✅ Pin Messages (optional)
   - Click **"Done"**

---

### **Step 5: Start Using Your Bot!**

1. **Start Voice Chat in your group:**
   - Click **"⋮"** menu in group
   - Select **"Start Voice Chat"**
   - The voice chat panel will open

2. **Join the voice chat:**
   - Click **"Join"** button
   - Important: You must be in VC for bot to work!

3. **Play your first song:**
   ```
   /play Believer Imagine Dragons
   ```

4. **Test all commands:**
   ```
   /play Faded Alan Walker
   /pause
   /resume
   /queue
   /nowplaying
   /skip
   /lyrics Faded
   /stop
   ```

5. **Use buttons:**
   - Click the inline buttons under messages
   - ⏸ Pause
   - ▶️ Resume
   - ⏭ Skip
   - ⏹ Stop
   - 🔄 Queue

---

## 🎯 Alternative: Railway.app Deployment

If Render doesn't work, try Railway:

1. **Go to [railway.app](https://railway.app)**
2. **Sign in with GitHub**
3. **New Project** → **"Deploy from GitHub repo"**
4. **Select** your `rhythmix-music-bot` repository
5. **Add Variables** (click Variables tab):
   ```
   API_ID = 20550203
   API_HASH = 690778a70966c6f3f1fbacb96a49f360
   BOT_TOKEN = 8244422744:AAF0ZSEONT7YTpwKldhLGGpZO_tseXlnmYA
   BOT_NAME = Rhythmix X Bot
   PORT = 8000
   ```
6. **Click Deploy**
7. **Wait 5-10 minutes**

---

## 🖥️ Local Testing (Windows/Mac/Linux)

### **Windows:**

1. **Install Python:**
   - Download from [python.org](https://www.python.org/downloads/)
   - Install Python 3.11
   - **Check** "Add Python to PATH"

2. **Install FFmpeg:**
   - Download from [ffmpeg.org](https://ffmpeg.org/download.html)
   - Extract and add to PATH

3. **Setup bot:**
   ```cmd
   mkdir rhythmix-bot
   cd rhythmix-bot
   
   REM Copy all bot files here
   
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   
   copy .env.example .env
   notepad .env
   REM Add your credentials
   
   python main.py
   ```

### **Mac/Linux:**

1. **Install requirements:**
   ```bash
   # Mac
   brew install python@3.11 ffmpeg
   
   # Ubuntu/Debian
   sudo apt update
   sudo apt install python3 python3-pip ffmpeg
   ```

2. **Setup bot:**
   ```bash
   mkdir rhythmix-bot
   cd rhythmix-bot
   
   # Copy all bot files here
   
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   
   cp .env.example .env
   nano .env
   # Add your credentials
   
   python main.py
   ```

---

## ✅ Verification Checklist

After deployment, check:

- [ ] Bot responds to `/start` in private chat
- [ ] Bot responds to `/start` in group
- [ ] Bot is admin in group with "Manage Voice Chats" permission
- [ ] Voice chat is started in group
- [ ] You joined the voice chat
- [ ] Bot joins VC when you use `/play`
- [ ] Music plays clearly
- [ ] Pause/Resume buttons work
- [ ] Queue system works
- [ ] Skip command works
- [ ] Bot reconnects if VC drops

---

## 🔧 Common Issues & Solutions

### **1. Bot doesn't respond to commands**

**Check:**
```bash
# Verify bot token
curl https://api.telegram.org/bot8244422744:AAF0ZSEONT7YTpwKldhLGGpZO_tseXlnmYA/getMe

# Should return bot info
```

**Solution:**
- Check Render logs for errors
- Make sure environment variables are correct
- Redeploy if needed

---

### **2. "No active group call" error**

**Solutions:**
1. Start voice chat first
2. Join the voice chat yourself
3. Make sure bot is admin
4. Check "Manage Voice Chats" permission is enabled

---

### **3. Bot joins but no audio**

**Solutions:**
1. Check Render logs for FFmpeg errors
2. Try a different song
3. Use YouTube URL directly:
   ```
   /play https://youtu.be/dQw4w9WgXcQ
   ```

---

### **4. "Permission denied" errors**

**Solution:**
1. Remove bot from group
2. Add it back
3. Make admin immediately with correct permissions
4. Try `/play` again

---

### **5. Bot keeps restarting**

**Check Render logs:**
- Look for "Out of memory" errors
- Check for missing dependencies
- Verify all environment variables

**Solution:**
- Free tier has 512MB RAM
- Should be enough for 1-2 groups
- Upgrade if using in many groups

---

## 📊 Monitoring Your Bot

### **On Render:**

1. **Dashboard:** [dashboard.render.com](https://dashboard.render.com)
2. **Click your service:** `rhythmix-music-bot`
3. **Tabs:**
   - **Logs:** Real-time bot logs
   - **Events:** Deployment history
   - **Metrics:** CPU, Memory usage
   - **Settings:** Change configuration

### **Check Bot Status:**

Send in Telegram:
```
/ping
```
Should show latency and uptime.

### **Health Check:**

Visit in browser:
```
https://your-app.onrender.com/health
```
Should show:
```json
{
  "status": "healthy",
  "uptime": "2:30:45",
  "timestamp": "2025-10-07T..."
}
```

---

## 🎵 Using the Bot - Complete Guide

### **Basic Playback:**

```
/play <song name>
/play <YouTube URL>
/play <Spotify link>
```

Examples:
```
/play Believer Imagine Dragons
/play Shape of You
/play https://youtu.be/kJQP7kiw5Fk
/play https://open.spotify.com/track/...
```

### **Queue Management:**

```
/queue - View current queue
/skip - Skip current song
/stop - Stop and clear queue
```

### **Playback Controls:**

```
/pause - Pause playback
/resume - Resume playback
/nowplaying - Show current song
```

### **Additional Features:**

```
/lyrics <song name> - Get song lyrics
/ping - Check bot status
```

### **Using Buttons:**

After `/play`, use inline buttons:
- ⏸ **Pause** - Pause current song
- ▶️ **Resume** - Resume playback
- ⏭ **Skip** - Skip to next
- ⏹ **Stop** - Stop everything
- 🔄 **Queue** - Quick queue view

---

## 🎨 Customization

### **Change Bot Name:**

In Render environment variables:
```
BOT_NAME = Your Custom Name
```

### **Add Adm