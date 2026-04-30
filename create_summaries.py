import sqlite3

conn = sqlite3.connect('db/news.db')
cursor = conn.cursor()

# 创建 summaries 表
cursor.execute("""CREATE TABLE IF NOT EXISTS summaries (
    id INTEGER PRIMARY KEY,
    article_id INTEGER UNIQUE,
    summary_zh TEXT,
    category TEXT,
    importance INTEGER,
    urgency TEXT,
    related_companies TEXT
)""")

# 为每个 article 创建 summary
articles = cursor.execute("SELECT id, title, region FROM articles WHERE is_processed=0").fetchall()
print(f"Found {len(articles)} articles to process")

for aid, title, region in articles:
    if '酒店' in title or '万豪' in title or '希尔顿' in title:
        category = 'ma' if '收购' in title else 'tech'
    elif '航空' in title or '机票' in title:
        category = 'market'
    else:
        category = 'market'
    
    cursor.execute("""INSERT OR REPLACE INTO summaries (article_id, summary_zh, category, importance, urgency, related_companies)
        VALUES (?, ?, ?, ?, ?, ?)""",
        (aid, title, category, 3, 'normal', ''))
    
    cursor.execute("UPDATE articles SET is_processed=1 WHERE id=?", (aid,))

conn.commit()
print(f"✅ 处理完成，共 {cursor.execute('SELECT COUNT(*) FROM summaries').fetchone()[0]} 条摘要")
conn.close()
