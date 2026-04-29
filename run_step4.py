#!/usr/bin/env python3
from db.database import get_db
from datetime import datetime, timedelta

conn = get_db('db/news.db')
cutoff = (datetime.now() - timedelta(days=90)).isoformat()
r = conn.execute('DELETE FROM articles WHERE published_at < ?', (cutoff,))
conn.commit()
print(f'已清理 {r.rowcount} 条过期数据')
conn.close()