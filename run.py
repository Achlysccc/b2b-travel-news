"""主流程脚本 - 串联 采集 → 处理 → 生成"""

import logging
import os
import sys
from pathlib import Path

# 将项目根目录加入 path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("run")


def main():
    log.info("=" * 60)
    log.info("B2B酒店分销行业动态 - 开始更新")
    log.info("=" * 60)

    # ── Step 1: 采集 ──
    log.info("\n>>> Step 1: 数据采集")
    try:
        from collector.fetcher import collect_all
        new_count = collect_all(
            config_path=str(PROJECT_ROOT / "config" / "sources.yaml"),
            db_path=str(PROJECT_ROOT / "db" / "news.db"),
        )
        log.info(f"采集完成，新增 {new_count} 篇")
    except Exception as e:
        log.error(f"采集阶段出错: {e}", exc_info=True)

    # ── Step 2: AI 处理 ──
    log.info("\n>>> Step 2: AI 内容处理")
    try:
        from processor.ai_processor import process_all
        processed = process_all(db_path=str(PROJECT_ROOT / "db" / "news.db"))
        log.info(f"处理完成，已处理 {processed} 篇")
    except Exception as e:
        log.error(f"处理阶段出错: {e}", exc_info=True)

    # ── Step 3: 生成站点 ──
    log.info("\n>>> Step 3: 生成静态站点")
    try:
        from generator.site_builder import build_site
        output = build_site(
            config_path=str(PROJECT_ROOT / "config" / "settings.yaml"),
            db_path=str(PROJECT_ROOT / "db" / "news.db"),
            output_path=str(PROJECT_ROOT / "output"),
        )
        log.info(f"站点已生成: {output}")
    except Exception as e:
        log.error(f"生成阶段出错: {e}", exc_info=True)

    # ── Step 4: 清理过期数据 ──
    log.info("\n>>> Step 4: 清理过期数据")
    try:
        from db.database import get_db, cleanup_old_data
        conn = get_db(str(PROJECT_ROOT / "db" / "news.db"))
        cleanup_old_data(conn, retention_days=90)
        conn.close()
        log.info("清理完成")
    except Exception as e:
        log.error(f"清理阶段出错: {e}", exc_info=True)

    log.info("\n" + "=" * 60)
    log.info("更新完成！")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
