#!/usr/bin/env python3
"""Step 2: AI Process articles"""
import sys
import urllib3
urllib3.disable_warnings()

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s', stream=sys.stdout)

from processor.ai_processor import process_all
count = process_all('db/news.db', batch_size=5)
print(f'PROCESS_DONE:{count}')