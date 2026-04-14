import os
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GH_PAT = os.getenv("GH_PAT")
OWNER = "bridge-00"
REPO = "TORVIKING"
WORKFLOW_FILE = "main.yml"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚔️ *TORVIKING Telegram Bot is ready!*\n\n"
        "📥 *Download & Upload torrents to VikingFile*\n\n"
        "**Commands:**\n"
        "`/upload <magnet-link-or-torrent-url>`\n"
        "`/upload <link> <userhash> <folder>`\n"
        "`/status` — Check last workflow run\n"
        "`/help` — Show this message",
        parse_mode="Markdown"
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)


async def upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text(
            "❌ Please send a magnet link or .torrent URL after /upload\n\n"
            "Example:\n"
            "`/upload magnet:?xt=urn:btih:...`",
            parse_mode="Markdown"
        )
        return

    torrent_link = args[0]
    viking_hash = args[1] if len(args) > 1 else ""
    viking_folder = args[2] if len(args) > 2 else ""
    chat_id = str(update.message.chat_id)

    # Trigger GitHub Actions workflow
    url = f"https://api.github.com/repos/{OWNER}/{REPO}/actions/workflows/{WORKFLOW_FILE}/dispatches"
    headers = {
        "Authorization": f"token {GH_PAT}",
        "Accept": "application/vnd.github+json"
    }
    payload = {
        "ref": "main",
        "inputs": {
            "torrent_link": torrent_link,
            "viking_user_hash": viking_hash,
            "viking_folder": viking_folder,
            "telegram_chat_id": chat_id
        }
    }

    try:
        r = requests.post(url, headers=headers, json=payload, timeout=30)

        if r.status_code == 204:
            await update.message.reply_text(
                "🚀 *TORVIKING started!*\n\n"
                "⏳ Downloading & uploading in progress...\n"
                "📨 I'll send you the VikingFile links when finished.\n\n"
                "Use `/status` to check progress.",
                parse_mode="Markdown"
            )
        elif r.status_code == 404:
            await update.message.reply_text(
                "❌ Workflow not found!\n\n"
                "Make sure `main.yml` exists in `.github/workflows/` in the TORVIKING repo."
            )
        elif r.status_code == 401 or r.status_code == 403:
            await update.message.reply_text(
                "❌ Authentication failed!\n\n"
                "Check your `GH_PAT` secret — it may have expired."
            )
        else:
            await update.message.reply_text(
                f"❌ Error triggering workflow\n"
                f"Status: {r.status_code}\n"
                f"Response: {r.text[:200]}"
            )
    except requests.exceptions.Timeout:
        await update.message.reply_text("❌ GitHub API request timed out. Try again.")
    except requests.exceptions.ConnectionError:
        await update.message.reply_text("❌ Could not connect to GitHub API. Check your internet.")
    except Exception as e:
        await update.message.reply_text(f"❌ Unexpected error: {str(e)[:200]}")


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check the status of the last workflow run."""
    url = f"https://api.github.com/repos/{OWNER}/{REPO}/actions/runs?per_page=1"
    headers = {
        "Authorization": f"token {GH_PAT}",
        "Accept": "application/vnd.github+json"
    }

    try:
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code != 200:
            await update.message.reply_text(f"❌ Could not fetch status (HTTP {r.status_code})")
            return

        data = r.json()
        runs = data.get("workflow_runs", [])

        if not runs:
            await update.message.reply_text("ℹ️ No workflow runs found yet.")
            return

        run = runs[0]
        status_icon = {
            "completed": "✅",
            "in_progress": "⏳",
            "queued": "🕐",
            "failure": "❌",
            "cancelled": "🚫"
        }

        run_status = run.get("status", "unknown")
        conclusion = run.get("conclusion", "pending")
        icon = status_icon.get(conclusion, status_icon.get(run_status, "❓"))

        msg = (
            f"📊 *Last Workflow Run*\n\n"
            f"{icon} Status: `{run_status}`\n"
            f"Result: `{conclusion or 'in progress'}`\n"
            f"Started: `{run.get('created_at', 'N/A')}`\n"
            f"🔗 [View Logs]({run.get('html_url', '')})"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")

    except Exception as e:
        await update.message.reply_text(f"❌ Error checking status: {str(e)[:200]}")


def main():
    if not TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN environment variable is not set!")
        return
    if not GH_PAT:
        print("❌ GH_PAT environment variable is not set!")
        return

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("upload", upload))
    app.add_handler(CommandHandler("status", status))
    print("🤖 TorViking Telegram bot started!")
    app.run_polling()


if __name__ == "__main__":
    main()
