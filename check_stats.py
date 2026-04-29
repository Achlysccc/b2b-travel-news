import urllib3
urllib3.disable_warnings()
from db.database import get_db

conn = get_db('db/news.db')
total = conn.execute('SELECT COUNT(*) as c FROM articles').fetchone()['c']
processed = conn.execute('SELECT COUNT(*) as c FROM summaries').fetchone()['c']
new_articles = conn.execute("SELECT COUNT(*) as c FROM articles WHERE date(fetched_at) = date('now')").fetchone()['c']
print(f'Total articles in DB: {total}')
print(f'Processed (with summaries): {processed}')
print(f'Unprocessed: {total - processed}')
print(f'Articles fetched today: {new_articles}')

# Check if site was generated
import os
output_files = []
if os.path.exists('output'):
    for root, dirs, files in os.walk('output'):
        for f in files:
            if f.endswith('.html'):
                output_files.append(os.path.join(root, f))
print(f'HTML files in output/: {len(output_files)}')
if os.path.exists('output/index.html'):
    mtime = os.path.getmtime('output/index.html')
    from datetime import datetime
    print(f'index.html modified: {datetime.fromtimestamp(mtime)}')

conn.close()