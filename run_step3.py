#!/usr/bin/env python3
import urllib3
urllib3.disable_warnings()
from generator.site_builder import build_site

output = build_site(
    config_path='config/settings.yaml',
    db_path='db/news.db',
    output_path='output',
)
print(f'站点已生成: {output}')