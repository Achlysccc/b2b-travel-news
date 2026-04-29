"""内容处理模块 - AI摘要、分类、地区标签、时效标记（批量版）"""

import json
import logging
import os
import re
from datetime import datetime, timezone, timedelta

from db.database import get_db, get_unprocessed_articles, insert_summary

log = logging.getLogger(__name__)

LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://ark.cn-beijing.volces.com/api/coding/v3")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "ark-fab6076f-0a74-44f4-8a82-5afa9f73dee3-dfbf7")
LLM_MODEL = os.environ.get("LLM_MODEL", "glm-5.1")

SYSTEM_PROMPT = """你是B2B酒店分销行业的专业信息分析师。你将收到一组新闻，请逐一分析，输出JSON数组。

每条分析结果包含：
{
  "summary_zh": "中文摘要，50-80字，简洁客观，保留关键数字和公司名",
  "category": "分类: tech/ma/partnership/policy/personnel/data/market",
  "importance": "重要性1-5",
  "related_companies": "关联公司名，逗号分隔，最多5个"
}

分类说明：tech=技术产品, ma=并购融资, partnership=合作签约, policy=政策法规, personnel=人事变动, data=市场数据, market=市场趋势
重要性：5=行业地震级, 4=重要, 3=常规, 2=次要, 1=边缘

只输出JSON数组，不要任何解释文字。数组长度必须与输入新闻数量一致。"""


def call_llm(prompt: str, retries: int = 2) -> str:
    """调用 LLM API，带重试"""
    import requests as req
    import time

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LLM_API_KEY}",
    }

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]

    payload = {
        "model": LLM_MODEL,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 2000,
    }

    for attempt in range(retries + 1):
        try:
            resp = req.post(
                f"{LLM_BASE_URL}/chat/completions",
                headers=headers,
                json=payload,
                timeout=90
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            if attempt < retries:
                log.warning(f"LLM API retry {attempt+1}: {e}")
                time.sleep(3)
            else:
                log.error(f"LLM API failed after {retries+1} attempts: {e}")
                raise


def parse_llm_batch_response(text: str, expected_count: int) -> list[dict]:
    """解析批量 LLM 返回"""
    text = re.sub(r'^```json\s*', '', text)
    text = re.sub(r'^```\s*', '', text)
    text = re.sub(r'\s*```$', '', text)
    text = text.strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # 尝试提取 JSON 数组
        match = re.search(r'\[.*\]', text, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group())
            except json.JSONDecodeError:
                log.error(f"Cannot parse batch response: {text[:300]}")
                return [None] * expected_count
        else:
            log.error(f"No JSON array found: {text[:300]}")
            return [None] * expected_count

    if not isinstance(data, list):
        data = [data]

    valid_categories = ["tech", "ma", "partnership", "policy", "personnel", "data", "market"]
    results = []
    for item in data:
        if not isinstance(item, dict) or "summary_zh" not in item:
            results.append(None)
            continue

        if item.get("category") not in valid_categories:
            item["category"] = "market"
        try:
            item["importance"] = max(1, min(5, int(item.get("importance", 3))))
        except (ValueError, TypeError):
            item["importance"] = 3
        item.setdefault("related_companies", "")
        results.append(item)

    # 补齐长度
    while len(results) < expected_count:
        results.append(None)

    return results[:expected_count]


def determine_urgency(published_at: str | None, importance: int) -> str:
    if not published_at:
        return "normal"
    try:
        from dateutil import parser as dtparser
        dt = dtparser.parse(published_at)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        hours_ago = (now - dt).total_seconds() / 3600
        if hours_ago <= 2 and importance >= 4:
            return "breaking"
        elif hours_ago <= 24:
            return "today"
        return "normal"
    except Exception:
        return "normal"


def process_all(db_path: str = None, batch_size: int = 5):
    """批量处理未处理的文章"""
    conn = get_db(db_path)
    articles = get_unprocessed_articles(conn)

    if not articles:
        log.info("没有待处理的文章")
        conn.close()
        return 0

    total = len(articles)
    log.info(f"待处理文章: {total} 篇 (批量大小: {batch_size})")
    processed = 0
    failed = 0

    for batch_start in range(0, total, batch_size):
        batch = articles[batch_start:batch_start + batch_size]
        log.info(f"  批次 [{batch_start+1}-{batch_start+len(batch)}/{total}]")

        # 构建批量 prompt
        items_text = []
        for i, article in enumerate(batch):
            items_text.append(
                f"{i+1}. 标题: {article['title']}\n"
                f"   来源: {article.get('source_name', '')} ({article.get('lang', 'en')})\n"
                f"   {'原文: ' + article.get('summary_original', '')[:200] if article.get('summary_original') else ''}"
            )

        prompt = f"请分析以下{len(batch)}条B2B酒店分销行业新闻：\n\n" + "\n\n".join(items_text)

        try:
            response = call_llm(prompt)
            results = parse_llm_batch_response(response, len(batch))

            for article, result in zip(batch, results):
                if result:
                    urgency = determine_urgency(article.get("published_at"), result["importance"])
                    insert_summary(
                        conn,
                        article_id=article["id"],
                        summary_zh=result["summary_zh"],
                        category=result["category"],
                        importance=result["importance"],
                        urgency=urgency,
                        related_companies=result["related_companies"],
                    )
                    processed += 1
                else:
                    failed += 1
                    log.warning(f"  跳过: {article['title'][:50]}")

        except Exception as e:
            failed += len(batch)
            log.error(f"  批次处理失败: {e}")

        import time
        time.sleep(2)

    conn.close()
    log.info(f"处理完成: {processed} 篇成功, {failed} 篇失败")
    return processed
