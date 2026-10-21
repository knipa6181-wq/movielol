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

# ডেটাবেস/ফাইল হ্যান্ডলিং
USERS_FILE = "subscribers.txt"
SEEN_MOVIES_FILE = "seen_movies.txt"

def load_subscribers():
    if not os.path.exists(USERS_FILE):
        return set()
    with open(USERS_FILE, "r") as f:
        return set(line.strip() for line in f if line.strip())

def save_subscriber(chat_id):
    subscribers = load_subscribers()
    if str(chat_id) not in subscribers:
        with open(USERS_FILE, "a") as f:
            f.write(f"{chat_id}\n")

def load_seen_movies():
    if not os.path.exists(SEEN_MOVIES_FILE):
        return set()
    with open(SEEN_MOVIES_FILE, "r") as f:
        return set(line.strip() for line in f if line.strip())

def save_seen_movies(links):
    with open(SEEN_MOVIES_FILE, "a") as f:
        for link in links:
            f.write(f"{link}\n")

def clean_movie_title(text):
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
        print(f"Error fetching movies: {e}")
    return movies

def search_movie_on_site(query):
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

                        # শুধুমাত্র সার্চের নামের সাথে মিল থাকলে যুক্ত হবে
                        if any(w in cleaned_title or w in cleaned_url for w in query_words):
                            if not any(r['link'] == full_link for r in results):
                                results.append({
                                    'title': raw_title.strip(),
                                    'link': full_link,
                                    'image': img_url
                                })
    except Exception as e:
        print(f"Search error: {e}")
    return results

# ৩ ভাষার স্বাগতম বার্তা এবং ইউজার আইডি সেভ
@bot.message_handler(commands=['start'])
def send_welcome(message):
    save_subscriber(message.chat.id)
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
    save_subscriber(message.chat.id)
    query = message.text.strip()
    if query.startswith('/'):
        return

    bot.send_chat_action(message.chat.id, 'typing')
    results = search_movie_on_site(query)
    
    if not results:
        not_found_text = (
            "❌ দুঃখিত, এই নামের কোনো মুভি পাওয়া যায়নি।\n"
            "❌ Sorry, no matching movie found.\n"
            "❌ क्षमा करें, कोई संबंधित मूवी नहीं मिली।"
        )
        bot.reply_to(message, not_found_text)
        return

    for item in results[:3]:
        caption = (
            f"🎬 *{item['title']}*\n\n"
            f"✨ *Quality:* Full HD / WEB-DL\n"
            f"🍿 *Language:* Original / Dubbed\n"
            f"━━━━━━━━━━━━━━━━━━━"
        )
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("📥 ডাউনলোড ও দেখুন (Watch/Download)", url=item['link']))

        if item.get('image') and item['image'].startswith('http'):
            try:
                bot.send_photo(message.chat.id, item['image'], caption=caption, reply_markup=markup, parse_mode='Markdown')
                continue
            except Exception:
                pass
        bot.send_message(message.chat.id, caption, reply_markup=markup, parse_mode='Markdown')

# প্রতিটি সাবস্ক্রাইবার ও চ্যানেলে মেসেজ ব্রডকাস্ট
def broadcast_movie(movie):
    caption = (
        f"🔥 *নতুন মুভি আপলোড হয়েছে!*\n\n"
        f"🎬 *{movie['title']}*\n\n"
        f"✨ এখনই ওয়েবসাইটে গিয়ে সরাসরি দেখুন বা ডাউনলোড করুন!\n"
        f"━━━━━━━━━━━━━━━━━━━"
    )
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("📥 ডাউনলোড লিংক", url=movie['link']))

    targets = list(load_subscribers())
    if CHANNEL_OR_CHAT_ID:
        targets.append(CHANNEL_OR_CHAT_ID)

    for target in targets:
        try:
            if movie.get('image') and movie['image'].startswith('http'):
                bot.send_photo(target, movie['image'], caption=caption, reply_markup=markup, parse_mode='Markdown')
            else:
                bot.send_message(target, caption, reply_markup=markup, parse_mode='Markdown')
            time.sleep(0.1) # টেলিগ্রাম রেট লিমিট এড়াতে সামান্য বিরতি
        except Exception as e:
            print(f"Broadcast failed to {target}: {e}")

# স্বয়ংক্রিয় ব্যাকগ্রাউন্ড ট্র্যাকার
def auto_check_new_movies():
    # প্রথমবার বটের মেমোরিতে থাকা পুরনো মুভিগুলো রেকর্ড করা (যাতে স্টার্ট দিলে সব না আসে)
    seen_links = load_seen_movies()
    if not seen_links:
        current_site_movies = get_latest_movies_from_site()
        initial_links = [m['link'] for m in current_site_movies]
        save_seen_movies(initial_links)
        seen_links = set(initial_links)

    while True:
        try:
            current_movies = get_latest_movies_from_site()
            new_movies = [m for m in current_movies if m['link'] not in seen_links]

            # নতুন মুভি পাওয়া গেলে সবচেয়ে পুরনো থেকে শুরু করে নতুন পর্যন্ত পোস্ট করা
            for movie in reversed(new_movies):
                broadcast_movie(movie)
                seen_links.add(movie['link'])
                save_seen_movies([movie['link']])
                time.sleep(1)

        except Exception as e:
            print(f"Auto-checker loop error: {e}")

        time.sleep(120)  # প্রতি ২ মিনিট পরপর সাইট চেক করবে

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
    thread = threading.Thread(target=auto_check_new_movies, daemon=True)
    thread.start()

    render_url = os.getenv("RENDER_EXTERNAL_URL")
    if render_url:
        bot.remove_webhook()
        time.sleep(1)
        bot.set_webhook(url=f"{render_url.rstrip('/')}/{BOT_TOKEN}")

    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
