#!/usr/bin/env python3
"""RSS 爬虫 - 简化版"""
import feedparser, sqlite3, hashlib, os
from datetime import datetime

DB_PATH = "db/news.db"

def init_db():
    os.makedirs("db", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS articles (
        id INTEGER PRIMARY KEY, title TEXT, link TEXT UNIQUE, summary_original TEXT,
        lang TEXT, region TEXT, region_label TEXT, region_flag TEXT, source_name TEXT,
        published_at TEXT, fetched_at TEXT, fingerprint TEXT)""")
    conn.commit()
    return conn

def fetch_feed(conn, url, name, region='global', label='全球', flag='🌍'):
    try:
        feed = feedparser.parse(url)
    except: return 0
    cursor = conn.cursor()
    count = 0
    for e in feed.entries[:20]:
        title, link = e.get('title','')[:500], e.get('link','')[:1000]
        summary = e.get('summary', e.get('description', ''))[:2000]
        published = e.get('published', '')[:20]
        if not title or not link: continue
        fp = hashlib.md5(f"{title}{link}{published}".encode()).hexdigest()
        try:
            cursor.execute("INSERT OR IGNORE INTO articles (title,link,summary_original,lang,region,region_label,region_flag,source_name,published_at,fetched_at,fingerprint) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (title, link, summary, 'en', region, label, flag, name, published, datetime.now().isoformat(), fp))
            if cursor.rowcount > 0: count += 1
        except: pass
    conn.commit()
    return count

if __name__ == "__main__":
    print("🚀 Crawling...")
    conn = init_db()
    sources = [
        ("https://www.hospitalitynet.org/rss/news.xml", "Hospitality Net"),
        ("https://skift.com/feed/", "Skift"),
    ]
    total = 0
    for url, name in sources:
        c = fetch_feed(conn, url, name)
        total += c
        print(f"  {name}: {c}")
    conn.close()
    print(f"✅ Done: {total}")
