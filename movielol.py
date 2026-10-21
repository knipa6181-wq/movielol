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
CHANNEL_OR_CHAT_ID = os.getenv("CHANNEL_ID", "YOUR_CHANNEL_ID_HERE")

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# ট্র্যাকিংয়ের জন্য শেষ দেখা মুভির লিংক
last_seen_movie_link = None

def clean_movie_title(text):
    """টাইটেল ও সার্চ কোয়েরি থেকে অপ্রয়োজনীয় শব্দ মুছে মূল নাম বের করার ফাংশন"""
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

def get_latest_movies_from_site():
    """সাইট থেকে সাম্প্রতিক মুভিগুলো সংগ্রহ করবে"""
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
                        raw_title = img_tag.get('alt') or a_tag.get_text(strip=True)
                        full_link = href if href.startswith('http') else SITE_URL.rstrip('/') + href
                        
                        if raw_title and not any(m['link'] == full_link for m in movies):
                            movies.append({
                                'title': raw_title.strip(),
                                'link': full_link,
                                'image': img_url
                            })
    except Exception as e:
        print(f"Error fetching latest movies: {e}")
    return movies

def search_movie_on_site(query):
    """ইউজারের সার্চ ফিল্টার করে শুধুমাত্র সঠিক মুভিটি রিটার্ন করবে"""
    results = []
    try:
        search_query = clean_movie_title(query)
        if not search_query:
            return results

        search_url = f"{SITE_URL}/?s={requests.utils.quote(search_query)}"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(search_url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            query_words = search_query.split()
            
            for a_tag in soup.find_all('a', href=True):
                href = a_tag['href']
                if '/watch/' in href:
                    img_tag = a_tag.find('img')
                    if img_tag:
                        img_url = img_tag.get('src') or img_tag.get('data-src') or ''
                        raw_title = img_tag.get('alt') or a_tag.get_text(strip=True)
                        full_link = href if href.startswith('http') else SITE_URL.rstrip('/') + href
                        
                        cleaned_title = clean_movie_title(raw_title)
                        cleaned_url = clean_movie_title(href)

                        # সার্চ শব্দের মিল নিশ্চিত করা
                        is_match = any(word in cleaned_title or word in cleaned_url for word in query_words)
                        
                        if is_match and not any(r['link'] == full_link for r in results):
                            results.append({
                                'title': raw_title.strip(),
                                'link': full_link,
                                'image': img_url
                            })
    except Exception as e:
        print(f"Search error: {e}")
    return results

# ৩ ভাষার স্বাগতম বার্তা (/start)
@bot.message_handler(commands=['start'])
def send_welcome(message):
    welcome_text = (
        "👋 *স্বাগতম!*\n"
        "আপনি যে মুভিটি দেখতে চান তার নাম লিখে সার্চ করুন।\n\n"
        "🌐 *Welcome!*\n"
        "Type and search the name of the movie you want to watch.\n\n"
        "🇮🇳 *नमस्ते!*\n"
        "आप जो मूवी देखना चाहते हैं उसका नाम लिखकर सर्च करें।"
    )
    bot.reply_to(message, welcome_text, parse_mode='Markdown')

# সার্চ হ্যান্ডলার
@bot.message_handler(func=lambda message: True)
def handle_search(message):
    query = message.text.strip()
    if query.startswith('/'):
        return

    bot.send_chat_action(message.chat.id, 'typing')
    results = search_movie_on_site(query)
    
    if not results:
        not_found_text = (
            "❌ দুঃখিত, কোনো মুভি পাওয়া যায়নি।\n"
            "❌ Sorry, no movie found.\n"
            "❌ क्षमा करें, कोई मूवी नहीं मिली।"
        )
        bot.reply_to(message, not_found_text)
        return

    # সর্বোচ্চ ৩টি প্রাসঙ্গিক রেজাল্ট স্টাইলিশভাবে পাঠানো
    for item in results[:3]:
        caption = (
            f"🎬 *{item['title']}*\n\n"
            f"✨ *Quality:* Full HD / HDRip\n"
            f"🍿 *Language:* Original / Multi-Audio\n"
            f"━━━━━━━━━━━━━━━━━━━"
        )
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("📥 ডাউনলোড ও দেখুন (Watch/Download)", url=item['link']))

        if item.get('image') and item['image'].startswith('http'):
            try:
                bot.send_photo(message.chat.id, item['image'], caption=caption, reply_markup=markup, parse_mode='Markdown')
                continue
            except Exception as e:
                print(f"Photo error: {e}")

        bot.send_message(message.chat.id, caption, reply_markup=markup, parse_mode='Markdown')

# স্বয়ংক্রিয় ব্যাকগ্রাউন্ড চেকার
def auto_check_new_movies():
    global last_seen_movie_link
    
    # প্রাথমিক সেটআপ
    try:
        initial = get_latest_movies_from_site()
        if initial:
            last_seen_movie_link = initial[0]['link']
    except Exception as e:
        print(f"Init tracker error: {e}")

    while True:
        try:
            movies = get_latest_movies_from_site()
            if movies and last_seen_movie_link:
                latest = movies[0]
                if latest['link'] != last_seen_movie_link:
                    last_seen_movie_link = latest['link']
                    
                    caption = (
                        f"🔥 *নতুন মুভি যুক্ত হয়েছে! (New Movie Alert)*\n\n"
                        f"🎬 *{latest['title']}*\n\n"
                        f"✨ নতুন প্রিন্ট সহ ওয়েবসাইটে যুক্ত হয়েছে!\n"
                        f"━━━━━━━━━━━━━━━━━━━"
                    )
                    markup = InlineKeyboardMarkup()
                    markup.add(InlineKeyboardButton("📥 এখনই দেখুন ও ডাউনলোড করুন", url=latest['link']))

                    if CHANNEL_OR_CHAT_ID and CHANNEL_OR_CHAT_ID != "YOUR_CHANNEL_ID_HERE":
                        if latest.get('image') and latest['image'].startswith('http'):
                            try:
                                bot.send_photo(CHANNEL_OR_CHAT_ID, latest['image'], caption=caption, reply_markup=markup, parse_mode='Markdown')
                            except Exception:
                                bot.send_message(CHANNEL_OR_CHAT_ID, caption, reply_markup=markup, parse_mode='Markdown')
                        else:
                            bot.send_message(CHANNEL_OR_CHAT_ID, caption, reply_markup=markup, parse_mode='Markdown')
        except Exception as e:
            print(f"Auto-checker error: {e}")
            
        time.sleep(300) # প্রতি ৫ মিনিটে চেক করবে

# Render-এর জন্য রুট
@app.route('/')
def index():
    return "Bot is actively running!", 200

# টেলিগ্রাম ওয়েবহুক
@app.route(f"/{BOT_TOKEN}", methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return "OK", 200
    return "Forbidden", 403

if __name__ == '__main__':
    # অটো চেকার থ্রেড ব্যাকগ্রাউন্ডে চালু করা
    thread = threading.Thread(target=auto_check_new_movies, daemon=True)
    thread.start()
    
    # Render Webhook সেটআপ
    render_url = os.getenv("RENDER_EXTERNAL_URL")
    if render_url:
        bot.remove_webhook()
        time.sleep(1)
        bot.set_webhook(url=f"{render_url.rstrip('/')}/{BOT_TOKEN}")
    
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
