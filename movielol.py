import os
import json
import logging
import urllib.parse
from flask import Flask, request, Response
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO)

# কনফিগারেশন
BOT_TOKEN = "8840283228:AAFy1dZxOfa9tFTksodSAVK38UkwtAlauU8"
WEBSITE_URL = "https://movielol.net"
DATA_FILE = "movies_data.json"
PORT = int(os.environ.get("PORT", 10000))

# Render-এর দেওয়া অ্যাপ URL (Render ড্যাশবোর্ড থেকে পাওয়া URL)
RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL", "https://movielol.onrender.com")

flask_app = Flask(__name__)

# ডাটাবেজ হ্যান্ডলিং
def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

movies_db = load_data()

# বট কমান্ড হ্যান্ডলার
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🎬 *MovieLoL.net Link Poster Bot* 🍿\n\n"
        "মুভির নাম এবং লিংক যেকোনো ফরম্যাটে পাঠান:\n\n"
        "🔹 *পদ্ধতি ১:* `Jawan - https://downloadlink.com/file`\n"
        "🔹 *পদ্ধতি ২:* `Inception` (সাইটে সরাসরি সার্চ হবে)\n\n"
        "সব সংরক্ষিত পোস্ট দেখতে `/all` লিখুন।"
    )
    if update.message:
        await update.message.reply_text(msg, parse_mode="Markdown")

async def process_movie_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    raw_text = update.message.text.strip()
    
    if "http://" in raw_text or "https://" in raw_text:
        parts = raw_text.split("http", 1)
        movie_name = parts[0].replace("-", "").strip()
        download_url = "http" + parts[1].strip()
        if not movie_name:
            movie_name = "Watch Movie"
    else:
        movie_name = raw_text
        encoded_query = urllib.parse.quote_plus(movie_name)
        download_url = f"{WEBSITE_URL}/?s={encoded_query}"

    entry = {"title": movie_name, "link": download_url}
    movies_db.append(entry)
    save_data(movies_db)

    buttons = [
        [InlineKeyboardButton("▶️ Watch / Download", url=download_url)],
        [InlineKeyboardButton("🌐 Visit MovieLoL.net", url=WEBSITE_URL)]
    ]
    reply_markup = InlineKeyboardMarkup(buttons)

    post_text = (
        f"🎬 *{movie_name}*\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"🔗 *Direct Link:* {download_url}\n"
        f"🌐 *Main Site:* [{WEBSITE_URL}]({WEBSITE_URL})\n\n"
        "⚡ _Enjoy high quality streaming & downloads on MovieLoL!_"
    )

    await update.message.reply_text(
        post_text, 
        parse_mode="Markdown", 
        reply_markup=reply_markup,
        disable_web_page_preview=False
    )

async def show_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    if not movies_db:
        await update.message.reply_text("এখনও কোনো মুভি লিংক যুক্ত করা হয়নি।")
        return

    text = "📁 *MovieLoL.net সংরক্ষিত মুভি তালিকা (সর্বশেষ ২০টি):*\n\n"
    for idx, item in enumerate(movies_db[-20:], 1):
        text += f"{idx}. [{item['title']}]({item['link']})\n"

    await update.message.reply_text(text, parse_mode="Markdown", disable_web_page_preview=True)

# হেলথ চেক রুট (Render পোর্ট ওপেন রাখার জন্য)
@flask_app.route('/')
def home():
    return "MovieLoL Bot is Running Live!"

if __name__ == '__main__':
    # Telegram Application সেটআপ
    bot_app = ApplicationBuilder().token(BOT_TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CommandHandler("all", show_all))
    bot_app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), process_movie_post))

    # Render-এর জন্য Webhook চালু করা
    webhook_url = f"{RENDER_EXTERNAL_URL}/{BOT_TOKEN}"
    
    bot_app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=BOT_TOKEN,
        webhook_url=webhook_url
    )
