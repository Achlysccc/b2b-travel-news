#!/bin/bash
# B2B酒店分销行业动态 - 完整更新脚本
set -e

PROJECT_DIR="/home/user/workspace/b2b-hotel-news"
cd "$PROJECT_DIR"

# 激活虚拟环境
source .venv/bin/activate

# 禁用 SSL 警告
export PYTHONWARNINGS="ignore:Unverified HTTPS request"

# Step 1: 采集
echo "=== $(date) 开始采集 ==="
.venv/bin/python3 -c "
import urllib3
urllib3.disable_warnings()
from collector.fetcher import collect_all
count = collect_all()
print(f'采集完成: {count} 篇新文章')
"

# Step 2: AI 处理
echo "=== $(date) 开始AI处理 ==="
.venv/bin/python3 -c "
import urllib3
urllib3.disable_warnings()
from processor.ai_processor import process_all
count = process_all('db/news.db', batch_size=5)
print(f'AI处理完成: {count} 篇')
"

# Step 3: 生成站点
echo "=== $(date) 开始生成站点 ==="
.venv/bin/python3 -c "
from generator.site_builder import build_site
output = build_site(
    config_path='config/settings.yaml',
    db_path='db/news.db',
    output_path='output',
)
print(f'站点已生成: {output}')
"

# Step 4: 清理过期数据（90天）
echo "=== $(date) 清理过期数据 ==="
.venv/bin/python3 -c "
from db.database import get_db
from datetime import datetime, timedelta
conn = get_db('db/news.db')
cutoff = (datetime.now() - timedelta(days=90)).isoformat()
r = conn.execute('DELETE FROM articles WHERE published_at < ?', (cutoff,))
conn.commit()
print(f'已清理 {r.rowcount} 条过期数据')
conn.close()
"

echo "=== $(date) 全部完成 ==="
