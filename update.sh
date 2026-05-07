#!/bin/bash
# B2B 旅游分销 - 简化版更新脚本（无需外部依赖）

set -e
PROJECT_DIR="/home/user/workspace/b2b-hotel-news"
cd "$PROJECT_DIR"

echo "🚀 B2B 旅游分销 - 开始更新"
echo "📅 时间：$(date '+%Y-%m-%d %H:%M:%S')"

# 运行爬虫（抓取真实 RSS）
echo "📡 抓取真实新闻..."
python3 crawler.py

# 构建网站
echo "🏗️  构建网站..."
python3 -c "from generator.site_builder import build_site; build_site()"

# 推送到 master
echo "📤 推送到 GitHub..."
git add -A
if ! git diff --quiet || ! git diff --cached --quiet; then
    git commit -m "chore: auto update $(date '+%Y-%m-%d')"
    git push origin master
fi

# 部署到 gh-pages
echo "🚀 部署到 gh-pages..."
git checkout gh-pages
rm -rf *
cp -r output/* .
git add .
if ! git diff --quiet || ! git diff --cached --quiet; then
    git commit -m "deploy: $(date '+%Y-%m-%d %H:%M')"
    git push origin gh-pages --force
fi

git checkout master

echo ""
echo "✅ 完成！访问：https://achlysccc.github.io/b2b-travel-news/"
