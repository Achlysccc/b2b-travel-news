#!/usr/bin/env python3
"""B2B 旅游分销网站 — 每日定时更新 pipeline
爬取 → AI摘要 → 修复urgency → 构建 → 部署 → 推送微信
"""
import os, sys, sqlite3, json, subprocess, time
from datetime import datetime, timezone, timedelta

PROJECT = "/home/user/workspace/b2b-hotel-news"
os.chdir(PROJECT)
sys.path.insert(0, PROJECT)

LOG_FILE = f"{PROJECT}/logs/$(date '+%Y-%m-%d').log"

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)

def run(cmd, timeout=300):
    log(f"▶ {cmd[:80]}")
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
    if r.stdout: print(r.stdout[:500], flush=True)
    if r.returncode != 0: print(f"⚠️ exit {r.returncode}: {r.stderr[:200]}", flush=True)
    return r.returncode == 0

# ── 1. 爬取 RSS ──────────────────────────────────────────
log("📡 爬取 RSS...")
run("python3 crawler.py", timeout=120)

# 检查是否有待处理文章
conn = sqlite3.connect(f"{PROJECT}/db/news.db")
pending = conn.execute("SELECT COUNT(*) FROM articles WHERE is_processed=0").fetchone()[0]
conn.close()
log(f"📊 待处理文章: {pending} 篇")

# ── 2. AI 摘要（仅处理未处理的文章）────────────────────
if pending > 0:
    log(f"🤖 AI 摘要（{pending}篇待处理）...")
    run(f"python3 create_summaries.py", timeout=600)
else:
    log("✅ 所有文章已有摘要，跳过 AI 处理")

# ── 3. 修复 urgency（时间驱动，非 AI） ─────────────────
log("🔧 修复 urgency 分类...")
try:
    conn = sqlite3.connect(f"{PROJECT}/db/news.db")
    conn.row_factory = sqlite3.Row
    from dateutil import parser as dtparser

    rows = conn.execute("""
        SELECT s.article_id, a.published_at
        FROM summaries s JOIN articles a ON s.article_id = a.id
    """).fetchall()

    def calc_urgency(published_at_str):
        try:
            dt = dtparser.parse(published_at_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            age = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
            if age < 2:   return 'breaking'
            elif age < 24: return 'today'
            else:          return 'normal'
        except:
            return 'normal'

    for r in rows:
        u = calc_urgency(r['published_at'])
        conn.execute('UPDATE summaries SET urgency=? WHERE article_id=?', (u, r['article_id']))
    conn.commit()
    conn.close()
    log("✅ urgency 修复完成")
except Exception as e:
    log(f"⚠️ urgency 修复失败: {e}")

# ── 4. 构建网站 ─────────────────────────────────────────
log("🏗️ 构建网站...")
try:
    from generator.site_builder import build_site
    build_site()
    log("✅ 网站构建完成")
except Exception as e:
    log(f"⚠️ build_site 失败: {e}")
    sys.exit(1)

# ── 5. 部署到 gh-pages ─────────────────────────────────
log("🚀 部署 gh-pages...")
DEPLOY_TMP = f"/tmp/gh-pages-pipeline-{int(time.time())}"

# 确保 gh-pages 存在
result = subprocess.run(
    "git ls-remote --heads origin gh-pages",
    shell=True, capture_output=True, text=True
)
has_gh_pages = bool(result.stdout.strip())

if has_gh_pages:
    run(f"git clone --branch gh-pages --single-branch git@github.com:Achlysccc/b2b-travel-news.git {DEPLOY_TMP}")
else:
    run(f"git clone git@github.com:Achlysccc/b2b-travel-news.git {DEPLOY_TMP}")
    subprocess.run("cd /tmp/gh-pages-pipeline && git checkout --orphan gh-pages", shell=True)

# 清理旧文件，复制新文件
subprocess.run(f"cd {DEPLOY_TMP} && git rm -rf . 2>/dev/null; cp -r {PROJECT}/output/* .", shell=True)

# 删除源代码文件（只留输出）
for dangerous in ["crawler.py", "create_summaries.py", "db", "generator",
                  "templates", "config", "logs", "push_summary.py",
                  "update.sh", "__pycache__", ".venv"]:
    subprocess.run(f"cd {DEPLOY_TMP} && rm -rf {dangerous}", shell=True)

subprocess.run(f"cd {DEPLOY_TMP} && git add -A", shell=True)
run(f"cd {DEPLOY_TMP} && git commit -m 'deploy: {datetime.now().strftime('%Y-%m-%d %H:%M')}'")
run(f"cd {DEPLOY_TMP} && git push origin gh-pages --force")
subprocess.run(f"rm -rf {DEPLOY_TMP}", shell=True)
log("✅ gh-pages 部署完成")

# ── 6. 微信摘要推送 ────────────────────────────────────
log("📲 生成微信摘要...")
try:
    result = subprocess.run(
        "python3 push_summary.py 2>&1",
        shell=True, capture_output=True, text=True, timeout=60
    )
    output = result.stdout
    idx = output.find("__HERMES_MSG__:")
    if idx >= 0:
        digest = output[idx + len("__HERMES_MSG__:"):].strip()
        # 通过 Hermes send_message 推送
        import urllib.request
        payload = json.dumps({
            "target": "weixin:o9cq80xwGKHnl3fKRfsjKqo3qteo@im.wechat",
            "message": digest
        }).encode()
        req = urllib.request.Request(
            "http://localhost:8765/api/send",
            data=payload, headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            log(f"📲 微信推送响应: {resp.read()[:100]}")
    else:
        log("⚠️ push_summary 无 __HERMES_MSG__ 输出")
except Exception as e:
    log(f"⚠️ 微信推送失败: {e}")

log(f"✅ 全部完成！https://achlysccc.github.io/b2b-travel-news/")