#!/usr/bin/env python3
"""翻译未翻译的摘要为中文（只处理 summary_zh 中没有中文字符的条目）"""
import sqlite3, requests, json, time, re, yaml
from pathlib import Path

# 从 hermes config 读取 Volcengine API key
def get_api_key():
    config_path = Path.home() / ".hermes" / "config.yaml"
    if config_path.exists():
        with open(config_path) as f:
            cfg = yaml.safe_load(f)
        for p in cfg.get("custom_providers", []):
            if "ark.cn-beijing.volces.com" in p.get("base_url", ""):
                return p["api_key"], p["base_url"]
    # fallback
    key_file = Path.home() / ".hermes" / ".api_key"
    if key_file.exists():
        return key_file.read_text().strip(), "https://ark.cn-beijing.volces.com/api/coding/v3"
    raise RuntimeError("找不到 Volcengine API key")

API_KEY, BASE_URL = get_api_key()
API_URL = f"{BASE_URL}/chat/completions"

DB_PATH = os.environ.get("DB_PATH", "db/news.db") if "os" in dir() else "db/news.db"
import os
DB_PATH = os.environ.get("DB_PATH", "db/news.db")

def has_chinese(text):
    """检查文本是否包含中文字符"""
    return bool(re.search(r'[\u4e00-\u9fff]', text or ''))

def translate_batch(items):
    """翻译一批标题+摘要"""
    articles_text = '\n\n'.join([
        f"[{i+1}] 标题: {t}\n摘要: {s[:400] if s else '无'}"
        for i, (t, s) in enumerate(items)
    ])

    prompt = f"""你是一个B2B旅游行业新闻翻译专家。请将以下英文标题和摘要翻译成中文（专业、简洁、地道、无AI味）：

{articles_text}

要求：
- 标题翻译简洁专业
- 摘要翻译保留关键数据（数字、公司名、技术术语）
- 只输出JSON数组格式，每行一个数组元素，不要有其他文字"""

    try:
        resp = requests.post(API_URL, headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }, json={
            "model": "GLM-5.1",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 4000,
            "temperature": 0.3
        }, timeout=120)
        result = resp.json()
        content = result['choices'][0]['message'].get('content') or \
                  result['choices'][0]['message'].get('reasoning_content', '')
        start = content.find('[')
        end = content.rfind(']') + 1
        if start >= 0 and end > start:
            return json.loads(content[start:end])
    except Exception as e:
        print(f'API错误: {e}')
        if 'result' in dir() and 'error' in result:
            print(f"API error details: {result}")
    return None

if __name__ == "__main__":
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 只取 summary_zh 没有中文字符的条目
    cur.execute("""
        SELECT s.id, a.title, a.summary_original, s.article_id
        FROM summaries s
        JOIN articles a ON s.article_id = a.id
        WHERE s.summary_zh NOT GLOB '*[一-龥]*'
        ORDER BY s.article_id
    """)
    articles = [(r['article_id'], r['title'], r['summary_original'] or '') for r in cur.fetchall()]
    conn.close()

    if not articles:
        print("✅ 所有摘要已是中文，无需翻译")
        exit(0)

    print(f'需要翻译 {len(articles)} 条')

    BATCH = 5
    all_results = {}
    for i in range(0, len(articles), BATCH):
        batch = articles[i:i+BATCH]
        batch_ids = [a[0] for a in batch]
        batch_texts = [(a[1], a[2]) for a in batch]

        print(f'批次 {i//BATCH + 1}/{(len(articles)-1)//BATCH + 1}，IDs: {batch_ids}')
        translated = translate_batch(batch_texts)

        if translated:
            for j, (zh_title, zh_summary) in enumerate(translated):
                if j < len(batch_ids):
                    all_results[batch_ids[j]] = (zh_title, zh_summary)
            print(f'  ✅ {len(translated)} 条')
        else:
            for bid in batch_ids:
                all_results[bid] = ('', '')
            print(f'  ❌ 失败')

        time.sleep(1.5)

    # 更新数据库
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    count = 0
    for art_id, (zh_title, zh_summary) in all_results.items():
        if zh_summary:
            cur.execute('UPDATE summaries SET summary_zh = ? WHERE article_id = ?', (zh_summary, art_id))
            count += 1

    conn.commit()
    print(f'\n✅ 更新了 {count} 条中文摘要')
    conn.close()
