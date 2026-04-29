#!/usr/bin/env python3
"""Step 1: 采集新闻"""
import urllib3
urllib3.disable_warnings()
from collector.fetcher import collect_all
count = collect_all()
print(f'采集完成: {count} 篇新文章')
