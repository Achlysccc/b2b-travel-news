#!/usr/bin/env python3
"""RSS 爬虫 - 采集 B2B 旅游分销行业新闻
只包含经过验证可访问的 RSS 源，降低超时避免卡死。
"""
import feedparser, sqlite3, hashlib, os, sys, time, time as time_module
import requests
from datetime import datetime, timezone, timedelta

DB_PATH = os.environ.get("DB_PATH", "db/news.db")

# 验证可访问的 RSS 源 (2026-05 测试)
VERIFIED_SOURCES = [
    # (url, name, region_key, label, flag, lang)
    ("https://skift.com/feed/", "Skift", "north-america", "北美", "🇺🇸", "en"),
    ("https://www.businesstraveller.com/feed/", "Business Traveller UK", "uk-ireland", "英国 & 爱尔兰", "🇬🇧", "en"),
    ("https://www.lodgingmagazine.com/feed/", "LODGING", "north-america", "北美", "🇺🇸", "en"),
    ("https://hotelanalyst.co.uk/feed/", "Hotel Analyst", "uk-ireland", "英国 & 爱尔兰", "🇬🇧", "en"),
    ("https://sleepermagazine.com/feed/", "Sleeper Magazine", "uk-ireland", "英国 & 爱尔兰", "🇬🇧", "en"),
    ("https://www.travelweekly.com.au/rss/Latest-News", "Travel Weekly ANZ", "oceania", "大洋洲", "🇦🇺", "en"),
    ("https://www.asianhospitality.com/feed/", "Asian Hospitality", "southeast-asia", "东南亚", "🇸🇬", "en"),
    ("https://www.reportur.com/feed/", "Reportur", "latam", "拉美", "🇲🇽", "es"),
    ("https://www.ttgmice.com/feed/", "TTG Mice", "southeast-asia", "东南亚", "🇸🇬", "en"),
    ("https://www.pinchain.com/feed", "品橙旅游", "china", "中国", "🇨🇳", "zh"),
]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/rss+xml, application/xml, text/xml, */*',
}

# 全局时间戳：脚本开始时间，所有文章 published_at 用这个，避免每条时间不一致
SCRIPT_START = datetime.now(timezone.utc)


def parse_feed_time(entry) -> str:
    """从 feedparser entry 提取可靠的时间戳，优先级：published_parsed > updated_parsed > now"""
    # published_parsed 是 time.struct_time (UTC)，最可靠
    if hasattr(entry, 'published_parsed') and entry.published_parsed:
        return time_module.strftime('%Y-%m-%dT%H:%M:%S+00:00', entry.published_parsed)
    if hasattr(entry, 'updated_parsed') and entry.updated_parsed:
        return time_module.strftime('%Y-%m-%dT%H:%M:%S+00:00', entry.updated_parsed)
    # fallback：用脚本启动时间
    return SCRIPT_START.strftime('%Y-%m-%dT%H:%M:%S+00:00')


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS articles (
        id INTEGER PRIMARY KEY, title TEXT, link TEXT UNIQUE, summary_original TEXT,
        lang TEXT, region TEXT, region_label TEXT, region_flag TEXT, source_name TEXT,
        published_at TEXT, fetched_at TEXT, fingerprint TEXT, is_processed INTEGER DEFAULT 0)""")
    conn.commit()
    return conn


def fetch_feed(conn, url, name, region, label, flag, lang, timeout=8):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout, verify=False)
        if resp.status_code != 200:
            print(f"  ⚠️  {name}: HTTP {resp.status_code}")
            return 0
        feed = feedparser.parse(resp.content)
    except Exception as e:
        print(f"  ⚠️  {name}: {e}")
        return 0

    cursor = conn.cursor()
    count = 0
    fetched_at = datetime.now(timezone(timedelta(hours=8))).isoformat()

    for e in feed.entries[:20]:
        title = (e.get('title', '') or '')[:500]
        link = (e.get('link', '') or '')[:1000]
        summary = (e.get('summary', e.get('description', '')) or '')[:2000]
        published_at = parse_feed_time(e)

        if not title or not link:
            continue

        fp = hashlib.md5(f"{title}{link}".encode()).hexdigest()

        try:
            cursor.execute("""INSERT OR IGNORE INTO articles
                (title,link,summary_original,lang,region,region_label,region_flag,
                 source_name,published_at,fetched_at,fingerprint,is_processed)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,0)""",
                (title, link, summary, lang, region, label, flag, name, published_at, fetched_at, fp))
            if cursor.rowcount > 0:
                count += 1
        except Exception as ex:
            if "UNIQUE" not in str(ex):
                print(f"DB error: {ex}", file=sys.stderr)

    conn.commit()
    return count


def main():
    print("🚀 B2B 旅游分销 - 数据采集")
    print(f"📅 时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    conn = init_db()
    total_new = 0
    success = 0

    for url, name, region, label, flag, lang in VERIFIED_SOURCES:
        c = fetch_feed(conn, url, name, region, label, flag, lang, timeout=8)
        total_new += c
        if c > 0:
            success += 1
            print(f"  📡 {name}... ✅ {c}条新增")
        else:
            print(f"  📡 {name}... ⚠️ 无内容")
        time.sleep(0.5)

    conn.close()
    print(f"")
    print(f"✅ 完成！新增 {total_new} 条 | 成功来源 {success}/{len(VERIFIED_SOURCES)}")

if __name__ == "__main__":
    main()
