#!/usr/bin/env python3
"""Step 3: Build static site"""
import sys
import urllib3
urllib3.disable_warnings()

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s', stream=sys.stdout)

from generator.site_builder import build_site
output = build_site(
    config_path='config/settings.yaml',
    db_path='db/news.db',
    output_path='output',
)
print(f'SITE_BUILT:{output}')