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

# গ্লোবাল স্টেট
latest_cached_movies = []
seen_movie_links = set()

# রিকোয়েস্ট সেশন
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9,bn;q=0.8',
    'Referer': SITE_URL
})

def clean_movie_title(text):
    """টাইটেল ও সার্চ শব্দ থেকে অপ্রয়োজনীয় ট্যাগ সম্পূর্ণ বাদ দেওয়া"""
    if not text:
        return ""
    noise_patterns = [
        r'\bfull movie\b', r'\bwatch online\b', r'\bdownload\b', 
        r'\bhd\b', r'\bweb-dl\b', r'\bbluray\b', r'\borg\b', 
        r'\bhevc\b', r'\bhindi\b', r'\bdubbed\b', r'\b720p\b', 
        r'\b1080p\b', r'\b480p\b', r'\bseason\b', r'\bseries\b',
        r'\b20[0-2][0-9]\b', r'\b19[0-9][0-9]\b'
    ]
    cleaned = text.lower()
    for pattern in noise_patterns:
        cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'[^a-zA-Z0-9\s]', ' ', cleaned)
    return ' '.join(cleaned.split()).strip()

def extract_image(img_tag):
    """পোস্টার ইমেজ পাওয়ার সব উপায় নিশ্চিত করা"""
    if not img_tag:
        return None
    for attr in ['data-src', 'data-lazy-src', 'data-original', 'src']:
        src = img_tag.get(attr)
        if src and src.startswith('http'):
            return src
    return None

def fetch_movies_from_site():
    """সাইট থেকে রিয়েল-টাইম মুভি ডেটা সংগ্রহ"""
    movies = []
    try:
        res = session.get(SITE_URL, timeout=15)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            for a_tag in soup.find_all('a', href=True):
                href = a_tag['href']
                if '/watch/' in href:
                    img_tag = a_tag.find('img')
                    raw_title = img_tag.get('alt') if img_tag and img_tag.get('alt') else a_tag.get_text(strip=True)
                    img_url = extract_image(img_tag)
                    full_link = href if href.startswith('http') else SITE_URL.rstrip('/') + href
                    
                    if raw_title and not any(m['link'] == full_link for m in movies):
                        movies.append({
                            'title': raw_title.strip(),
                            'link': full_link,
                            'image': img_url
                        })
    except Exception as e:
        print(f"Scraping Error: {e}")
    return movies

def search_movie_on_site(query):
    """সার্চ ফিল্টারিং লজিক"""
    results = []
    cleaned_query = clean_movie_title(query)
    
    # ব্যাকগ্রাউন্ডে ৩ অক্ষরের কম হলে সরাসরি বাতিল (ইউজারকে কারণ না জানিয়ে)
    if len(cleaned_query) < 3:
        return results

    try:
        search_url = f"{SITE_URL}/?s={requests.utils.quote(cleaned_query)}"
        res = session.get(search_url, timeout=15)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            query_tokens = set(cleaned_query.split())

            for a_tag in soup.find_all('a', href=True):
                href = a_tag['href']
                if '/watch/' in href:
                    img_tag = a_tag.find('img')
                    raw_title = img_tag.get('alt') if img_tag and img_tag.get('alt') else a_tag.get_text(strip=True)
                    img_url = extract_image(img_tag)
                    full_link = href if href.startswith('http') else SITE_URL.rstrip('/') + href

                    title_cleaned = clean_movie_title(raw_title)
                    url_cleaned = clean_movie_title(href)
                    combined_tokens = set(title_cleaned.split() + url_cleaned.split())

                    # সার্চ শব্দের প্রতিটি অংশ মিললে তবেই নেওয়া হবে
                    if query_tokens.issubset(combined_tokens) or cleaned_query in title_cleaned:
                        if not any(r['link'] == full_link for r in results):
                            results.append({
                                'title': raw_title.strip(),
                                'link': full_link,
                                'image': img_url
                            })
    except Exception as e:
        print(f"Search Execution Error: {e}")
    return results

