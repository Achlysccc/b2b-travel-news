import sqlite3
conn = sqlite3.connect('db/news.db')
cursor = conn.cursor()

print("=== 数据库状态 ===")
total = cursor.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
print(f"总文章数: {total}")

print("\n=== 数据来源 ===")
for row in cursor.execute("SELECT source_name, COUNT(*) FROM articles GROUP BY source_name ORDER BY 2 DESC"):
    print(f"  {row[0]}: {row[1]} articles")

print("\n=== 最新文章 ===")
for row in cursor.execute("SELECT published_at, title, source_name FROM articles ORDER BY published_at DESC LIMIT 10"):
    print(f"  {row[0]} | {row[2]} | {row[1][:60]}")

print("\n=== 站点构建文件 ===")
import os
output_files = []
for root, dirs, files in os.walk('output'):
    for f in files:
        if f.endswith('.html'):
            output_files.append(os.path.join(root, f))
print(f"生成的HTML文件数: {len(output_files)}")
for f in sorted(output_files)[:10]:
    print(f"  {f}")

conn.close()