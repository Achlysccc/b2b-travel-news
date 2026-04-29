#!/usr/bin/env python3
"""Step 2: AI处理 - with logging"""
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
import urllib3
urllib3.disable_warnings()
from processor.ai_processor import process_all
count = process_all('db/news.db', batch_size=5)
print(f'AI处理完成: {count} 篇')
