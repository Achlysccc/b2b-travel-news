#!/usr/bin/env python3
"""AI 摘要生成 — 调 GLM-5.1 为每篇未处理文章生成中文摘要"""
import sqlite3, requests, json, time, re, yaml, os
from pathlib import Path
from datetime import datetime

DB_PATH = os.environ.get("DB_PATH", "db/news.db")

# ════════════════════════════════════════
# GLM-5.1 API 配置
# ════════════════════════════════════════
def get_api_key():
    config_path = Path.home() / ".hermes" / "config.yaml"
    if config_path.exists():
        with open(config_path) as f:
            cfg = yaml.safe_load(f)
        for p in cfg.get("custom_providers", []):
            if "ark.cn-beijing.volces.com" in p.get("base_url", ""):
                return p["api_key"], p["base_url"]
    key_file = Path.home() / ".hermes" / ".api_key"
    if key_file.exists():
        return key_file.read_text().strip(), "https://ark.cn-beijing.volces.com/api/coding/v3"
    raise RuntimeError("找不到 Volcengine API key")

API_KEY, BASE_URL = get_api_key()
API_URL = f"{BASE_URL}/chat/completions"

CATEGORIES = ["ma", "tech", "partnership", "policy", "data", "market", "personnel"]
CATEGORY_LABELS = {
    "ma": "并购", "tech": "技术", "partnership": "合作",
    "policy": "政策", "data": "数据", "market": "市场", "personnel": "人事"
}

def generate_summary(title: str, original_summary: str, region: str) -> dict:
    """调 GLM-5.1 生成一条中文摘要"""
    prompt = f"""你是一个B2B旅游行业新闻分析师。请为以下新闻生成结构化摘要。

标题: {title}
原始摘要: {original_summary or '无'}
地区: {region}

请按以下JSON格式输出（只输出JSON，不要其他文字）：
{{
  "summary_zh": "中文摘要，不超过80字，简洁专业",
  "category": "ma|tech|partnership|policy|data|market|personnel 之一",
  "importance": 1-5的整数，5最重要",
  "urgency": "breaking|today|normal 之一",
  "related_companies": "相关公司名称，逗号分隔，无则空字符串"
}}"""

    try:
        resp = requests.post(API_URL, headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }, json={
            "model": "GLM-5.1",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 300,
            "temperature": 0.3
        }, timeout=60)
        result = resp.json()
        content = result["choices"][0]["message"].get("content") or \
                  result["choices"][0]["message"].get("reasoning_content", "")
        # 提取 JSON
        start = content.find("{")
        end = content.rfind("}") + 1
        if start >= 0 and end > start:
            parsed = json.loads(content[start:end])
            # 校验字段
            return {
                "summary_zh": str(parsed.get("summary_zh", "") or "")[:200],
                "category": parsed.get("category", "market") if parsed.get("category") in CATEGORIES else "market",
                "importance": min(5, max(1, int(parsed.get("importance", 3)))),
                "urgency": parsed.get("urgency", "normal") if parsed.get("urgency") in ("breaking", "today", "normal") else "normal",
                "related_companies": str(parsed.get("related_companies") or "")[:200],
            }
    except Exception as e:
        print(f"  API错误: {e}")
    return None


if __name__ == "__main__":
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # 建表（如果不存在）
    conn.execute("""CREATE TABLE IF NOT EXISTS summaries (
        id INTEGER PRIMARY KEY,
        article_id INTEGER UNIQUE,
        summary_zh TEXT,
        category TEXT,
        importance INTEGER,
        urgency TEXT,
        related_companies TEXT
    )""")

    # 取所有未处理的文章
    articles = conn.execute(
        "SELECT id, title, summary_original, region FROM articles WHERE is_processed=0"
    ).fetchall()
    print(f"待处理: {len(articles)} 条")

    if not articles:
        print("✅ 没有待处理文章")
        conn.close()
        exit(0)

    success = 0
    failed = 0

    for art in articles:
        aid, title, orig_sum, region = art["id"], art["title"], art["summary_original"] or "", art["region"]
        print(f"  处理 [{aid}] {title[:50]}...")

        result = generate_summary(title, orig_sum, region)

        if result:
            conn.execute("""INSERT OR REPLACE INTO summaries
                (article_id, summary_zh, category, importance, urgency, related_companies)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (aid, result["summary_zh"], result["category"],
                 result["importance"], result["urgency"], result["related_companies"]))
            conn.execute("UPDATE articles SET is_processed=1 WHERE id=?", (aid,))
            success += 1
            print(f"  ✅ [{result['category']}] {result['summary_zh'][:40]}")
        else:
            # fallback：写入原始标题作为摘要，标记已处理避免卡住
            conn.execute("""INSERT OR REPLACE INTO summaries
                (article_id, summary_zh, category, importance, urgency, related_companies)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (aid, title, "market", 3, "normal", ""))
            conn.execute("UPDATE articles SET is_processed=1 WHERE id=?", (aid,))
            failed += 1
            print(f"  ⚠️ fallback")

        time.sleep(0.5)  # 避免 API 限速

    conn.commit()
    total = conn.execute("SELECT COUNT(*) FROM summaries").fetchone()[0]
    print(f"\n✅ 完成: 成功 {success}, 失败 {failed}, 累计摘要 {total} 条")
    conn.close()
