#!/usr/bin/env python3
import sys
print("Python:", sys.version)
for p in sys.path:
    print(" ", p)
try:
    import feedparser
    print("feedparser: OK")
except ImportError as e:
    print("feedparser: MISSING -", e)