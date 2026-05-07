#!/usr/bin/env python3
"""翻译所有文章摘要为中文"""
import sqlite3, requests, json, time

API_URL = "https://ark.cn-beijing.volces.com/api/coding/v3/chat/completions"

# 读取 API key
with open('/home/user/.hermes/.api_key') as f:
    API_KEY = f.read().strip()

conn = sqlite3.connect('db/news.db')
cur = conn.cursor()
cur.execute('SELECT id, title, summary_original FROM articles ORDER BY id')
articles = [(r[0], r[1], r[2] or '') for r in cur.fetchall()]
conn.close()

print(f'需要翻译 {len(articles)} 条')

def translate_batch(items):
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
            "model": "glm-5.1",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 4000,
            "temperature": 0.3
        }, timeout=120)
        result = resp.json()
        content = result['choices'][0]['message']['content']
        start = content.find('[')
        end = content.rfind(']') + 1
        if start >= 0 and end > start:
            return json.loads(content[start:end])
    except Exception as e:
        print(f'API错误: {e}')
        if 'choices' in locals() and 'error' in result:
            print(f"API error details: {result}")
    return None

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
            all_results[batch_ids[j]] = (zh_title, zh_summary)
        print(f'  ✅ {len(translated)} 条')
    else:
        for bid in batch_ids:
            all_results[bid] = ('', '')
        print(f'  ❌ 失败')

    time.sleep(1.5)

# 更新数据库的 summary_zh
conn = sqlite3.connect('db/news.db')
cur = conn.cursor()
count = 0
for art_id, (zh_title, zh_summary) in all_results.items():
    if zh_summary:
        cur.execute('UPDATE summaries SET summary_zh = ? WHERE article_id = ?', (zh_summary, art_id))
        count += 1

conn.commit()
print(f'\n✅ 更新了 {count} 条中文摘要')
conn.close()