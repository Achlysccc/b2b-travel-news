"""数据库模块 - SQLite schema + CRUD 操作"""

import sqlite3
import hashlib
import os
from datetime import datetime, timedelta
from pathlib import Path


SCHEMA = """
CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    url TEXT NOT NULL UNIQUE,
    type TEXT NOT NULL DEFAULT 'rss',
    lang TEXT NOT NULL DEFAULT 'en',
    region TEXT NOT NULL,
    region_label TEXT NOT NULL,
    region_flag TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active',
    last_fetched_at TEXT,
    last_article_at TEXT,
    fetch_count INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL REFERENCES sources(id),
    title TEXT NOT NULL,
    link TEXT NOT NULL,
    summary_original TEXT,
    lang TEXT NOT NULL,
    region TEXT NOT NULL,
    region_label TEXT NOT NULL,
    region_flag TEXT NOT NULL,
    source_name TEXT NOT NULL,
    published_at TEXT,
    fetched_at TEXT NOT NULL DEFAULT (datetime('now')),
    fingerprint TEXT NOT NULL UNIQUE,
    is_processed INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_articles_published ON articles(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_articles_region ON articles(region);
CREATE INDEX IF NOT EXISTS idx_articles_processed ON articles(is_processed);
CREATE INDEX IF NOT EXISTS idx_articles_fingerprint ON articles(fingerprint);

CREATE TABLE IF NOT EXISTS summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id INTEGER NOT NULL REFERENCES articles(id) UNIQUE,
    summary_zh TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'market',
    importance INTEGER NOT NULL DEFAULT 3,
    urgency TEXT NOT NULL DEFAULT 'normal',
    related_companies TEXT DEFAULT '',
    processed_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_summaries_category ON summaries(category);
CREATE INDEX IF NOT EXISTS idx_summaries_importance ON summaries(importance DESC);
CREATE INDEX IF NOT EXISTS idx_summaries_urgency ON summaries(urgency);

CREATE TABLE IF NOT EXISTS companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name_zh TEXT NOT NULL,
    name_en TEXT,
    aliases TEXT DEFAULT ''
);
"""


def get_db(db_path: str = None) -> sqlite3.Connection:
    if db_path is None:
        db_path = os.environ.get("DB_PATH", "./db/news.db")
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    return conn


def make_fingerprint(title: str, link: str) -> str:
    """生成文章指纹用于去重"""
    raw = f"{title.strip().lower()}|{link.strip().lower()}"
    return hashlib.md5(raw.encode()).hexdigest()


def upsert_source(conn: sqlite3.Connection, source: dict, region: str, region_label: str, region_flag: str) -> int:
    """插入或更新信息源，返回 source_id"""
    row = conn.execute("SELECT id FROM sources WHERE url = ?", (source["url"],)).fetchone()
    if row:
        return row["id"]
    cur = conn.execute(
        """INSERT INTO sources (name, url, type, lang, region, region_label, region_flag)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (source["name"], source["url"], source.get("type", "rss"),
         source.get("lang", "en"), region, region_label, region_flag)
    )
    conn.commit()
    return cur.lastrowid


def insert_article(conn: sqlite3.Connection, source_id: int, title: str, link: str,
                   summary_original: str, lang: str, region: str, region_label: str,
                   region_flag: str, source_name: str, published_at: str) -> int | None:
    """插入文章，重复则跳过，返回 article_id 或 None"""
    fp = make_fingerprint(title, link)
    try:
        cur = conn.execute(
            """INSERT INTO articles
               (source_id, title, link, summary_original, lang, region, region_label,
                region_flag, source_name, published_at, fingerprint)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (source_id, title, link, summary_original, lang, region, region_label,
             region_flag, source_name, published_at, fp)
        )
        conn.commit()
        return cur.lastrowid
    except sqlite3.IntegrityError:
        return None


def update_source_status(conn: sqlite3.Connection, source_id: int, last_article_at: str = None, error: bool = False):
    """更新信息源抓取状态"""
    now = datetime.utcnow().isoformat()
    if error:
        conn.execute(
            "UPDATE sources SET last_fetched_at = ?, error_count = error_count + 1 WHERE id = ?",
            (now, source_id)
        )
    else:
        if last_article_at:
            conn.execute(
                "UPDATE sources SET last_fetched_at = ?, last_article_at = ?, fetch_count = fetch_count + 1, error_count = 0 WHERE id = ?",
                (now, last_article_at, source_id)
            )
        else:
            conn.execute(
                "UPDATE sources SET last_fetched_at = ?, fetch_count = fetch_count + 1, error_count = 0 WHERE id = ?",
                (now, source_id)
            )
    conn.commit()


