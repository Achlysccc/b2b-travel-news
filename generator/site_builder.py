"""静态站点生成模块"""

import json
import logging
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from db.database import (
 get_db, get_articles_with_summaries, get_articles_by_date,
 get_region_stats, get_dates_with_articles, get_breaking_articles
)

log = logging.getLogger(__name__)


# ════════════════════════════════════════
# 行业板块定义（首页四大板块 + 地区）
# ════════════════════════════════════════
SECTOR_DEFS = {
    "hotel": {
        "label": "酒店",
        "icon": "🏨",
        "keywords": [
            "酒店", "旅馆", "住宿", "民宿", "客房", "酒店业", "酒店集团",
            "万豪", "希尔顿", "洲际", "凯悦", "雅高", "首旅", "华住", "锦江",
            "hotel", "hostel", "resort", "inn ", "lodge", "accommodation",
            "Marriott", "Hilton", "IHG", "Hyatt", "Accor",
            "旅館", "宿泊", "ホテル", "ホテル業",
            "住客", "入住率", "RevPAR", "ADR", "客房收入",
            "ホテル", "観光", "旅馆业",
        ],
    },
    "flight": {
        "label": "机票",
        "icon": "✈️",
        "keywords": [
            "航空", "机票", "航班", "航司", "机场", "飞机", "廉价航空",
            "airline", "airport", "flight", "aviation", "carrier",
            "Emirates", "Lufthansa", "United Airlines", "Spirit", "Ryanair",
            "空港", "航空会社", "フライト",
            "燃油", "航权", "航线", "执飞", "机组",
            "史基浦", "航站楼",
        ],
    },
    "car": {
        "label": "用车",
        "icon": "🚗",
        "keywords": [
            "租车", "用车", "出行", "网约车", "出租车", "打车", "共享汽车",
            "car rental", "ride", "taxi", "uber", "lyft", "mobility",
            "自驾", "MaaS", "交通", "二次交通",
            "レンタカー", "タクシー", "移動",
            "道路", "机场接送",
        ],
    },
    "travel": {
        "label": "旅游",
        "icon": "🗺️",
        "keywords": [
            "旅游", "旅行", "观光", "游客", "目的地", "OTA", "在线旅游",
            "旅行社", "邮轮", "游轮", "签证", "入境", "出境",
            "tourism", "travel", "tourist", "destination", "cruise", "visa",
            "Booking.com", "Expedia", "Trip.com", "JTB", "TUI",
            "観光", "旅行", "ツーリズム", "インバウンド",
            "景区", "景点", "文化遗产", "博览会", "展会",
            "访日", "赴美", "入境游", "商旅",
        ],
    },
}

# 旧分类标签（用于分类页等子页面）
CATEGORY_LABELS = {
    "tech": "技术",
    "ma": "并购",
    "partnership": "合作",
    "policy": "政策",
    "personnel": "人事",
    "data": "数据",
    "market": "市场",
}

CATEGORY_ICONS = {
    "tech": "💻",
    "ma": "🤝",
    "partnership": "🔗",
    "policy": "📜",
    "personnel": "👤",
    "data": "📊",
    "market": "📈",
}

CATEGORY_ORDER = ["ma", "partnership", "tech", "policy", "data", "market", "personnel"]

URGENCY_LABELS = {"breaking": "🔴", "today": "🟡", "normal": ""}


def _classify_sector(summary_zh: str, title: str) -> str:
    """根据中文摘要+标题关键词判断属于哪个行业板块"""
    text = f"{summary_zh or ''} {title or ''}".lower()
    scores = {}
    for sector_id, sector_info in SECTOR_DEFS.items():
        score = 0
        for kw in sector_info["keywords"]:
            count = len(re.findall(re.escape(kw.lower()), text))
            score += count
        scores[sector_id] = score
    # 返回得分最高的，如果都0则归入travel
    best = max(scores, key=scores.get)
    if scores[best] == 0:
        return "travel"
    return best


def format_time_ago(published_at: str | None) -> str:
    if not published_at:
        return ""
    try:
        from dateutil import parser as dtparser
        dt = dtparser.parse(published_at)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        seconds = int((now - dt).total_seconds())
        if seconds < 60: return "刚刚"
        if seconds < 3600: return f"{seconds // 60}分钟前"
        if seconds < 86400: return f"{seconds // 3600}小时前"
        if seconds < 172800: return f"昨天"
        return f"{seconds // 86400}天前"
    except Exception:
        return ""


