import sqlite3
conn = sqlite3.connect('db/news.db')
cursor = conn.cursor()

print("=== 当前数据库状态 ===")
articles = cursor.execute("SELECT id, title, is_processed FROM articles").fetchall()
print(f"总文章数：{len(articles)}")

summaries = cursor.execute("SELECT COUNT(*) FROM summaries").fetchone()[0]
print(f"摘要数：{summaries}")

sample = cursor.execute("SELECT article_id, summary_zh, category, importance, urgency FROM summaries LIMIT 1").fetchone()
if sample:
    print(f"示例摘要：article_id={sample[0]}, category={sample[2]}, importance={sample[3]}, urgency={sample[4]}")

print("\n=== 所有文章 ===")
rows = cursor.execute("""
    SELECT a.id, a.title, a.region, a.region_label, a.region_flag, s.summary_zh, s.category, s.importance, s.urgency
    FROM articles a
    JOIN summaries s ON a.id = s.article_id
""").fetchall()

for r in rows:
    print(f"{r[0]}: {r[1][:20]}... | region={r[2]}/{r[3]} | category={r[6]} | importance={r[7]} | urgency={r[8]}")

conn.close()