def get_unprocessed_articles(conn: sqlite3.Connection) -> list[dict]:
    """获取未处理的文章"""
    rows = conn.execute(
        """SELECT a.*, s.lang as source_lang FROM articles a
           JOIN sources s ON a.source_id = s.id
           WHERE a.is_processed = 0
           ORDER BY a.published_at DESC"""
    ).fetchall()
    return [dict(r) for r in rows]


def insert_summary(conn: sqlite3.Connection, article_id: int, summary_zh: str,
                   category: str, importance: int, urgency: str, related_companies: str):
    """插入AI处理后的摘要"""
    conn.execute(
        """INSERT INTO summaries (article_id, summary_zh, category, importance, urgency, related_companies)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (article_id, summary_zh, category, importance, urgency, related_companies)
    )
    conn.execute("UPDATE articles SET is_processed = 1 WHERE id = ?", (article_id,))
    conn.commit()


def get_articles_with_summaries(conn: sqlite3.Connection, region: str = None,
  category: str = None, days: int = 7,
  limit: int = 200, min_importance: int = None) -> list[dict]:
  """获取带摘要的文章列表，支持按地区/分类/时间/最低重要性筛选"""
  where_clauses = ["a.is_processed = 1"]
  params = []

  if region:
    where_clauses.append("a.region = ?")
    params.append(region)
  if category:
    where_clauses.append("s.category = ?")
    params.append(category)
  if days:
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
    where_clauses.append("a.published_at > ?")
    params.append(cutoff)
    if min_importance is not None:
        where_clauses.append("s.importance >= ?")
        params.append(min_importance)

    where = " AND ".join(where_clauses)
    query = f"""
    SELECT a.*, s.summary_zh, s.category, s.importance, s.urgency, s.related_companies
    FROM articles a
    JOIN summaries s ON a.id = s.article_id
    WHERE {where}
    ORDER BY s.importance DESC, a.published_at DESC
    LIMIT ?
    """
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def get_articles_by_date(conn: sqlite3.Connection, date: str, limit: int = 100) -> list[dict]:
    """获取指定日期（YYYY-MM-DD）的所有文章"""
    d_start = date + "T00:00:00"
    d_end = date + "T23:59:59"
    rows = conn.execute(
        """SELECT a.*, s.summary_zh, s.category, s.importance, s.urgency, s.related_companies
 FROM articles a JOIN summaries s ON a.id = s.article_id
 WHERE a.is_processed = 1 AND a.published_at >= ? AND a.published_at <= ?
 ORDER BY s.importance DESC, a.published_at DESC LIMIT ?""",
        (d_start, d_end, limit)
    ).fetchall()
    return [dict(r) for r in rows]


def get_region_stats(conn: sqlite3.Connection, days: int = 1) -> list[dict]:
    """获取各地区文章数量统计"""
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
    rows = conn.execute(
        """SELECT a.region, a.region_label, a.region_flag, COUNT(*) as count
           FROM articles a
           JOIN summaries s ON a.id = s.article_id
           WHERE a.is_processed = 1 AND a.published_at > ?
           GROUP BY a.region
           ORDER BY count DESC""",
        (cutoff,)
    ).fetchall()
    return [dict(r) for r in rows]


def get_dates_with_articles(conn: sqlite3.Connection, days: int = 30) -> list[str]:
    """获取有文章的日期列表"""
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
    rows = conn.execute(
        """SELECT DISTINCT DATE(a.published_at) as date
           FROM articles a
           WHERE a.is_processed = 1 AND a.published_at > ?
           ORDER BY date DESC""",
        (cutoff,)
    ).fetchall()
    return [r["date"] for r in rows]


def get_breaking_articles(conn: sqlite3.Connection, hours: int = 48) -> list[dict]:
    """获取突发新闻"""
    cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
    rows = conn.execute(
        """SELECT a.*, s.summary_zh, s.category, s.importance, s.urgency, s.related_companies
           FROM articles a
           JOIN summaries s ON a.id = s.article_id
           WHERE a.is_processed = 1 AND s.urgency = 'breaking' AND a.published_at > ?
           ORDER BY a.published_at DESC""",
        (cutoff,)
    ).fetchall()
    return [dict(r) for r in rows]


def cleanup_old_data(conn: sqlite3.Connection, retention_days: int = 90):
    """清理过期数据"""
    cutoff = (datetime.utcnow() - timedelta(days=retention_days)).isoformat()
    # 先删摘要
    conn.execute(
        """DELETE FROM summaries WHERE article_id IN
           (SELECT id FROM articles WHERE published_at < ?)""",
        (cutoff,)
    )
    # 再删文章
    conn.execute("DELETE FROM articles WHERE published_at < ?", (cutoff,))
    conn.commit()


def load_companies(conn: sqlite3.Connection, companies_file: str = None):
    """从 Top100 Excel 导入公司名录（后续可加）"""
    pass
