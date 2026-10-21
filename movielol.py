import os
import time
import requests
import threading
from bs4 import BeautifulSoup
from flask import Flask, request
import telebot

# আপনার কনফিগারেশন (Render-এর Environment Variables থেকে নেবে অথবা ডিফল্ট মান ব্যবহার করবে)
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
SITE_URL = os.getenv("SITE_URL", "https://movielol.net")
CHANNEL_OR_CHAT_ID = os.getenv("CHANNEL_ID", "YOUR_CHANNEL_ID_HERE")

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# ট্র্যাকিংয়ের জন্য শেষ পাওয়া মুভির লিংক
last_seen_movie_link = None

def get_latest_movies_from_site():
    """সাইট থেকে সাম্প্রতিক রিলিজ হওয়া মুভিগুলো সংগ্রহ করবে"""
    movies = []
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(SITE_URL, headers=headers, timeout=15)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            # মুভি কার্ডের <a> ট্যাগগুলো খুঁজে বের করা
            for a_tag in soup.find_all('a', href=True):
                href = a_tag['href']
                if '/watch/' in href:
                    img_tag = a_tag.find('img')
                    if img_tag:
                        img_url = img_tag.get('src') or img_tag.get('data-src') or ''
                        title = img_tag.get('alt') or a_tag.get_text(strip=True)
                        full_link = href if href.startswith('http') else SITE_URL.rstrip('/') + href
                        
                        if title and not any(m['link'] == full_link for m in movies):
                            movies.append({
                                'title': title.strip(),
                                'link': full_link,
                                'image': img_url
                            })
    except Exception as e:
        print(f"Error fetching latest movies: {e}")
    return movies

def search_movie_on_site(query):
    """ব্যবহারকারীর সার্চ অনুযায়ী মুভি খুঁজবে"""
    results = []
    try:
        search_url = f"{SITE_URL}/?s={requests.utils.quote(query)}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(search_url, headers=headers, timeout=15)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            for a_tag in soup.find_all('a', href=True):
                href = a_tag['href']
                if '/watch/' in href:
                    img_tag = a_tag.find('img')
                    if img_tag:
                        img_url = img_tag.get('src') or img_tag.get('data-src') or ''
                        title = img_tag.get('alt') or a_tag.get_text(strip=True)
                        full_link = href if href.startswith('http') else SITE_URL.rstrip('/') + href
                        
                        if title and not any(r['link'] == full_link for r in results):
                            results.append({
                                'title': title.strip(),
                                'link': full_link,
                                'image': img_url
                            })
    except Exception as e:
        print(f"Search error: {e}")
    return results

# /start কমান্ড হ্যান্ডলার
@bot.message_handler(commands=['start'])
def send_welcome(message):
    welcome_text = "স্বাগতম! আপনি যে মুভিটি দেখতে চান তার নাম লিখে সার্চ করুন।"
    bot.reply_to(message, welcome_text)

# ইউজার মেসেজ দিয়ে সার্চ করার হ্যান্ডলার
@bot.message_handler(func=lambda message: True)
def handle_search(message):
    query = message.text.strip()
    bot.send_chat_action(message.chat.id, 'typing')
    
    results = search_movie_on_site(query)
    
    if not results:
        bot.reply_to(message, "দুঃখিত, কোনো মুভি পাওয়া যায়নি। নাম সঠিকভাবে লিখে আবার চেষ্টা করুন।")
        return

    for item in results:
        caption = f"🎬 *{item['title']}*\n\n🔗 [ডাউনলোড লিংক]({item['link']})"
        if item.get('image') and item['image'].startswith('http'):
            try:
                bot.send_photo(message.chat.id, item['image'], caption=caption, parse_mode='Markdown')
                continue
            except Exception as e:
                print(f"Error sending photo: {e}")
        
        bot.send_message(message.chat.id, caption, parse_mode='Markdown')

def auto_check_new_movies():
    """ব্যাকগ্রাউন্ডে নতুন মুভি মনিটর করে চ্যানেলে পোস্ট করবে"""
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
                    caption = f"🔥 *নতুন মুভি আপলোড হয়েছে!*\n\n🎬 *{latest['title']}*\n\n🔗 [এখনই দেখুন ও ডাউনলোড করুন]({latest['link']})"
                    
                    if CHANNEL_OR_CHAT_ID and CHANNEL_OR_CHAT_ID != "YOUR_CHANNEL_ID_HERE":
                        if latest.get('image') and latest['image'].startswith('http'):
                            try:
                                bot.send_photo(CHANNEL_OR_CHAT_ID, latest['image'], caption=caption, parse_mode='Markdown')
                            except Exception:
                                bot.send_message(CHANNEL_OR_CHAT_ID, caption, parse_mode='Markdown')
                        else:
                            bot.send_message(CHANNEL_OR_CHAT_ID, caption, parse_mode='Markdown')
        except Exception as e:
            print(f"Background check error: {e}")
        
        time.sleep(300)  # প্রতি ৫ মিনিট পরপর চেক করবে

# রেন্ডার সার্ভার সক্রিয় রাখার রুট
@app.route('/')
def home():
    return "Bot is running perfectly!", 200

# টেলিগ্রাম ওয়েবহুক এন্ডপয়েন্ট
@app.route(f"/{BOT_TOKEN}", methods=['POST'])
def telegram_webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return "OK", 200
    return "Forbidden", 403

if __name__ == '__main__':
    # ব্যাকগ্রাউন্ড চেকার চালু করা
    monitor_thread = threading.Thread(target=auto_check_new_movies, daemon=True)
    monitor_thread.start()
    
    # Render Webhook সেটআপ
    render_url = os.getenv("RENDER_EXTERNAL_URL")
    if render_url:
        bot.remove_webhook()
        time.sleep(1)
        bot.set_webhook(url=f"{render_url.rstrip('/')}/{BOT_TOKEN}")
    
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
