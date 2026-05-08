#!/usr/bin/env python3
import sys
print("Python:", sys.version)

try:
    import feedparser
    print("feedparser: OK")
except ImportError as e:
    print("feedparser: MISSING -", e)

try:
    import requests
    print("requests: OK")
except ImportError as e:
    print("requests: MISSING -", e)

try:
    import sqlite3
    print("sqlite3: OK")
except ImportError as e:
    print("sqlite3: MISSING -", e)

try:
    import jinja2
    print("jinja2: OK")
except ImportError as e:
    print("jinja2: MISSING -", e)

# Check db
import sqlite3
conn = sqlite3.connect('/home/user/workspace/b2b-hotel-news/db/news.db')
c = conn.execute("SELECT COUNT(*) FROM articles")
print("DB articles:", c.fetchone()[0])
c = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
print("Tables:", [r[0] for r in c.fetchall()])
conn.close()