#!/bin/bash
# B2B 旅游分销 - 更新脚本
# 抓取 RSS → AI摘要 → 构建网站 → 部署到 gh-pages → 推送中文概览

set -e
PROJECT_DIR="/home/user/workspace/b2b-hotel-news"
cd "$PROJECT_DIR"

git checkout master 2>/dev/null || true

export PATH="$PROJECT_DIR/.venv/bin:$PATH"
export PYTHONPATH="$PROJECT_DIR/.venv/lib/python3.11/site-packages:$PYTHONPATH"

echo "🚀 B2B 旅游分销 - 开始更新"
echo "📅 时间：$(date '+%Y-%m-%d %H:%M:%S')"

# 记录日志
LOG_FILE="$PROJECT_DIR/logs/$(date '+%Y-%m-%d').log"
exec > >(tee -a "$LOG_FILE") 2>&1

# 1. 抓取 RSS
echo "📡 抓取新闻..."
python3 crawler.py

# 2. AI 摘要生成
echo "🤖 生成 AI 摘要..."
python3 create_summaries.py

# 3. 构建网站
echo "🏗️  构建网站..."
python3 -c "
import sys
sys.path.insert(0, '.')
from generator.site_builder import build_site
build_site()
"

# 4. 推送到 GitHub master
echo "📤 推送到 GitHub..."
git add -A
git reset HEAD output/ logs/ 2>/dev/null || true
if ! git diff --quiet || ! git diff --cached --quiet; then
    git commit -m "chore: auto update $(date '+%Y-%m-%d')"
    git push origin master
fi

# 5. 部署到 gh-pages（独立 clone 方式）
echo "🚀 部署到 gh-pages..."
DEPLOY_DIR="/tmp/gh-pages-deploy-$(date '+%s')"
git clone --branch gh-pages --single-branch git@github.com:Achlysccc/b2b-travel-news.git "$DEPLOY_DIR"
cd "$DEPLOY_DIR"
git rm -rf . 2>/dev/null || true
cp -r "$PROJECT_DIR/output/"* .
git add -A
git commit -m "deploy: $(date '+%Y-%m-%d %H:%M')"
git push origin gh-pages
cd "$PROJECT_DIR"
rm -rf "$DEPLOY_DIR"

# 6. 推送中文概览到 WeChat
echo "📲 推送中文概览到 WeChat..."
SUMMARY_OUTPUT=$(python3 push_summary.py 2>&1)
echo "$SUMMARY_OUTPUT"

# 从输出中提取 __HERMES_MSG__ 后的内容
DIGEST=$(echo "$SUMMARY_OUTPUT" | sed -n '/__HERMES_MSG__:/,$p' | sed 's/__HERMES_MSG__://')

if [ -n "$DIGEST" ]; then
    # 通过 Hermes API 推送
    ESCAPED=$(echo "$DIGEST" | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read()))')
    curl -s -X POST "http://localhost:8765/api/send" \
        -H "Content-Type: application/json" \
        -d "{\"target\": \"weixin:o9cq80xwGKHnl3fKRfsjKqo3qteo@im.wechat\", \"message\": $ESCAPED}" \
        2>&1 || echo "⚠️ WeChat 推送失败（可能 Hermes API 未启动）"
fi

echo ""
echo "✅ 完成！访问：https://achlysccc.github.io/b2b-travel-news/"
