import sys, os
sys.path.insert(0, '/home/user/workspace/b2b-hotel-news/.venv/lib/python3.11/site-packages')
os.environ['PYTHONPATH'] = '/home/user/workspace/b2b-hotel-news/.venv/lib/python3.11/site-packages'
import feedparser
print("feedparser OK:", feedparser.__version__)