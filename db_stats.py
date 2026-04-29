#!/usr/bin/env python3
"""DB stats"""
from db.database import get_db
conn = get_db('db/news.db')
total = conn.execute('SELECT COUNT(*) FROM articles').fetchone()[0]
today = conn.execute("SELECT COUNT(*) FROM articles WHERE date(published_at) = date('now')").fetchone()[0]
processed = conn.execute('SELECT COUNT(*) FROM articles WHERE id IN (SELECT article_id FROM summaries)').fetchone()[0]
print(f'数据库总文章数: {total}')
print(f'今日新增: {today}')
print(f'已处理: {processed}')
conn.close()
