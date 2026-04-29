#!/usr/bin/env python3
import urllib3
urllib3.disable_warnings()
from db.database import get_db

conn = get_db('db/news.db')
total = conn.execute('SELECT COUNT(*) as c FROM articles').fetchone()['c']
processed = conn.execute('SELECT COUNT(*) as c FROM summaries').fetchone()['c']
unprocessed = total - processed
print(f'Total articles: {total}')
print(f'Processed: {processed}')
print(f'Unprocessed: {unprocessed}')
conn.close()