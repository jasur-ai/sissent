# 🤖 guid_erbot — Telegram Remote Control

Control your Kali Linux VM entirely from your phone via Telegram. **103 buttons** organized into sorted categories — all inside Telegram, no browser needed!

## 📦 Project Structure

```
guid_erbot/
├── bot.py                 # Main bot (3,454 lines, 103 buttons)
├── extra_commands.py      # 60+ extra command handlers (827 lines)
├── utils.py               # Shared utilities (151 lines)
├── web_panel.py           # Flask web UI (optional, 1,675 lines)
├── healthcheck.py         # Keep-alive server for Uptime Runner
│
├── requirements.txt       # Python dependencies
├── runtime.txt            # Python 3.11
├── render.yaml            # Render deployment config
├── .env.example           # Environment variables template
├── .gitignore             # Git ignore rules
├── startup.sh             # Render entrypoint script
└── install.sh             # Local VM setup script
```

## 🚀 Deploy to Render.com

### Step 1: Push to GitHub
```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USER/guid_erbot.git
git push -u origin main
```

### Step 2: Deploy on Render
1. Go to **[render.com](https://render.com)** → Dashboard → **New +** → **Blueprint**
2. Connect your GitHub repo
3. Render reads `render.yaml` and creates:
   - **Background Worker** → runs the Telegram bot
   - **Web Service** → runs healthcheck for Uptime Robot
4. Set `BOT_TOKEN` in Render's **Environment Variables** (get it from @BotFather)
5. Click **Apply** — done! 🎉

### Step 3: Keep Alive with Uptime Robot (FREE)
Render's free tier sleeps after 15 min of inactivity. Prevent this:

1. Go to **[uptimerobot.com](https://uptimerobot.com)** → Sign up (free)
2. Click **+ Add New Monitor**
   - Monitor Type: **HTTP(s)**
   - URL: `https://YOUR-APP-NAME.onrender.com/health`
   - Interval: **10 minutes**
3. Bot stays awake 24/7! 🔋

## 🔧 Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `BOT_TOKEN` | ✅ Yes | From @BotFather on Telegram |
| `ADMIN_IDS` | ❌ No | Default: `8004724563` |

## 📱 Usage
1. Open Telegram → search `@guid_erbot` → tap **Start**
2. Use the **103 buttons** sorted by category:
   - 🚀 Power Tools — Terminal, Firefox, Screenshot, Record, VPN
   - 💻 System — Shell, Services, Apps, CPU, Packages, Updates
   - 📊 Monitoring — Processes, Sysinfo, GPU, IP, Speed Test
   - 🖥️ Desktop — Lock, Unlock, GPG, Notify, Type, Key
   - 🔊 Sound & Media — Vol, Music, YouTube, Steam, Podcasts
   - 🖱️ Mouse — Click, Scroll, Position
   - 📁 Files — Home, Downloads, Docs, Upload, Backup, Empty Trash
   - 🌐 Remote — VNC, RustDesk, Share Folder, Open URL
   - 🛡️ Security — Firewall, SSH Keys, Port Scan, Keychain
   - 🛠️ Developer — Python, Docker, VS Code, Git, Build, Tests
   - 🎮 Fun — Dice, Coin, Fortune, 8-Ball, Matrix, Cat Facts
   - ⚙️ Display — Screen Res, Brightness, Night Mode, Theme, Camera
   - ⚡ Control — Shutdown, Reboot, Web Panel, About, Power Off

## ⚠️ Notes
- **Web Panel** (`web_panel.py`) is optional — uncomment it in `render.yaml` to deploy it as a web service
- Some commands (VNC, screen lock, volume) need X11/desktop environment — won't work on Render, only on a real VM
