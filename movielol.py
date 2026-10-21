import json
import os
import urllib.parse
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# আপনার টেলিগ্রাম বট টোকেন যুক্ত করা হয়েছে
BOT_TOKEN = "8840283228:AAFy1dZxOfa9tFTksodSAVK38UkwtAlauU8"
WEBSITE_URL = "https://movielol.net"
DATA_FILE = "movies_data.json"

# ডাটা লোড করার ফাংশন
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []

# ডাটা সেভ করার ফাংশন
def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

movies_db = load_data()

# /start কমান্ড হ্যান্ডলার
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🎬 *MovieLoL.net Link Poster Bot* 🍿\n\n"
        "মুভির নাম এবং লিংক যেকোনো ফরম্যাটে পাঠান:\n\n"
        "🔹 *পদ্ধতি ১ (নাম ও লিংক):*\n"
        "`Jawan - https://downloadlink.com/file`\n\n"
        "🔹 *পদ্ধতি ২ (শুধুমাত্র নাম):*\n"
        "`Inception` (সাইটে স্বয়ংক্রিয় সার্চ লিংক হবে)\n\n"
        "সব সংরক্ষিত পোস্ট দেখতে `/all` লিখুন।"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

# মেসেজ প্রসেস এবং পোস্ট করার হ্যান্ডলার
async def process_movie_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw_text = update.message.text.strip()
    
    movie_name = ""
    download_url = ""

    # লিংক শনাক্ত করার লজিক
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

    # ডাটাবেজে সংরক্ষণ
    entry = {"title": movie_name, "link": download_url}
    movies_db.append(entry)
    save_data(movies_db)

    # ক্লিক বাটন তৈরি
    buttons = [
        [InlineKeyboardButton("▶️ Watch / Download", url=download_url)],
        [InlineKeyboardButton("🌐 Visit MovieLoL.net", url=WEBSITE_URL)]
    ]
    reply_markup = InlineKeyboardMarkup(buttons)

    # টেলিগ্রাম কার্ড টেক্সট
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

# সংরক্ষিত লিংকগুলো দেখার হ্যান্ডলার
async def show_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not movies_db:
        await update.message.reply_text("এখনও কোনো মুভি লিংক যুক্ত করা হয়নি।")
        return

    text = "📁 *MovieLoL.net সংরক্ষিত মুভি তালিকা (সর্বশেষ ২০টি):*\n\n"
    for idx, item in enumerate(movies_db[-20:], 1):
        text += f"{idx}. [{item['title']}]({item['link']})\n"

    await update.message.reply_text(text, parse_mode="Markdown", disable_web_page_preview=True)

if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("all", show_all))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), process_movie_post))

    print("MovieLoL Bot চালু হয়েছে...")
    app.run_polling()
