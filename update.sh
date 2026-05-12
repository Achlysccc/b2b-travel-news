#!/bin/bash
# B2B 旅游分销 - 更新脚本
# 抓取 RSS → 构建网站 → 部署到 gh-pages

set -e
PROJECT_DIR="/home/user/workspace/b2b-hotel-news"
cd "$PROJECT_DIR"

# 确保在 master 分支
git checkout master 2>/dev/null || true

# 使用 venv Python（dependencies 已安装）
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

# 2. 构建网站
echo "🏗️  构建网站..."
python3 -c "
import sys
sys.path.insert(0, '.')
from generator.site_builder import build_site
build_site()
"

# 3. 推送到 master（排除 output/ 和 logs/）
echo "📤 推送到 GitHub..."
git add -A
# Remove output/ and logs/ from staging to avoid pushing build artifacts to master
git reset HEAD output/ logs/ 2>/dev/null || true
if ! git diff --quiet || ! git diff --cached --quiet; then
    git commit -m "chore: auto update $(date '+%Y-%m-%d')"
    git push origin master
fi

# 4. 部署到 gh-pages（clean 方式：只放构建产物）
echo "🚀 部署到 gh-pages..."

# 临时保存 output 路径
OUTPUT_DIR="$PROJECT_DIR/output"

# 切换到 gh-pages，删除所有文件
git checkout gh-pages 2>/dev/null || git checkout --orphan gh-pages
git rm -rf . 2>/dev/null || true

# 复制构建产物到根目录
cp -r "$OUTPUT_DIR/"* .
# 删除 output 目录本身（已复制到根目录）
rm -rf "$OUTPUT_DIR"

# 提交并推送
git add -A
git commit -m "deploy: $(date '+%Y-%m-%d %H:%M')" || true
git push origin gh-pages --force

# 切回 master
git checkout master

echo ""
echo "✅ 完成！访问：https://achlysccc.github.io/b2b-travel-news/"
