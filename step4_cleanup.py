#!/usr/bin/env python3
"""Step 4: Cleanup + stats"""
import sys
import urllib3
urllib3.disable_warnings()

from db.database import get_db
from datetime import datetime, timedelta

conn = get_db('db/news.db')

cutoff = (datetime.now() - timedelta(days=90)).isoformat()
r = conn.execute('DELETE FROM articles WHERE published_at < ?', (cutoff,))
conn.commit()
print(f'已清理 {r.rowcount} 条过期数据')

total = conn.execute('SELECT COUNT(*) as c FROM articles').fetchone()['c']
processed = conn.execute('SELECT COUNT(*) as c FROM articles a JOIN summaries s ON a.id=s.article_id').fetchone()['c']
new_today = conn.execute("SELECT COUNT(*) as c FROM articles WHERE date(fetched_at) = date('now')").fetchone()['c']
print(f'数据库文章总数: {total}')
print(f'已处理文章数: {processed}')
print(f'今日新增: {new_today}')
conn.close()
print('CLEANUP_DONE')