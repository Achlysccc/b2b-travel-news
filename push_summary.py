#!/usr/bin/env python3
"""推送中文概览到 WeChat — 读取数据库生成今日动态摘要"""
import sqlite3, os
from datetime import datetime, timedelta

DB_PATH = os.environ.get("DB_PATH", "db/news.db")

CATEGORY_LABELS = {
    "ma": "并购", "tech": "技术", "partnership": "合作",
    "policy": "政策", "data": "数据", "market": "市场", "personnel": "人事"
}
REGION_LABELS = {
    "china": "🇨🇳 中国", "north-america": "🇺🇸 北美", "uk-ireland": "🇬🇧 英国",
    "southeast-asia": "🌏 东南亚", "latam": "🌎 拉美", "europe": "🇪🇺 欧洲",
    "japan": "🇯🇵 日本", "india": "🇮🇳 印度", "oceania": "🇦🇺 大洋洲",
    "middle-east": "🇸🇦 中东", "africa": "🌍 非洲",
}


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def build_digest():
    conn = get_db()
    now = datetime.utcnow()

    cutoff = (now - timedelta(hours=24)).isoformat()
    today_count = conn.execute(
        "SELECT COUNT(*) FROM articles WHERE is_processed=1 AND published_at > ?", (cutoff,)
    ).fetchone()[0]

    top = conn.execute("""
        SELECT s.summary_zh, s.category, s.importance, s.urgency, s.related_companies,
               a.title, a.region, a.published_at, a.link
        FROM summaries s
        JOIN articles a ON s.article_id = a.id
        WHERE s.importance >= 3
        ORDER BY s.importance DESC, a.published_at DESC
        LIMIT 12
    """).fetchall()

    regions = conn.execute("""
        SELECT a.region, COUNT(*) as c
        FROM articles a WHERE a.is_processed=1
        GROUP BY a.region ORDER BY c DESC
    """).fetchall()

    source_count = conn.execute(
        "SELECT COUNT(*) FROM sources WHERE status='active'"
    ).fetchone()[0]

    conn.close()
    return now, today_count, top, regions, source_count


def format_digest():
    now, today_count, top, regions, source_count = build_digest()

    lines = []
    lines.append(f"📋 B2B旅游分销 行业日报")
    lines.append(f"🕐 生成时间：{now.strftime('%Y-%m-%d %H:%M')} (UTC)")
    lines.append(f"")
    lines.append(f"📊 今日概览")
    lines.append(f"  新增动态：{today_count} 条")
    lines.append(f"  信息源：{source_count} 个")
    lines.append(f"  覆盖地区：{len(regions)} 个")

    if regions:
        region_str = " · ".join([
            f"{REGION_LABELS.get(r['region'], r['region'])}({r['c']})"
            for r in regions[:6]
        ])
        lines.append(f"  地区：{region_str}")

    lines.append(f"")
    lines.append(f"⭐ 重点动态 ({len(top)} 条)")

    if top:
        for i, item in enumerate(top, 1):
            cat = CATEGORY_LABELS.get(item["category"], item["category"])
            stars = "★" * item["importance"] + "☆" * (5 - item["importance"])
            region = REGION_LABELS.get(item["region"], item["region"])
            companies = f" | {item['related_companies']}" if item["related_companies"] else ""
            urgency_icon = "🔴" if item["urgency"] == "breaking" else ("🟡" if item["urgency"] == "today" else "")
            summary_text = (item['summary_zh'] or item['title'] or '')[:60]
            lines.append(f"")
            lines.append(f"  {i}. {urgency_icon}{summary_text}")
            lines.append(f"     📁 {cat} {stars}{companies}")
    else:
        lines.append(f"  暂无重点动态，数据采集中")

    lines.append(f"")
    lines.append(f"🔗 https://achlysccc.github.io/b2b-travel-news/")

    return "\n".join(lines)


if __name__ == "__main__":
    digest = format_digest()
    print(digest)

    # 输出 JSON 格式，方便 update.sh 调用 Hermes API
    import json, sys
    print(f"\n__HERMES_MSG__:{digest}", file=sys.stdout)