# ════════════════════════════════════════
# 重要性等级
# ════════════════════════════════════════
IMPORTANCE_THRESHOLD_HOME = 3   # 首页只展示三星及以上
IMPORTANCE_THRESHOLD_SUB  = 1   # 子版块展示一星及以上
MAX_PER_SECTOR_HOME = 5         # 首页每个板块最多5条

def _importance_level(importance: int) -> str:
  if importance >= 4: return "high"
  if importance >= 3: return "mid"
  return "low"

def _render_stars(importance: int) -> str:
  full = min(importance, 5)
  empty = max(0, 5 - full)
  return "★" * full + "☆" * empty

def _enrich_articles(articles: list[dict]) -> None:
  for a in articles:
    a["category_label"] = CATEGORY_LABELS.get(a.get("category", ""), a.get("category", ""))
    a["urgency_icon"] = URGENCY_LABELS.get(a.get("urgency", ""), "")
    a["time_ago"] = format_time_ago(a.get("published_at"))
    # 自动分类行业板块
    a["sector"] = _classify_sector(a.get("summary_zh", ""), a.get("title", ""))
    # 重要性分级
    imp = a.get("importance", 3)
    a["importance_level"] = _importance_level(imp)
    a["importance_stars"] = _render_stars(imp)


def _group_by_sector(articles: list[dict]) -> dict:
    """按行业板块分组"""
    groups = defaultdict(list)
    for a in articles:
        sector = a.get("sector", "travel")
        groups[sector].append(a)
    # 按 SECTOR_DEFS 的顺序排列
    ordered = {}
    for sector_id in SECTOR_DEFS:
        if sector_id in groups:
            ordered[sector_id] = groups[sector_id]
    # 未匹配的归入travel
    for sector_id, items in groups.items():
        if sector_id not in ordered:
            if "travel" not in ordered:
                ordered["travel"] = []
            ordered["travel"].extend(items)
    return ordered


def _group_by_category(articles: list[dict]) -> dict:
    """按分类分组，按 CATEGORY_ORDER 排列"""
    groups = defaultdict(list)
    for a in articles:
        cat = a.get("category", "market")
        groups[cat].append(a)
    ordered = {}
    for cat in CATEGORY_ORDER:
        if cat in groups:
            ordered[cat] = groups[cat]
    for cat, items in groups.items():
        if cat not in ordered:
            ordered[cat] = items
    return ordered


def _get_date_archives(conn, days: int = 60) -> list[dict]:
    """返回最近N天每天的文章计数，含日期和星期"""
    cn_tz = timezone(timedelta(hours=8))
    today = datetime.now(cn_tz).date()
    result = []
    for i in range(days - 1, -1, -1):
        d = today - timedelta(days=i)
        d_start = d.isoformat() + "T00:00:00"
        d_end = d.isoformat() + "T23:59:59"
        row = conn.execute(
            "SELECT COUNT(*) as c FROM articles WHERE is_processed = 1 AND published_at >= ? AND published_at <= ?",
            (d_start, d_end)
        ).fetchone()
        count = row["c"] if row else 0
        weekday = ["周一","周二","周三","周四","周五","周六","周日"][d.weekday()]
        is_weekend = d.weekday() >= 5
        result.append({
            "date": d.isoformat(),
            "day": d.day,
            "month_label": d.strftime("%m/%d"),
            "weekday_short": weekday,
            "count": count,
            "is_weekend": is_weekend,
            "is_today": d == today,
        })
    return result


def _get_month_groups(dates: list[dict]) -> list[dict]:
    """按月分组，供模板渲染"""
    months = []
    current_month = None
    for d in dates:
        ym = d["date"][:7]  # "2026-04"
        if current_month != ym:
            current_month = ym
            months.append({"key": ym, "label": f"{ym[5:]}月{ym[:4]}年", "days": []})
        months[-1]["days"].append(d)
    return months



def _get_top_companies(conn, days: int = 3, limit: int = 25) -> list[dict]:
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
    rows = conn.execute(
        """SELECT s.related_companies
           FROM articles a JOIN summaries s ON a.id = s.article_id
           WHERE a.is_processed = 1 AND a.published_at > ? AND s.related_companies != ''
        """, (cutoff,)
    ).fetchall()
    counter = Counter()
    for r in rows:
        for name in r["related_companies"].split(","):
            name = name.strip()
            if name:
                counter[name] += 1
    return [{"name": n, "count": c} for n, c in counter.most_common(limit)]


