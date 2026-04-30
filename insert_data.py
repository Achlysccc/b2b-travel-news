import sqlite3, hashlib
from datetime import datetime

conn = sqlite3.connect('db/news.db')
cursor = conn.cursor()

cursor.execute("""CREATE TABLE IF NOT EXISTS articles (
    id INTEGER PRIMARY KEY, title TEXT, link TEXT UNIQUE, summary_original TEXT,
    lang TEXT, region TEXT, region_label TEXT, region_flag TEXT, source_name TEXT,
    published_at TEXT, fetched_at TEXT, fingerprint TEXT, is_processed INTEGER DEFAULT 0)""")

tests = [
    ("万豪宣布 2026 亚洲新开 50 家酒店", "https://ex.com/m1", "万豪国际宣布 2026 年亚洲扩张计划", "global", "全球", "🌍", "Test"),
    ("希尔顿推商务套餐", "https://ex.com/m2", "希尔顿推出全新商务旅行套餐", "north-america", "北美", "🇺🇸", "Test"),
    ("Airbnb Q1 营收 +18%", "https://ex.com/m3", "Airbnb 公布 Q1 财报", "north-america", "北美", "🇺🇸", "Test"),
    ("五 一旅游预订创新高", "https://ex.com/m4", "中国文旅部数据", "china", "中国", "🇨🇳", "Test"),
    ("日本放宽签证", "https://ex.com/m5", "日本简化东南亚签证", "japan", "日本", "🇯🇵", "Test"),
]

now = datetime.now()
for title, link, summary, region, label, flag, source in tests:
    fp = hashlib.md5(f"{title}{link}".encode()).hexdigest()
    try:
        cursor.execute("INSERT OR REPLACE INTO articles (title,link,summary_original,lang,region,region_label,region_flag,source_name,published_at,fetched_at,fingerprint,is_processed) VALUES (?,?,?,?,?,?,?,?,?,?,?,0)",
            (title, link, summary, 'zh', region, label, flag, source, now.strftime('%Y-%m-%d'), now.isoformat(), fp))
    except: pass

conn.commit()
print(f"✅ 插入完成，共 {cursor.execute('SELECT COUNT(*) FROM articles').fetchone()[0]} 条")
conn.close()
