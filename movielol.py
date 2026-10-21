import os
import json
import logging
import urllib.parse
import requests
from bs4 import BeautifulSoup
from flask import Flask, request, Response
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

logging.basicConfig(level=logging.INFO)

# টোকেন ও কনফিগারেশন
BOT_TOKEN = "8840283228:AAfy1dZXOfa9tFTksodSAVK38UWktwAlAU8"
WEBSITE_URL = "https://movielol.net"
DATA_FILE = "movies_data.json"
PORT = int(os.environ.get("PORT", 10000))
RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL")

flask_app = Flask(__name__)

# লোকাল ডাটাবেস লোড ও সেভ
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except Exception:
                return {}
    return {}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

movies_db = load_data()

# ওয়েবসাইট স্ক্র্যাপ করে মুভির ইমেজ, লিংক ও টাইটেল বের করা
def scrape_movie_from_site(query):
    try:
        search_url = f"{WEBSITE_URL}/?s={urllib.parse.quote(query)}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        resp = requests.get(search_url, headers=headers, timeout=10)
        
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            
            # ওয়েবসাইটের কার্ড/পোস্ট কনটেইনার
            movie_card = soup.find("article") or soup.find("div", class_="post") or soup.find("div", class_="card")
            
            if movie_card:
                # পোস্ট লিংক
                link_tag = movie_card.find("a", href=True)
                post_url = link_tag["href"] if link_tag else None
                
                # ইমেজ লিংক
                img_tag = movie_card.find("img")
                img_url = None
                if img_tag:
                    img_url = img_tag.get("src") or img_tag.get("data-src")
                
                # টাইটেল
                title = movie_card.get_text().strip().split("\n")[0]
                if not title and link_tag:
                    title = link_tag.get("title", query)
                
                if post_url:
                    return {
                        "title": title or query,
                        "url": post_url,
                        "image": img_url
                    }
    except Exception as e:
        logging.error(f"Scraping error: {e}")
    return None

# /start কমান্ড
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🎬 *MovieLol.net Bot এ স্বাগতম!*\n\n"
        "যে কোনো মুভির নাম লিখে পাঠালে ওয়েবসাইট থেকে সার্চ করে সরাসরি ডাউনলোড লিংক দেওয়া হবে।\n\n"
        "মুভি লিংক দেখতে নিচের যে কোনো মুভির নাম লিখে মেসেজ দিন।"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

# টেক্সট মেসেজ ও সার্চ হ্যান্ডলার
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    
    # অ্যাডমিন যদি ফরম্যাটে পোস্ট করতে চায়: Movie Name - DownloadLink
    if " - " in text:
        parts = text.split(" - ", 1)
        name = parts[0].strip()
        link = parts[1].strip()
        movies_db[name.lower()] = {"title": name, "url": link, "image": None}
        save_data(movies_db)
        await update.message.reply_text(f"✅ '{name}' সফলভাবে সেভ করা হয়েছে!")
        return

    # সাধারণ সার্চ
    await update.message.reply_text("🔍 ওয়েবসাইট থেকে খোঁজা হচ্ছে, একটু অপেক্ষা করুন...")
    
    movie_info = None
    query_key = text.lower()
    
    # প্রথমে লোকাল ডাটাতে চেক
    if query_key in movies_db:
        movie_info = movies_db[query_key]
    else:
        # সরাসরি ওয়েবসাইটে স্ক্র্যাপ করে সার্চ
        movie_info = scrape_movie_from_site(text)
        if not movie_info:
            # ফলব্যাক লিংক তৈরি
            fallback_url = f"{WEBSITE_URL}/?s={urllib.parse.quote(text)}"
            movie_info = {
                "title": text,
                "url": fallback_url,
                "image": None
            }

    # বাটন তৈরি
    buttons = [
        [InlineKeyboardButton("📥 Watch / Download", url=movie_info["url"])],
        [InlineKeyboardButton("🌐 Visit MovieLol.net", url=WEBSITE_URL)]
    ]
    reply_markup = InlineKeyboardMarkup(buttons)
    
    caption = (
        f"🎬 *{movie_info['title']}*\n\n"
        f"🔗 *Direct Link:* {movie_info['url']}\n"
        f"🌐 *Main Site:* {WEBSITE_URL}\n\n"
        f"✨ Enjoy high quality streaming & downloads on MovieLol!"
    )

    # ছবি থাকলে ছবিসহ পাঠাবে, না থাকলে শুধু টেক্সট
    if movie_info.get("image"):
        try:
            await update.message.reply_photo(
                photo=movie_info["image"],
                caption=caption,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
            return
        except Exception as e:
            logging.error(f"Photo send error: {e}")
            
    await update.message.reply_text(
        caption,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

# Telegram Application তৈরি
application = ApplicationBuilder().token(BOT_TOKEN).build()
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

@flask_app.route(f"/{BOT_TOKEN}", methods=["POST"])
async def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    await application.process_update(update)
    return Response(status=200)

@flask_app.route("/")
def index():
    return "Bot is running!"

if __name__ == "__main__":
    if RENDER_EXTERNAL_URL:
        webhook_url = f"{RENDER_EXTERNAL_URL}/{BOT_TOKEN}"
        requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook?url={webhook_url}")
    
    flask_app.run(host="0.0.0.0", port=PORT)