def _get_region_digests(conn, region_stats: list, days: int = 3) -> list[dict]:
    """每个地区取最核心的一条摘要做速览"""
    result = []
    for rs in region_stats:
        region = rs["region"]
        rows = conn.execute(
            """SELECT a.title, s.summary_zh
               FROM articles a JOIN summaries s ON a.id = s.article_id
               WHERE a.is_processed = 1 AND a.region = ?
               ORDER BY s.importance DESC, a.published_at DESC LIMIT 1
            """, (region,)
        ).fetchall()
        top_summary = ""
        if rows:
            r = rows[0]
            top_summary = r["summary_zh"] if r["summary_zh"] else r["title"]
            if len(top_summary) > 60:
                top_summary = top_summary[:57] + "…"
        result.append({
            "region": region,
            "flag": rs["region_flag"],
            "label": rs["region_label"],
            "count": rs["count"],
            "top_summary": top_summary,
        })
    return result


def _count_today(conn) -> int:
    cutoff = (datetime.utcnow() - timedelta(hours=24)).isoformat()
    row = conn.execute(
        "SELECT COUNT(*) as c FROM articles WHERE is_processed = 1 AND published_at > ?",
        (cutoff,)
    ).fetchone()
    return row["c"] if row else 0


def _count_breaking(conn, hours: int = 48) -> int:
    cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
    row = conn.execute(
        """SELECT COUNT(*) as c FROM articles a JOIN summaries s ON a.id = s.article_id
           WHERE a.is_processed = 1 AND s.urgency = 'breaking' AND a.published_at > ?""",
        (cutoff,)
    ).fetchone()
    return row["c"] if row else 0


def _count_sources(conn) -> int:
    row = conn.execute("SELECT COUNT(*) as c FROM sources WHERE status = 'active'").fetchone()
    return row["c"] if row else 0


def _build_digest_lines(articles_by_sector: dict) -> list[str]:
    """构建今日摘要5行：从每个行业板块取最重要一条浓缩"""
    lines = []
    for sector_id in SECTOR_DEFS:
        sector_arts = articles_by_sector.get(sector_id, [])
        if sector_arts:
            a = sector_arts[0]
            summary = a.get("summary_zh") or a.get("title", "")
            if len(summary) > 60:
                summary = summary[:57] + "…"
            companies = a.get("related_companies", "")
            sector_label = SECTOR_DEFS[sector_id]["label"]
            if companies:
                lines.append(f"{companies}：{summary}")
            else:
                lines.append(summary)
            if len(lines) >= 5:
                break
    # 如果不够5行，从其他文章补
    if len(lines) < 5:
        all_arts = []
        for arts in articles_by_sector.values():
            all_arts.extend(arts)
        for a in all_arts:
            if len(lines) >= 5:
                break
            summary = a.get("summary_zh") or a.get("title", "")
            if len(summary) > 60:
                summary = summary[:57] + "…"
            line = f"{a.get('related_companies', '行业')}：{summary}" if a.get("related_companies") else summary
            if line not in lines:
                lines.append(line)
    return lines[:5]


def _get_archive_days(conn, lookback_days: int = 60) -> dict:
    """获取最近有数据的日期，按月分组"""
    cutoff = (datetime.utcnow() - timedelta(days=lookback_days)).isoformat()
    rows = conn.execute(
        """SELECT DISTINCT DATE(published_at) as d
           FROM articles WHERE is_processed = 1 AND published_at > ?
           ORDER BY d DESC""",
        (cutoff,)
    ).fetchall()
    months = {}
    for r in rows:
        d = r["d"]
        month_key = d[:7]
        day = d[8:]
        if month_key not in months:
            months[month_key] = []
        months[month_key].append(day)
    return months




