# Deployment Guide — JumysTap Bot

## Local development

```bash
cd jumystap_bot
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env              # then edit .env with your values
# Load env vars from .env at runtime:
export $(grep -v '^#' .env | xargs)

python bot.py
```

---

## Deploy to Render (free tier)

### 1. Push to GitHub
Create a private GitHub repo and push the `jumystap_bot/` folder as the repo root.

### 2. Create a Web Service on Render
- Dashboard → **New → Web Service**
- Connect your GitHub repo
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `python bot.py`
- **Environment:** Python 3
- **Instance Type:** Free

### 3. Set environment variables
In Render → your service → **Environment** tab, add:

| Key        | Value                       |
|------------|-----------------------------|
| `BOT_TOKEN` | Your BotFather token       |
| `ADMIN_ID`  | Your Telegram numeric user ID |

Render automatically injects `PORT`; the bot's aiohttp server reads it.

### 4. Keep-alive ping (prevents 15-min spin-down)
Free Render instances sleep after 15 minutes of no HTTP traffic.

Set up a free uptime monitor (e.g. [cron-job.org](https://cron-job.org) or
[UptimeRobot](https://uptimerobot.com)) to `GET https://<your-render-url>/health`
every **10 minutes**.

### 5. Persistent settings
`settings.json` is written to the container's local disk.  
**Warning:** Render free-tier ephemeral disk resets on every deploy or restart.  
To keep settings across restarts either:
- Use Render's **Disk** add-on (paid), or
- Edit values via `/settings` in the bot after each redeploy (takes ~30 seconds).

---

## How to get your ADMIN_ID
Send any message to [@userinfobot](https://t.me/userinfobot) on Telegram — it replies with your numeric user ID.

## Bot must be channel admin
For publishing to work, add the bot as an **Administrator** of `@jumystap1`
with the **Post Messages** permission enabled.
