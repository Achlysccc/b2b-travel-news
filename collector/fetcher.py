"""数据采集模块 - RSS 抓取 + 网页抓取"""

import time
import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import feedparser
import requests
from bs4 import BeautifulSoup

from db.database import get_db, upsert_source, insert_article, update_source_status

log = logging.getLogger(__name__)

# 只抓最近 24 小时的文章
MAX_AGE_HOURS = 24
REQUEST_TIMEOUT = 15  # 缩短超时
REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# 配置 requests session
_session = requests.Session()
_session.headers.update(REQUEST_HEADERS)
_adapter = requests.adapters.HTTPAdapter(max_retries=1, pool_maxsize=10)
_session.mount("http://", _adapter)
_session.mount("https://", _adapter)


def load_sources(config_path: str) -> dict:
    """加载 sources.yaml"""
    import yaml
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def parse_published_time(entry) -> str | None:
    """从 RSS entry 解析发布时间"""
    for field in ["published_parsed", "updated_parsed"]:
        t = entry.get(field)
        if t:
            try:
                dt = datetime(*t[:6], tzinfo=timezone.utc)
                return dt.isoformat()
            except Exception:
                continue
    for field in ["published", "updated"]:
        val = entry.get(field)
        if val:
            return val
    return None


def is_within_window(published_at: str | None) -> bool:
    if not published_at:
        return True
    try:
        from dateutil import parser as dtparser
        dt = dtparser.parse(published_at)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        return (now - dt) < timedelta(hours=MAX_AGE_HOURS)
    except Exception:
        return True


def _fetch_url_content(url: str) -> str | None:
    """用 requests 获取 URL 内容"""
    try:
        resp = _session.get(url, timeout=REQUEST_TIMEOUT, verify=True)
        resp.raise_for_status()
        return resp.text
    except requests.exceptions.SSLError:
        try:
            resp = _session.get(url, timeout=REQUEST_TIMEOUT, verify=False)
            resp.raise_for_status()
            return resp.text
        except Exception:
            return None
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
        return None
    except Exception:
        return None


def fetch_rss(source: dict) -> list[dict]:
    """抓取单个 RSS 源"""
    articles = []
    try:
        content = _fetch_url_content(source["url"])
        if content:
            feed = feedparser.parse(content)
        else:
            feed = feedparser.parse(source["url"], request_headers=REQUEST_HEADERS)

        if not feed.entries:
            return articles

        for entry in feed.entries[:30]:
            title = entry.get("title", "").strip()
            link = entry.get("link", "").strip()
            if not title or not link:
                continue

            summary = ""
            for field in ["summary", "description"]:
                if entry.get(field):
                    soup = BeautifulSoup(entry.get(field), "html.parser")
                    summary = soup.get_text(separator=" ", strip=True)[:500]
                    if summary:
                        break

            published_at = parse_published_time(entry)

            if not is_within_window(published_at):
                continue

            articles.append({
                "title": title,
                "link": link,
                "summary_original": summary,
                "published_at": published_at,
            })

    except Exception as e:
        log.error(f"Error fetching RSS {source['name']}: {e}")

    return articles


def fetch_page(source: dict) -> list[dict]:
    """网页抓取"""
    articles = []
    content = _fetch_url_content(source["url"])
    if not content:
        return articles

    try:
        soup = BeautifulSoup(content, "html.parser")
        seen_links = set()

        for tag in soup.find_all(["a", "h2", "h3"]):
            link_tag = tag if tag.name == "a" else tag.find("a")
            if not link_tag or not link_tag.get("href"):
                continue
            href = link_tag["href"]
            if not href.startswith("http"):
                base = urlparse(source["url"])
                href = f"{base.scheme}://{base.netloc}{href}"
            if href in seen_links:
                continue
            seen_links.add(href)

            title = link_tag.get_text(strip=True)
            if len(title) < 10:
                continue

            articles.append({
                "title": title,
                "link": href,
                "summary_original": "",
                "published_at": None,
            })

    except Exception as e:
        log.error(f"Error scraping {source['name']}: {e}")

    return articles


def collect_all(config_path: str = "config/sources.yaml", db_path: str = None):
    """采集所有源"""
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    config = load_sources(config_path)
    conn = get_db(db_path)

    total_new = 0
    total_errors = 0
    total_sources = 0

    for region_key, region_data in config.get("regions", {}).items():
        region_label = region_data["label"]
        region_flag = region_data.get("flag", "")
        sources = region_data.get("sources", [])

        log.info(f"=== 采集地区: {region_label} ({len(sources)} 个源) ===")

        for source in sources:
            total_sources += 1
            source_id = upsert_source(conn, source, region_key, region_label, region_flag)
            log.info(f"  抓取: {source['name']}")

            try:
                if source.get("type") == "rss":
                    articles = fetch_rss(source)
                else:
                    articles = fetch_page(source)

                new_count = 0
                latest_pub = None
                for art in articles:
                    aid = insert_article(
                        conn, source_id, art["title"], art["link"],
                        art.get("summary_original", ""), source.get("lang", "en"),
                        region_key, region_label, region_flag, source["name"],
                        art.get("published_at")
                    )
                    if aid:
                        new_count += 1
                        if art.get("published_at"):
                            if latest_pub is None or art["published_at"] > latest_pub:
                                latest_pub = art["published_at"]

                is_error = len(articles) == 0
                update_source_status(conn, source_id, last_article_at=latest_pub, error=is_error)
                total_new += new_count
                if is_error:
                    total_errors += 1
                log.info(f"  {'✓' if articles else '✗'} {source['name']}: {len(articles)}篇, {new_count}篇新增")

            except Exception as e:
                update_source_status(conn, source_id, error=True)
                total_errors += 1
                log.error(f"  ✗ {source['name']}: {e}")

            time.sleep(1)

    conn.close()
    log.info(f"采集完成: {total_sources}个源, {total_new}篇新增, {total_errors}个源无数据")
    return total_new
