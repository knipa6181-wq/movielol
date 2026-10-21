def get_latest_movies_from_site():
    movies = []
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(SITE_URL, headers=headers, timeout=20)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            # মুভির পোস্টার ও কার্ড সাধারণত <a> ট্যাগের ভেতরে থাকে
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
                                'title': title,
                                'link': full_link,
                                'image': img_url
                            })
    except Exception as e:
        print(f"Error fetching latest movies: {e}")
    return movies

def search_movie_on_site(query):
    results = []
    try:
        search_url = f"{SITE_URL}/?s={requests.utils.quote(query)}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(search_url, headers=headers, timeout=20)
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
                                'title': title,
                                'link': full_link,
                                'image': img_url
                            })
    except Exception as e:
        print(f"Search error: {e}")
    return results
