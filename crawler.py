#!/usr/bin/env python3
"""RSS 爬虫 - 采集 B2B 旅游分销行业新闻（增强版）"""
import feedparser, sqlite3, hashlib, os, sys, time
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
        if not feed or not feed.entries:
            print(f"  ⚠️  {name}: 无内容", file=sys.stderr)
            return 0
    except Exception as e:
        print(f"  ❌ {name}: {e}", file=sys.stderr)
        return 0
    
    cursor = conn.cursor()
    count = 0
    for e in feed.entries[:30]:  # 每个源最多抓 30 条
        title = e.get('title', '')[:500]
        link = e.get('link', '')[:1000]
        summary = e.get('summary', e.get('description', ''))[:2000]
        published = e.get('published', e.get('published_parsed', ''))
        if published:
            try:
                published = time.strftime('%Y-%m-%d', published) if isinstance(published, time.struct_time) else str(published)[:20]
            except:
                published = ''
        else:
            published = ''
        
        if not title or not link:
            continue
        
        # 生成指纹
        fp = hashlib.md5(f"{title}{link}{published}".encode()).hexdigest()
        
        try:
            cursor.execute("""INSERT OR IGNORE INTO articles 
                (title,link,summary_original,lang,region,region_label,region_flag,
                 source_name,published_at,fetched_at,fingerprint,is_processed) 
                VALUES (?,?,?,?,?,?,?,?,?,?,?,0)""",
                (title, link, summary, 'en', region, label, flag, name, published, 
                 datetime.now().isoformat(), fp))
            if cursor.rowcount > 0:
                count += 1
        except Exception as e:
            if "UNIQUE" not in str(e):
                print(f"  DB error: {e}", file=sys.stderr)
    
    conn.commit()
    return count

if __name__ == "__main__":
    print("🚀 B2B 旅游分销 - RSS 爬虫")
    print(f"📅 时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    conn = init_db()
    
    # 多个可靠的 RSS 源
    sources = [
        # 综合旅游
        ("https://www.hospitalitynet.org/rss/news.xml", "Hospitality Net"),
        ("https://skift.com/feed/", "Skift"),
        ("https://www.phocuswire.com/feed", "PhocusWire"),
        # 酒店
        ("https://www.hotelierglobal.com/rss/news.xml", "Hotelier Global"),
        ("https://hotelnewsresource.com/feed/", "Hotel News Resource"),
        # 航空
        ("https://www.flightglobal.com/rss", "FlightGlobal"),
        # 技术
        ("https://www.tnooz.com/feed/", "Tnooz"),
    ]
    
    total = 0
    success_count = 0
    for url, name in sources:
        print(f"\n📡 {name}...")
        try:
            c = fetch_feed(conn, url, name)
            total += c
            if c > 0:
                success_count += 1
                print(f"  ✅ 新增 {c} 条")
            else:
                print(f"  ⚠️  无新内容")
        except Exception as e:
            print(f"  ❌ 错误：{e}")
        
        # 礼貌延迟
        time.sleep(1)
    
    conn.close()
    print(f"\n✅ 完成！共 {success_count}/{len(sources)} 个源成功，总计 {total} 条新闻")
