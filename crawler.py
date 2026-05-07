#!/usr/bin/env python3
"""RSS 爬虫 - 只抓真实新闻，无假数据"""
import feedparser, sqlite3, hashlib, os, sys, time, requests
from datetime import datetime, timedelta

DB_PATH = os.environ.get("DB_PATH", "db/news.db")

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS articles (
        id INTEGER PRIMARY KEY, title TEXT, link TEXT UNIQUE, summary_original TEXT,
        lang TEXT, region TEXT, region_label TEXT, region_flag TEXT, source_name TEXT,
        published_at TEXT, fetched_at TEXT, fingerprint TEXT, is_processed INTEGER DEFAULT 0,
        importance INTEGER DEFAULT 3)""")
    # 确保 importance 字段存在
    try:
        conn.execute("ALTER TABLE articles ADD COLUMN importance INTEGER DEFAULT 3")
        conn.commit()
    except:
        pass
    return conn

def fetch_feed(url, name, region='global', label='全球', flag='🌍'):
    """抓取单个 RSS 源，返回文章列表"""
    articles = []
    try:
        # 先尝试 requests 预抓（解决某些 RSS 需要 HTTP header 的问题）
        try:
            r = requests.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
            feed = feedparser.parse(r.text)
        except:
            feed = feedparser.parse(url)
        
        if not feed or not feed.entries:
            return []
    except Exception as e:
        return []
    
    for e in feed.entries[:20]:  # 最多取 20 条
        title = (e.get('title') or '').strip()[:500]
        link = (e.get('link') or '').strip()[:1000]
        if not title or not link:
            continue
        
        # 获取摘要
        summary = ''
        for field in ('summary', 'description', 'content'):
            if field in e:
                val = e.get(field)
                if isinstance(val, list) and val:
                    val = val[0].get('value', '')
                summary = (val or '')[:2000]
                break
        
        # 解析发布时间
        published = ''
        for field in ('published_parsed', 'updated_parsed'):
            if field in e and e[field]:
                try:
                    published = datetime(*e[field][:6]).strftime('%Y-%m-%d %H:%M:%S')
                    break
                except:
                    pass
        
        if not published:
            published = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        articles.append({
            'title': title,
            'link': link,
            'summary': summary,
            'published_at': published,
            'source': name,
            'region': region,
            'label': label,
            'flag': flag,
        })
    
    return articles

def save_articles(conn, articles):
    """保存文章到数据库"""
    cursor = conn.cursor()
    now = datetime.now()
    count = 0
    
    for a in articles:
        fp = hashlib.md5(f"{a['title']}{a['link']}".encode()).hexdigest()
        try:
            cursor.execute("""INSERT OR IGNORE INTO articles 
                (title, link, summary_original, lang, region, region_label, region_flag,
                 source_name, published_at, fetched_at, fingerprint, is_processed, importance)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,1,3)""",
                (a['title'], a['link'], a['summary'], 'en', a['region'], a['label'],
                 a['flag'], a['source'], a['published_at'], now.isoformat(), fp))
            if cursor.rowcount > 0:
                count += 1
        except Exception as e:
            pass
    conn.commit()
    return count

# RSS 源配置（酒店/旅游/B2B 行业）
RSS_SOURCES = [
    # 全球酒店业
    ("https://www.hospitalitynet.org/rss/news.xml", "Hospitality Net", "global", "全球", "🌍"),
    ("https://skift.com/feed/", "Skift", "global", "全球", "🌍"),
    ("https://hotelnewsnow.com/rss", "Hotel News Now", "global", "全球", "🌍"),
    ("https://www.phocuswire.com/rss", "PhocusWire", "global", "全球", "🌍"),
    # 航空
    ("https://www.flightglobal.com/feeds/rss", "FlightGlobal", "global", "全球", "🌍"),
    ("https://www.tnooz.com/feed/", "Tnooz", "global", "全球", "🌍"),
    # 旅游商业
    ("https://www.travelweekly.com/rss/all-articles", "Travel Weekly", "global", "全球", "🌍"),
    # 经济/商业
    ("https://www.businesstraveller.com/feed/", "Business Traveller", "global", "全球", "🌍"),
    ("https://www.mckinsey.com/industries/travel-logistics-and-transport/overview/rss", "McKinsey Travel", "global", "全球", "🌍"),
    # 差旅/商旅
    ("https://www.globalbusinesstravel.com/news/rss", "GBTA", "global", "全球", "🌍"),
]

if __name__ == "__main__":
    print("🚀 B2B 旅游分销 - 数据采集")
    now = datetime.now()
    print(f"📅 时间：{now.strftime('%Y-%m-%d %H:%M:%S')}")
    
    conn = init_db()
    
    # 清理超旧数据（90天以前）
    cutoff = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d %H:%M:%S')
    cur = conn.cursor()
    cur.execute("DELETE FROM articles WHERE published_at < ?", (cutoff,))
    print(f"🗑️ 清理过期数据：{cur.rowcount} 条")
    conn.commit()
    
    total_new = 0
    total_sources = 0
    
    for url, name, region, label, flag in RSS_SOURCES:
        print(f"\n📡 {name}...", end=" ", flush=True)
        try:
            articles = fetch_feed(url, name, region, label, flag)
            if articles:
                n = save_articles(conn, articles)
                print(f"✅ {len(articles)}条 / 新增{n}条")
                total_new += n
                total_sources += 1
            else:
                print("⚠️ 无内容")
        except Exception as e:
            print(f"❌ 错误: {e}")
        time.sleep(1)  # 礼貌延迟
    
    # 统计
    cur.execute("SELECT COUNT(*) FROM articles")
    total_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM articles WHERE datetime(published_at) >= datetime('now', '-48 hours')")
    recent = cur.fetchone()[0]
    
    conn.close()
    
    print(f"\n✅ 完成！新增 {total_new} 条 | 数据库共 {total_count} 条（48h内 {recent} 条）| 成功来源 {total_sources}/{len(RSS_SOURCES)}")