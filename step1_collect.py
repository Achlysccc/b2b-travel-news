#!/usr/bin/env python3
"""Step 1: Collect articles"""
import sys
import urllib3
urllib3.disable_warnings()

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s', stream=sys.stdout)

from collector.fetcher import collect_all
count = collect_all()
print(f'COLLECT_DONE:{count}')