def build_site(config_path: str = "config/settings.yaml", db_path: str = None, output_path: str = None):
    """生成完整静态站点"""
    import yaml
    with open(config_path, "r", encoding="utf-8") as f:
        settings = yaml.safe_load(f)

    if output_path is None:
        output_path = settings.get("output", {}).get("path", "./output")
    output_dir = Path(output_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    conn = get_db(db_path)

    template_dir = Path(__file__).parent.parent / "templates"
    env = Environment(loader=FileSystemLoader(str(template_dir)), autoescape=True)
    env.filters["time_ago"] = format_time_ago

    site_name = settings["site"]["name"]
    site_desc = settings["site"]["description"]
    cn_tz = timezone(timedelta(hours=8))
    now_cn = datetime.now(cn_tz)
    now_str = now_cn.strftime("%Y-%m-%d %H:%M")
    today_str = now_cn.strftime("%Y-%m-%d")
    weekday_zh = ["周一","周二","周三","周四","周五","周六","周日"][now_cn.weekday()]

    # 首页数据（只取重要性>=3，每板块最多5条）
    all_articles_home = get_articles_with_summaries(conn, days=3, limit=200, min_importance=IMPORTANCE_THRESHOLD_HOME)
    _enrich_articles(all_articles_home)
    articles_by_sector = _group_by_sector(all_articles_home)
    for sid in articles_by_sector:
        articles_by_sector[sid] = articles_by_sector[sid][:MAX_PER_SECTOR_HOME]

    # 全量数据（子版块用）
    all_articles = get_articles_with_summaries(conn, days=7, limit=300, min_importance=IMPORTANCE_THRESHOLD_SUB)
    _enrich_articles(all_articles)

    breaking = get_breaking_articles(conn, hours=48)
    _enrich_articles(breaking)

    region_stats = get_region_stats(conn, days=3)
    articles_by_sector_all = _group_by_sector(all_articles)
    articles_by_category = _group_by_category(all_articles)
    top_companies = _get_top_companies(conn, days=3)
    region_digests = _get_region_digests(conn, region_stats, days=3)
    total_articles_home = len(all_articles_home)
    low_imp_count = len([a for a in all_articles if a.get("importance", 3) < IMPORTANCE_THRESHOLD_HOME])
    today_articles = _count_today(conn)
    breaking_count = _count_breaking(conn)
    region_count = len(region_stats)
    source_count = _count_sources(conn)
    company_count = len(top_companies)
    digest_lines = _build_digest_lines(articles_by_sector)
    archive_days = _get_archive_days(conn)
    date_archives = _get_date_archives(conn, days=60)
    date_archives_months = _get_month_groups(date_archives)
    today_day = now_cn.strftime("%d")
    today_display = f"{now_cn.year}/{now_cn.month}/{now_cn.day}"

    # 首页
    index_html = env.get_template("index.html").render(
        site_name=site_name, site_desc=site_desc, updated_at=now_str,
        today=today_str, weekday_zh=weekday_zh, today_display=today_display, today_day=today_day,
        digest_lines=digest_lines, archive_days=archive_days,
        all_articles=all_articles, breaking=breaking, region_stats=region_stats,
        sectors=SECTOR_DEFS, articles_by_sector=articles_by_sector,
        articles_by_sector_all=articles_by_sector_all,
        categories=CATEGORY_LABELS, CATEGORY_LABELS=CATEGORY_LABELS,
        articles_by_category=articles_by_category, category_icons=CATEGORY_ICONS,
        CATEGORY_ICONS=CATEGORY_ICONS,
        top_companies=top_companies, region_digests=region_digests,
        low_imp_count=low_imp_count, total_articles=total_articles_home,
        today_articles=today_articles, breaking_count=breaking_count,
        region_count=region_count, source_count=source_count, company_count=company_count,
        current_region=None, current_category=None,
        date_archives=date_archives, date_archives_months=date_archives_months,
    )
    (output_dir / "index.html").write_text(index_html, encoding="utf-8")

    # 行业板块页
    sector_dir = output_dir / "sector"
    sector_dir.mkdir(exist_ok=True)
    for sector_id, sector_info in SECTOR_DEFS.items():
        sector_all = get_articles_with_summaries(conn, days=7, limit=300, min_importance=IMPORTANCE_THRESHOLD_SUB)
        _enrich_articles(sector_all)
        sector_articles = [a for a in sector_all if a.get("sector") == sector_id]
        sector_html = env.get_template("sector.html").render(
            site_name=site_name, site_desc=site_desc, updated_at=now_str,
            sector_id=sector_id, sector_label=sector_info["label"], sector_icon=sector_info["icon"],
            articles=sector_articles, region_stats=region_stats,
            sectors=SECTOR_DEFS, articles_by_sector=articles_by_sector_all,
            CATEGORY_LABELS=CATEGORY_LABELS, CATEGORY_ICONS=CATEGORY_ICONS,
            all_articles=sector_all,  # 用于搜索
            current_sector=sector_id, current_region=None, current_category=None,
            breaking_count=breaking_count,
        )
        (sector_dir / f"{sector_id}.html").write_text(sector_html, encoding="utf-8")

    # 地区页
    regions_config_path = Path(__file__).parent.parent / "config" / "sources.yaml"
    with open(regions_config_path, "r", encoding="utf-8") as f:
        regions_config = yaml.safe_load(f)
    region_dir = output_dir / "region"
    region_dir.mkdir(exist_ok=True)
    for region_key, region_data in regions_config.get("regions", {}).items():
        region_articles = get_articles_with_summaries(conn, region=region_key, days=7, limit=100)
        _enrich_articles(region_articles)
        region_breaking = get_breaking_articles(conn, hours=72)
        region_html = env.get_template("region.html").render(
            site_name=site_name, site_desc=site_desc, updated_at=now_str,
            region_key=region_key, region_label=region_data["label"],
            region_flag=region_data.get("flag", ""),
            articles=region_articles, breaking=region_breaking, region_stats=region_stats,
            categories=CATEGORY_LABELS, sectors=SECTOR_DEFS,
            CATEGORY_LABELS=CATEGORY_LABELS, CATEGORY_ICONS=CATEGORY_ICONS,
            articles_by_sector=articles_by_sector_all,
            current_region=region_key, current_category=None,
            all_articles=region_articles,
            breaking_count=breaking_count,
        )
        (region_dir / f"{region_key}.html").write_text(region_html, encoding="utf-8")

    # 分类页
    category_dir = output_dir / "category"
    category_dir.mkdir(exist_ok=True)
    for cat_id, cat_label in CATEGORY_LABELS.items():
        cat_articles = get_articles_with_summaries(conn, category=cat_id, days=7, limit=100)
        _enrich_articles(cat_articles)
        cat_html = env.get_template("category.html").render(
            site_name=site_name, site_desc=site_desc, updated_at=now_str,
            category_id=cat_id, category_label=cat_label,
            articles=cat_articles, region_stats=region_stats,
            categories=CATEGORY_LABELS, sectors=SECTOR_DEFS,
            CATEGORY_LABELS=CATEGORY_LABELS, CATEGORY_ICONS=CATEGORY_ICONS,
            articles_by_sector=articles_by_sector_all,
            current_region=None, current_category=cat_id,
            all_articles=cat_articles,
            breaking_count=breaking_count,
        )
        (category_dir / f"{cat_id}.html").write_text(cat_html, encoding="utf-8")

    # 突发页
    breaking_all = get_breaking_articles(conn, hours=72)
    _enrich_articles(breaking_all)
    breaking_html = env.get_template("breaking.html").render(
        site_name=site_name, site_desc=site_desc, updated_at=now_str,
        articles=breaking_all, region_stats=region_stats,
        categories=CATEGORY_LABELS, sectors=SECTOR_DEFS,
        CATEGORY_LABELS=CATEGORY_LABELS, CATEGORY_ICONS=CATEGORY_ICONS,
        articles_by_sector=articles_by_sector_all,
        all_articles=breaking_all, page_type="breaking",
        breaking_count=breaking_count,
    )
    (output_dir / "breaking.html").write_text(breaking_html, encoding="utf-8")

    # 日期归档页
    date_dir = output_dir / "date"
    date_dir.mkdir(exist_ok=True)
    for d_entry in date_archives:
        if d_entry["count"] > 0:
            day_arts = get_articles_by_date(conn, d_entry["date"])
            _enrich_articles(day_arts)
            articles_by_sector_day = _group_by_sector(day_arts)
            day_html = env.get_template("date.html").render(
                site_name=site_name, site_desc=site_desc, updated_at=now_str,
                date_label=d_entry["date"], weekday=d_entry["weekday_short"],
                articles=day_arts, articles_by_sector=articles_by_sector_day,
                region_stats=region_stats,
                categories=CATEGORY_LABELS, sectors=SECTOR_DEFS,
                CATEGORY_LABELS=CATEGORY_LABELS, CATEGORY_ICONS=CATEGORY_ICONS,
                all_articles=day_arts, breaking_count=d_entry["count"],
            )
            (date_dir / f"{d_entry['date']}.html").write_text(day_html, encoding="utf-8")


    # 复制静态资源
    import shutil
    static_src = Path(__file__).parent.parent / "static"
    static_dst = output_dir / "static"
    if static_src.exists():
        if static_dst.exists():
            shutil.rmtree(static_dst)
        shutil.copytree(static_src, static_dst)

    conn.close()
    log.info(f"站点已生成到 {output_dir}")
    return str(output_dir)
