#!/usr/bin/env python3
"""快速构建 - 直接从 articles 表读取，不需要 summaries 表"""
import sqlite3, os
from datetime import datetime

# 构建网站
os.system("cd /home/user/workspace/b2b-hotel-news && python3 -c 'from generator.site_builder import build_site; build_site()'")

# 检查数据库
conn = sqlite3.connect('db/news.db')
count = conn.execute('SELECT COUNT(*) FROM articles').fetchone()[0]
print(f"数据库内容：{count} 条")
if count == 0:
    print("⚠️ 数据库为空！")
conn.close()
