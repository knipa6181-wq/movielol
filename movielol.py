import os
import re
import time
import requests
import threading
from bs4 import BeautifulSoup
from flask import Flask, request
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# কনফিগারেশন
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
SITE_URL = os.getenv("SITE_URL", "https://movielol.net")
CHANNEL_OR_CHAT_ID = os.getenv("CHANNEL_ID", "")

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# সাইটের ক্যাশ ও দেখা মুভি ট্র্যাক রাখার জন্য
latest_site_movies = []
seen_movie_links = set()

def clean_movie_title(text):
    """টাইটেল ও সার্চ কোয়েরি থেকে অপ্রয়োজনীয় ট্যাগ বাদ দেওয়া"""
    noise_words = [
        r'\bfull movie\b', r'\bwatch online\b', r'\bdownload\b', 
        r'\bhd\b', r'\bweb-dl\b', r'\bbluray\b', r'\borg\b', 
        r'\bhevc\b', r'\bhindi\b', r'\bdubbed\b', r'\b720p\b', 
        r'\b1080p\b', r'\b480p\b', r'\bseason\b', r'\bseries\b'
    ]
    cleaned = text
    for word in noise_words:
        cleaned = re.sub(word, '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'[\[\]\(\)\-\:_\|]', ' ', cleaned)
    return ' '.join(cleaned.split()).strip().lower()

def fetch_movies_from_site():
    """সাইট থেকে রিয়েল-টাইম মুভি ডেটা সংগ্রহ"""
    movies = []
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': SITE_URL
        }
        response = requests.get(SITE_URL, headers=headers, timeout=20)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            for a_tag in soup.find_all('a', href=True):
                href = a_tag['href']
                if '/watch/' in href:
                    img_tag = a_tag.find('img')
                    if img_tag:
                        img_url = img_tag.get('src') or img_tag.get('data-src') or ''
                        raw_title = img_tag.get('alt') or a_tag.get_text(strip=True)
                        full_link = href if href.startswith('http') else SITE_URL.rstrip('/') + href
                        
                        if raw_title and not any(m['link'] == full_link for m in movies):
                            movies.append({
                                'title': raw_title.strip(),
                                'link': full_link,
                                'image': img_url
                            })
    except Exception as e:
        print(f"Fetch error: {e}")
    return movies

def search_movie_on_site(query):
    """ফিল্টারিং সহ সার্চ লজিক"""
    results = []
    cleaned_query = clean_movie_title(query)

    # ৩ অক্ষরের কম হলে সরাসরি বাদ (ইউজারকে কারণ জানানো হবে না)
    if len(cleaned_query) < 3:
        return results

    try:
        search_url = f"{SITE_URL}/?s={requests.utils.quote(cleaned_query)}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(search_url, headers=headers, timeout=20)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            query_words = cleaned_query.split()

            for a_tag in soup.find_all('a', href=True):
                href = a_tag['href']
                if '/watch/' in href:
                    img_tag = a_tag.find('img')
                    if img_tag:
                        img_url = img_tag.get('src') or img_tag.get('data-src') or ''
                        raw_title = img_tag.get('alt') or a_tag.get_text(strip=True)
                        full_link = href if href.startswith('http') else SITE_URL.rstrip('/') + href
                        
                        title_clean = clean_movie_title(raw_title)
                        url_clean = clean_movie_title(href)

                        # সার্চের মূল শব্দের সাথে মিল নিশ্চিত করা
                        if any(w in title_clean or w in url_clean for w in query_words):
                            if not any(r['link'] == full_link for r in results):
                                results.append({
                                    'title': raw_title.strip(),
                                    'link': full_link,
                                    'image': img_url
                                })
    except Exception as e:
        print(f"Search error: {e}")
    return results

