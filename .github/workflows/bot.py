import os
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GH_PAT = os.getenv("GH_PAT")
OWNER = "bridge-00"
REPO = "TORVIKING"
WORKFLOW = "main.yml"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚔️ *TORVIKING Telegram Bot is ready!*\n\n"
        "Send this command:\n"
        "`/upload <magnet-link-or-torrent-url>`\n\n"
        "You can add your VikingFile hash and folder like this:\n"
        "`/upload magnet:... yourhash foldername`"
    )

async def upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("❌ Please send a magnet link or .torrent URL after /upload")
        return

    torrent_link = args[0]
    viking_hash = args[1] if len(args) > 1 else ""
    viking_folder = args[2] if len(args) > 2 else ""

    chat_id = str(update.message.chat_id)

    url = f"https://api.github.com/repos/{OWNER}/{REPO}/actions/workflows/{WORKFLOW}/dispatches"
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

    r = requests.post(url, headers=headers, json=payload)
    if r.status_code == 204:
        await update.message.reply_text("🚀 TORVIKING started! I'll DM you the VikingFile links when finished.")
    else:
        await update.message.reply_text(f"❌ Error starting workflow: {r.status_code}\nCheck your GH_PAT secret.")

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("upload", upload))
    print("🤖 TorViking Telegram bot started!")
    app.run_polling()

if __name__ == "__main__":
    main()
