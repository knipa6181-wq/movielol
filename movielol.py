import os
import time
import requests
import threading
from bs4 import BeautifulSoup
from flask import Flask, request
import telebot

# কনফিগারেশন
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
SITE_URL = os.getenv("SITE_URL", "https://movielol.net")
CHANNEL_OR_CHAT_ID = os.getenv("CHANNEL_ID", "YOUR_CHANNEL_ID_HERE")

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# ট্র্যাকিংয়ের জন্য শেষ দেখা মুভির লিংক
last_seen_movie_link = None

def get_latest_movies_from_site():
    """সাইট থেকে সাম্প্রতিক মুভিগুলো স্ক্র্যাপ করে নিয়ে আসবে"""
    movies = []
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(SITE_URL, headers=headers, timeout=15)
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
    """ব্যবহারকারীর দেওয়া সার্চ কি-ওয়ার্ড অনুযায়ী নিখুঁত ফিল্টারিং করে মুভি খুঁজবে"""
    results = []
    try:
        search_url = f"{SITE_URL}/?s={requests.utils.quote(query)}"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(search_url, headers=headers, timeout=15)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            query_clean = query.lower().strip()
            
            for a_tag in soup.find_all('a', href=True):
                href = a_tag['href']
                if '/watch/' in href:
                    img_tag = a_tag.find('img')
                    if img_tag:
                        img_url = img_tag.get('src') or img_tag.get('data-src') or ''
                        title = img_tag.get('alt') or a_tag.get_text(strip=True)
                        full_link = href if href.startswith('http') else SITE_URL.rstrip('/') + href
                        
                        # টাইটেল ও লিংকের সাথে সার্চ কি-ওয়ার্ডের মিল আছে কিনা যাচাই
                        title_clean = title.lower()
                        link_clean = full_link.lower()
                        
                        # সার্চ শব্দের প্রতিটি অংশ চেক করা
                        query_words = query_clean.split()
                        matches = all(word in title_clean or word in link_clean for word in query_words)
                        
                        if matches and not any(r['link'] == full_link for r in results):
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

# ইউজার কোনো মেসেজ পাঠালে সার্চ করবে
@bot.message_handler(func=lambda message: True)
def handle_search(message):
    query = message.text.strip()
    
    # কমান্ড এড়িয়ে যাওয়া
    if query.startswith('/'):
        return

    bot.send_chat_action(message.chat.id, 'typing')
    results = search_movie_on_site(query)
    
    if not results:
        bot.reply_to(message, "দুঃখিত, এই নামের কোনো মুভি পাওয়া যায়নি। সঠিক নাম লিখে আবার চেষ্টা করুন।")
        return

    # সর্বোচ্চ ৫টি প্রাসঙ্গিক রেজাল্ট দেখাবে যাতে স্প্যাম না হয়
    for item in results[:5]:
        caption = f"🎬 *{item['title']}*\n\n🔗 [ডাউনলোড লিংক]({item['link']})"
        if item.get('image') and item['image'].startswith('http'):
            try:
                bot.send_photo(message.chat.id, item['image'], caption=caption, parse_mode='Markdown')
                continue
            except Exception as e:
                print(f"Error sending photo: {e}")
        
        bot.send_message(message.chat.id, caption, parse_mode='Markdown')

def auto_check_new_movies():
    """ব্যাকগ্রাউন্ডে মনিটর করবে এবং শুধুমাত্র নতুন মুভি আপলোড হলে অ্যালার্ট পাঠাবে"""
    global last_seen_movie_link
    
    # শুরুতে সাইটের সর্বশেষ মুভিটির লিংক সেভ করে রাখা
    try:
        initial_movies = get_latest_movies_from_site()
        if initial_movies:
            last_seen_movie_link = initial_movies[0]['link']
    except Exception as e:
        print(f"Initial setup error: {e}")

    while True:
        try:
            movies = get_latest_movies_from_site()
            if movies and last_seen_movie_link:
                latest = movies[0]
                # নতুন আপলোড পাওয়া গেলে
                if latest['link'] != last_seen_movie_link:
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

# Render-এর জন্য হেলথ চেক রুট
@app.route('/')
def home():
    return "Bot is running perfectly!", 200

# টেলিগ্রাম ওয়েব হুক
@app.route(f"/{BOT_TOKEN}", methods=['POST'])
def telegram_webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return "OK", 200
    return "Forbidden", 403

if __name__ == '__main__':
    # অটো চেকার থ্রেড ব্যাকগ্রাউন্ডে চালু করা
    monitor_thread = threading.Thread(target=auto_check_new_movies, daemon=True)
    monitor_thread.start()
    
    # Render Webhook সক্রিয় করা
    render_url = os.getenv("RENDER_EXTERNAL_URL")
    if render_url:
        bot.remove_webhook()
        time.sleep(1)
        bot.set_webhook(url=f"{render_url.rstrip('/')}/{BOT_TOKEN}")
    
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
