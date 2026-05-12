#!/usr/bin/env python3
"""为已有 articles 批量创建 summaries（关键词分类 + 重要性默认值）"""
import sqlite3, re
from datetime import datetime, timezone, timedelta

DB_PATH = "db/news.db"

CATEGORY_KEYWORDS = {
    "tech": ["ai", "digital", "platform", "api", "software", "technology", "system", "app", "online", "cloud", "data", "analytics", "robot", "automated", "gds", "nlp", "machine learning", "chatbot", "iot", "blockchain"],
    "ma": ["acquisition", "merger", "acquire", "acqui", "takeover", "buy", "sell", "deal", "stake", "ownership", "收购", "并购", "收购"],
    "partnership": ["partner", "partnership", "collaborat", "alliance", "joint venture", "strategic", "signs with", "team up", "合作", "战略合作"],
    "policy": ["policy", "regulation", "visa", "regulat", "government", "law", "rule", "ban", "restriction", "travel advisory", "border", "policy", "政策", "签证", "法规"],
    "personnel": ["ceo", "cfo", "coo", "appoint", "hire", "executive", "resign", "leave", "promot", "new head of", "任命", "高管", "离职", "上任"],
    "data": ["report", "data", "survey", "revenue", "profit", "growth", "revpar", "occupancy", "adr", "forecast", "projection", "recover", "数据", "报告", "营收", "增长"],
    "market": [],  # default
}

IMPORTANCE_KEYWORDS = {
    5: ["crisis", "emergency", "breaking", "bankrupt", "shutdown", "halt", "ban", "突发", "破产", "紧急"],
    4: ["acquisition", "merger", "strategic", "major", "significant", "record", "收购", "并购", "重大"],
    3: ["announce", "launch", "expand", "new", "partners", "合作", "推出", "扩张"],
}

def classify_category(title, summary):
    text = (title + " " + (summary or "")).lower()
    scores = {}
    for cat, kws in CATEGORY_KEYWORDS.items():
        if cat == "market":
            continue
        score = sum(1 for kw in kws if kw.lower() in text)
        if score > 0:
            scores[cat] = score
    if not scores:
        return "market"
    return max(scores, key=scores.get)

def assess_importance(title, summary):
    text = (title + " " + (summary or "")).lower()
    for level in [5, 4, 3]:
        kws = IMPORTANCE_KEYWORDS.get(level, [])
        for kw in kws:
            if kw.lower() in text:
                return level
    return 3  # default

def main():
    print("📝 回填 summaries 表...")
    conn = sqlite3.connect(DB_PATH)

    # Create summaries table
    conn.execute("""CREATE TABLE IF NOT EXISTS summaries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        article_id INTEGER NOT NULL UNIQUE REFERENCES articles(id),
        summary_zh TEXT NOT NULL,
        category TEXT NOT NULL DEFAULT 'market',
        importance INTEGER NOT NULL DEFAULT 3,
        urgency TEXT NOT NULL DEFAULT 'normal',
        related_companies TEXT DEFAULT '',
        processed_at TEXT NOT NULL DEFAULT (datetime('now')))""")

    # Create related_companies column in articles if missing
    try:
        conn.execute("ALTER TABLE articles ADD COLUMN importance INTEGER DEFAULT 3")
    except:
        pass

    articles = conn.execute("SELECT id, title, summary_original FROM articles").fetchall()
    now = datetime.now(timezone(timedelta(hours=8))).isoformat()

    count = 0
    for aid, title, summary in articles:
        summary_zh = (summary or title or "")[:300]
        category = classify_category(title, summary)
        importance = assess_importance(title, summary)

        try:
            conn.execute("""INSERT OR IGNORE INTO summaries
                (article_id, summary_zh, category, importance, urgency, related_companies, processed_at)
                VALUES (?, ?, ?, ?, 'normal', '', ?)""",
                (aid, summary_zh, category, importance, now))
            if conn.total_changes > 0:
                count += 1
        except Exception as e:
            pass

    conn.commit()
    conn.close()
    print(f"✅ 完成！回填 {count} 条 summaries")

if __name__ == "__main__":
    main()