def send_stylish_card(chat_id, movie, prefix="🎬"):
    """স্টাইলিশ লেআউট ও ডাউনলোড বাটন তৈরি"""
    caption = (
        f"{prefix} *{movie['title']}*\n\n"
        f"⚡ *Quality:* Full HD / WEB-DL\n"
        f"🎧 *Audio:* Multi-Audio / Original\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("📥 ডাউনলোড ও দেখুন (Watch / Download)", url=movie['link']))

    if movie.get('image'):
        try:
            bot.send_photo(chat_id, movie['image'], caption=caption, reply_markup=markup, parse_mode='Markdown')
            return
        except Exception:
            pass
    bot.send_message(chat_id, caption, reply_markup=markup, parse_mode='Markdown')

# /start হ্যান্ডলার
@bot.message_handler(commands=['start'])
def handle_start(message):
    welcome_text = (
        "✨ *স্বাগতম মুভি বটের জগতে!* 🍿\n"
        "মুভি দেখতে চাইলে নিচে সঠিক ও পুরো নামটি লিখে সার্চ করুন।\n\n"
        "🌐 *Welcome to Movie Bot!* 🎬\n"
        "Please type the full and correct movie name to search.\n\n"
        "🇮🇳 *मूवी बॉट में आपका स्वागत है!* 🎥\n"
        "मूवी खोजने के लिए कृपया पूरा और सही नाम लिखकर भेजें।"
    )
    bot.reply_to(message, welcome_text, parse_mode='Markdown')

    # সাইটের সর্বশেষ নতুন মুভি বটের ভেতরে শো করা
    movies = latest_cached_movies if latest_cached_movies else fetch_movies_from_site()
    if movies:
        bot.send_message(message.chat.id, "🔥 *সাম্প্রতিক আপলোড হওয়া মুভিগুলো:* 👇", parse_mode='Markdown')
        for m in movies[:2]:
            send_stylish_card(message.chat.id, m, prefix="🔥 [New Upload]")
            time.sleep(0.3)

# সার্চ রিকোয়েস্ট হ্যান্ডলার
@bot.message_handler(func=lambda message: True)
def handle_search(message):
    query = message.text.strip()
    if query.startswith('/'):
        return

    bot.send_chat_action(message.chat.id, 'typing')
    results = search_movie_on_site(query)

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

    for item in results[:2]:
        send_stylish_card(message.chat.id, item)
        time.sleep(0.3)

# ব্যাকগ্রাউন্ড চেকার (রিয়েল-টাইম নতুন মুভি ডিটেক্টর)
def auto_check_new_movies():
    global latest_cached_movies, seen_movie_links
    time.sleep(5)

    initial = fetch_movies_from_site()
    if initial:
        latest_cached_movies = initial
        seen_movie_links = {m['link'] for m in initial}

    while True:
        try:
            current = fetch_movies_from_site()
            if current:
                latest_cached_movies = current
                new_movies = [m for m in current if m['link'] not in seen_movie_links]

                if new_movies and CHANNEL_OR_CHAT_ID:
                    for m in reversed(new_movies):
                        send_stylish_card(CHANNEL_OR_CHAT_ID, m, prefix="🔥 [New Release]")
                        seen_movie_links.add(m['link'])
                        time.sleep(1)
                else:
                    for m in new_movies:
                        seen_movie_links.add(m['link'])
        except Exception as e:
            print(f"Background Loop Error: {e}")

        time.sleep(90) # প্রতি ৯০ সেকেন্ডে সাইট মনিটর করবে

@app.route('/')
def home():
    return "Bot is active and running!", 200

@app.route(f"/{BOT_TOKEN}", methods=['POST'])
def telegram_webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return "OK", 200
    return "Forbidden", 403

if __name__ == '__main__':
    # ব্যাকগ্রাউন্ড থ্রেড রান করা
    monitor_thread = threading.Thread(target=auto_check_new_movies, daemon=True)
    monitor_thread.start()

    # ওয়েব-হুক সেটআপ
    render_url = os.getenv("RENDER_EXTERNAL_URL")
    if render_url:
        bot.remove_webhook()
        time.sleep(1)
        bot.set_webhook(url=f"{render_url.rstrip('/')}/{BOT_TOKEN}")

    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
