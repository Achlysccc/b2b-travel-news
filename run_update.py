#!/usr/bin/env python3
import urllib3
urllib3.disable_warnings()

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

from collector.fetcher import collect_all
count = collect_all()
print(f'采集完成: {count} 篇新文章')