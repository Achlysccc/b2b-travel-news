#!/usr/bin/env python3
"""RSS 爬虫 - 采集 B2B 旅游分销行业新闻"""
import feedparser, sqlite3, hashlib, os, sys
from datetime import datetime

DB_PATH = os.environ.get("DB_PATH", "db/news.db")

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS articles (
        id INTEGER PRIMARY KEY, title TEXT, link TEXT UNIQUE, summary_original TEXT,
        lang TEXT, region TEXT, region_label TEXT, region_flag TEXT, source_name TEXT,
        published_at TEXT, fetched_at TEXT, fingerprint TEXT, is_processed INTEGER DEFAULT 0)""")
    conn.commit()
    return conn

def fetch_feed(conn, url, name, region='global', label='全球', flag='🌍'):
    try:
        feed = feedparser.parse(url)
    except Exception as e:
        print(f"Error fetching {url}: {e}", file=sys.stderr)
        return 0
    cursor = conn.cursor()
    count = 0
    for e in feed.entries[:20]:
        title, link = e.get('title','')[:500], e.get('link','')[:1000]
        summary = e.get('summary', e.get('description', ''))[:2000]
        published = e.get('published', '')[:20]
        if not title or not link: continue
        fp = hashlib.md5(f"{title}{link}{published}".encode()).hexdigest()
        try:
            cursor.execute("INSERT OR IGNORE INTO articles (title,link,summary_original,lang,region,region_label,region_flag,source_name,published_at,fetched_at,fingerprint,is_processed) VALUES (?,?,?,?,?,?,?,?,?,?,?,0)",
                (title, link, summary, 'en', region, label, flag, name, published, datetime.now().isoformat(), fp))
            if cursor.rowcount > 0: count += 1
        except Exception as e:
            if "UNIQUE" not in str(e): print(f"DB error: {e}", file=sys.stderr)
    conn.commit()
    return count

if __name__ == "__main__":
    print("🚀 Crawling RSS feeds...")
    conn = init_db()
    sources = [
        ("https://www.hospitalitynet.org/rss/news.xml", "Hospitality Net"),
        ("https://skift.com/feed/", "Skift"),
        ("https://www.phocuswire.com/feed", "PhocusWire"),
    ]
    total = 0
    for url, name in sources:
        c = fetch_feed(conn, url, name)
        total += c
        print(f"  {name}: {c} new")
    conn.close()
    print(f"✅ Done: {total} total")
