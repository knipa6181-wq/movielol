import os
import time
import threading
import requests
from bs4 import BeautifulSoup
from flask import Flask, request
import telebot

# আপনার কনফিগারেশন
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
SITE_URL = "https://movielol.onrender.com"  # অথবা আপনার মূল মুভি সাইটের ডোমেইন
CHANNEL_OR_CHAT_ID = os.getenv("CHANNEL_ID", "YOUR_CHAT_OR_CHANNEL_ID")

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# ট্র্যাক রাখার জন্য শেষ পাওয়া মুভির লিংক
last_seen_movie_link = None

def get_latest_movies_from_site():
    """সাইট থেকে সাম্প্রতিক মুভিগুলো স্ক্র্যাপ করে"""
    movies = []
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(SITE_URL, headers=headers, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            # আপনার সাইটের এইচটিএমএল স্ট্রাকচার অনুযায়ী ক্লাস/ট্যাগ নির্বাচন করুন
            articles = soup.find_all("article")
            for item in articles:
                title_tag = item.find("h2") or item.find("a")
                link_tag = item.find("a")
                img_tag = item.find("img")

                title = title_tag.get_text(strip=True) if title_tag else "No Title"
                link = link_tag.get("href") if link_tag else None
                img = img_tag.get("src") if img_tag else None

                if link:
                    movies.append({"title": title, "link": link, "image": img})
    except Exception as e:
        print(f"Error fetching latest movies: {e}")
    return movies

def search_movie_on_site(query):
    """ইউজারের সার্চ কুয়েরি দিয়ে সাইটে খোঁজে"""
    results = []
    try:
        search_url = f"{SITE_URL}/?s={requests.utils.quote(query)}"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(search_url, headers=headers, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            articles = soup.find_all("article")
            for item in articles[:5]:  # প্রথম ৫টি রেজাল্ট নেবে
                title_tag = item.find("h2") or item.find("a")
                link_tag = item.find("a")
                img_tag = item.find("img")

                title = title_tag.get_text(strip=True) if title_tag else "Movie Link"
                link = link_tag.get("href") if link_tag else None
                img = img_tag.get("src") if img_tag else None

                if link:
                    results.append({"title": title, "link": link, "image": img})
    except Exception as e:
        print(f"Search error: {e}")
    return results

# /start কমান্ড হ্যান্ডলার
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(
        message,
        "স্বাগতম! আপনি যে মুভিটি দেখতে চান তার নাম লিখে সার্চ করুন।"
    )

# ইউজার মেসেজ দিয়ে সার্চ করলে
@bot.message_handler(func=lambda message: True)
def handle_search(message):
    query = message.text.strip()
    bot.send_chat_action(message.chat.id, 'typing')
    
    results = search_movie_on_site(query)
    
    if not results:
        bot.reply_to(message, "দুঃখিত, কোনো মুভি পাওয়া যায়নি। নাম সঠিকভাবে লিখে আবার চেষ্টা করুন।")
        return

    for item in results:
        caption = f"🎬 *{item['title']}*\n\n🔗 [ডাউনলোড / ওয়াচ লিংক]({item['link']})"
        if item['image']:
            try:
                bot.send_photo(message.chat.id, item['image'], caption=caption, parse_mode="Markdown")
                continue
            except Exception:
                pass
        bot.send_message(message.chat.id, caption, parse_mode="Markdown")

def auto_check_new_movies():
    """ব্যাকগ্রাউন্ডে নতুন মুভি মনিটর করে স্বয়ংক্রিয় মেসেজ পাঠানো"""
    global last_seen_movie_link
    while True:
        try:
            movies = get_latest_movies_from_site()
            if movies:
                latest = movies[0]
                if last_seen_movie_link is None:
                    last_seen_movie_link = latest['link']
                elif latest['link'] != last_seen_movie_link:
                    last_seen_movie_link = latest['link']
                    caption = f"🔥 *নতুন মুভি আপলোড হয়েছে!*\n\n🎬 *{latest['title']}*\n\n🔗 [এখানে দেখুন]({latest['link']})"
                    if latest['image']:
                        try:
                            bot.send_photo(CHANNEL_OR_CHAT_ID, latest['image'], caption=caption, parse_mode="Markdown")
                        except Exception:
                            bot.send_message(CHANNEL_OR_CHAT_ID, caption, parse_mode="Markdown")
                    else:
                        bot.send_message(CHANNEL_OR_CHAT_ID, caption, parse_mode="Markdown")
        except Exception as e:
            print(f"Background check error: {e}")
        time.sleep(300)  # প্রতি ৫ মিনিট পরপর সাইট চেক করবে

# রেন্ডার ওয়েবুক রুট
@app.route(f"/{BOT_TOKEN}", methods=['POST'])
def telegram_webhook():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "OK", 200

@app.route('/')
def home():
    return "Bot is running perfectly!", 200

if __name__ == '__main__':
    # ব্যাকগ্রাউন্ড চেকার চালু
    threading.Thread(target=auto_check_new_movies, daemon=True).start()
    
    # Render Webhook সেটআপ
    render_url = os.getenv("RENDER_EXTERNAL_URL")
    if render_url:
        bot.remove_webhook()
        bot.set_webhook(url=f"{render_url}/{BOT_TOKEN}")
        
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
