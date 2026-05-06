import sqlite3

conn = sqlite3.connect('db/news.db')
cursor = conn.cursor()

# 更新摘要信息，使其能在首页显示
updates = [
    (1, 'tech', 4, 'breaking'),  # 万豪 - 高重要性，突发
    (2, 'tech', 4, 'today'),     # 希尔顿 - 高重要性，今日
    (3, 'market', 4, 'today'),   # Airbnb - 高重要性，今日
    (4, 'market', 5, 'breaking'),# 五一旅游 - 最高重要性，突发
    (5, 'market', 4, 'today'),   # 日本签证 - 高重要性，今日
]

for aid, cat, imp, urg in updates:
    cursor.execute("""
        UPDATE summaries 
        SET category=?, importance=?, urgency=?
        WHERE article_id=?
    """, (cat, imp, urg, aid))
    
    # 同时更新 articles 表
    cursor.execute("UPDATE articles SET is_processed=1 WHERE id=?", (aid,))

conn.commit()
print("✅ 更新完成")

# 验证
rows = cursor.execute('SELECT a.id, a.title, s.category, s.importance, s.urgency FROM articles a JOIN summaries s ON a.id = s.article_id').fetchall()
print("\\n更新后：")
for r in rows:
    print(f"  {r[0]}: {r[1][:10]}... | cat={r[2]} | imp={r[3]} | urg={r[4]}")

conn.close()
