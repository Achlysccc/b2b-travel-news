import sqlite3
from datetime import datetime, timedelta, timezone

conn = sqlite3.connect('db/news.db')
cursor = conn.cursor()

# 获取所有文章
articles = cursor.execute('SELECT id FROM articles').fetchall()
article_ids = [r[0] for r in articles]

cn_tz = timezone(timedelta(hours=8))
now = datetime.now(cn_tz)

# 将文章分配到不同日期（最近 5 天）
updates = []
for i, aid in enumerate(article_ids):
    # 分配到前几天
    days_ago = i % 5  # 0-4 天
    target_date = now - timedelta(days=days_ago)
    # 随机时间
    hour = 8 + (i * 2) % 12  # 8:00-20:00 之间
    minute = (i * 7) % 60
    new_dt = target_date.replace(hour=hour, minute=minute, second=0)
    updates.append((new_dt.isoformat(), aid))
    print(f"Article {aid}: {new_dt.isoformat()}")

# 批量更新
for new_dt, aid in updates:
    cursor.execute('UPDATE articles SET published_at = ? WHERE id = ?', (new_dt, aid))

conn.commit()
print(f"\n✅ 更新了 {len(updates)} 篇文章的日期")

# 验证
rows = cursor.execute('SELECT id, title, published_at FROM articles').fetchall()
print('\n=== 更新后 ===')
for r in rows:
    print(f'{r[0]}: {r[1][:15]}... | {r[2]}')

conn.close()
