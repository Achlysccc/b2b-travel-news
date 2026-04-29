#!/usr/bin/env python3
import urllib3
urllib3.disable_warnings()
from processor.ai_processor import process_all
count = process_all('db/news.db', batch_size=5)
print(f'AI处理完成: {count} 篇')