def send_movie_card(chat_id, movie, prefix="🎬"):
    """স্টাইলিশ থাম্বনেইল ও বাটনসহ মুভি কার্ড পাঠানো"""
    caption = (
        f"{prefix} *{movie['title']}*\n\n"
        f"⭐ *Quality:* Full HD / WEB-DL\n"
        f"🔊 *Audio:* Multi-Audio / Original\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("📥 ডাউনলোড ও দেখুন (Watch/Download)", url=movie['link']))

    if movie.get('image') and movie['image'].startswith('http'):
        try:
            bot.send_photo(chat_id, movie['image'], caption=caption, reply_markup=markup, parse_mode='Markdown')
            return
        except Exception:
            pass
    bot.send_message(chat_id, caption, reply_markup=markup, parse_mode='Markdown')

# /start কমান্ড হ্যান্ডলার
@bot.message_handler(commands=['start'])
def send_welcome(message):
    welcome_text = (
        "✨ *স্বাগতম মুভি বটের জগতে!* 🍿\n"
        "মুভি দেখতে চাইলে নিচে সঠিক ও পুরো নামটি লিখে সার্চ করুন।\n\n"
        "🌐 *Welcome to Movie Bot!* 🎬\n"
        "Please type the full and correct movie name to search.\n\n"
        "🇮🇳 *मूवी बॉट में आपका स्वागत है!* 🎥\n"
        "मूवी खोजने के लिए कृपया पूरा और सही नाम लिखकर भेजें।"
    )
    bot.reply_to(message, welcome_text, parse_mode='Markdown')

    # সাইটের সর্বশেষ নতুন মুভিগুলো বটের ভেতরেই শো করানো
    current_movies = latest_site_movies if latest_site_movies else fetch_movies_from_site()
    if current_movies:
        bot.send_message(message.chat.id, "🔥 *সাম্প্রতিক আপলোড হওয়া নতুন মুভিগুলো:* 👇", parse_mode='Markdown')
        for m in current_movies[:2]:
            send_movie_card(message.chat.id, m, prefix="🔥 [New Upload]")
            time.sleep(0.3)

# সার্চ হ্যান্ডলার
@bot.message_handler(func=lambda message: True)
def handle_search(message):
    query = message.text.strip()
    if query.startswith('/'):
        return

    bot.send_chat_action(message.chat.id, 'typing')
    results = search_movie_on_site(query)

    # সঠিক ও পুরো নাম চাওয়ার ৩ ভাষার ইমোজি সহ মেসেজ
    if not results:
        not_found_msg = (
            "⚠️ 🔍 *সঠিক ও পুরো নামটি দিন!* 🎬\n"
            "মুভিটি খুঁজে পেতে দয়া করে বানান ঠিক রেখে পুরো নামটি স্পষ্টভাবে লিখুন। 🍿\n\n"
            "⚠️ 🔍 *Please provide the full and correct name!* 🎥\n"
            "Kindly type the accurate movie title with proper spelling to find it. 🍿\n\n"
            "⚠️ 🔍 *कृपया पूरा और सही नाम लिखें!* 🎬\n"
            "मूवी खोजने के लिए कृपया सही स्पेलिंग के साथ पूरा नाम लिखकर भेजें। 🍿"
        )
        bot.reply_to(message, not_found_msg, parse_mode='Markdown')
        return

    # শুধুমাত্র সর্বোচ্চ ৩টি প্রাসঙ্গিক রেজাল্ট দেখানো
    for item in results[:3]:
        send_movie_card(message.chat.id, item)
        time.sleep(0.3)

# ব্যাকগ্রাউন্ড মনিটর (শুধুমাত্র চ্যানেলে পোস্ট ও ডেটা আপডেট করবে)
def auto_check_new_movies():
    global latest_site_movies, seen_movie_links
    time.sleep(5)

    initial_movies = fetch_movies_from_site()
    if initial_movies:
        latest_site_movies = initial_movies
        seen_movie_links = {m['link'] for m in initial_movies}

    while True:
        try:
            current = fetch_movies_from_site()
            if current:
                latest_site_movies = current
                new_movies = [m for m in current if m['link'] not in seen_movie_links]

                # শুধু চ্যানেলে নোটিফিকেশন যাবে যদি CHANNEL_ID দেওয়া থাকে (ইউজারদের বিরক্ত করবে না)
                if new_movies and CHANNEL_OR_CHAT_ID:
                    for m in reversed(new_movies):
                        send_movie_card(CHANNEL_OR_CHAT_ID, m, prefix="🔥 [New Release]")
                        seen_movie_links.add(m['link'])
                        time.sleep(1)
                else:
                    for m in new_movies:
                        seen_movie_links.add(m['link'])
        except Exception as e:
            print(f"Background check error: {e}")

        time.sleep(90)  # প্রতি ৯০ সেকেন্ডে সাইট রিফ্রেশ হবে

@app.route('/')
def home():
    return "Bot is running perfectly!", 200

@app.route(f"/{BOT_TOKEN}", methods=['POST'])
def telegram_webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return "OK", 200
    return "Forbidden", 403

if __name__ == '__main__':
    monitor_thread = threading.Thread(target=auto_check_new_movies, daemon=True)
    monitor_thread.start()

    render_url = os.getenv("RENDER_EXTERNAL_URL")
    if render_url:
        bot.remove_webhook()
        time.sleep(1)
        bot.set_webhook(url=f"{render_url.rstrip('/')}/{BOT_TOKEN}")

    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
