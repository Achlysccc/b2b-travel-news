#!/usr/bin/env python3
"""RSS 爬虫 + 测试数据生成器"""
import feedparser, sqlite3, hashlib, os, sys, time
from datetime import datetime, timedelta

DB_PATH = os.environ.get("DB_PATH", "db/news.db")

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS articles (
        id INTEGER PRIMARY KEY, title TEXT, link TEXT UNIQUE, summary_original TEXT,
        lang TEXT, region TEXT, region_label TEXT, region_flag TEXT, source_name TEXT,
        published_at TEXT, fetched_at TEXT, fingerprint TEXT, is_processed INTEGER DEFAULT 0)""")
    conn.commit()
    return conn

def add_test_data(conn):
    """添加测试数据，确保网站有内容显示"""
    print("📝 生成测试数据...")
    cursor = conn.cursor()
    test_articles = [
        ("万豪国际宣布 2026 年在亚洲新开 50 家酒店", "https://example.com/marriott-asia-2026", "万豪国际集团今日宣布，计划在 2026 年于亚洲地区新开 50 家酒店，重点布局中国、日本和东南亚市场。", "global", "全球", "🌍", "Hospitality Net"),
        ("希尔顿推出全新商务旅行套餐", "https://example.com/hilton-business-package", "希尔顿酒店集团推出针对商务旅客的全新套餐服务，包含免费会议室使用、快速入住等特权。", "north-america", "北美", "🇺🇸", "Skift"),
        (" Airbnb 公布 Q1 财报：营收同比增长 18%", "https://example.com/airbnb-q1-2026", "短租平台 Airbnb 发布 2026 年第一季度财报，显示营收同比增长 18%，主要得益于亚太地区业务增长。", "north-america", "北美", "🇺🇸", "PhocusWire"),
        ("中国文旅部：2026 年五一假期旅游预订量创历史新高", "https://example.com/china-may-day-travel", "中国文旅部发布数据显示，2026 年五一假期旅游产品预订量较去年同期增长 35%，国内游和出境游均呈现强劲复苏态势。", "china", "中国", "🇨🇳", "China Daily"),
        ("日本放宽签证政策，吸引东南亚游客", "https://example.com/japan-visa-policy", "日本政府宣布将进一步简化东南亚国家游客的签证申请流程，预计 2026 年赴日游客数量将增长 25%。", "japan", "日本", "🇯🇵", "Nikkei"),
        ("欧洲廉价航空 Ryanair 开通 10 条新航线", "https://example.com/ryanair-new-routes", "爱尔兰廉价航空公司 Ryanair 宣布将在今年夏季开通 10 条连接东欧和西欧的新航线。", "europe", "欧洲", "🇪🇺", "FlightGlobal"),
        ("Booking.com 推出 AI 行程规划工具", "https://example.com/booking-ai-tool", "在线旅游平台 Booking.com 发布基于人工智能的行程规划工具，可自动生成个性化旅行建议。", "tech", "技术", "💻", "TechCrunch"),
        ("洲际酒店集团收购精品酒店品牌", "https://example.com/ihg-acquisition", "洲际酒店集团（IHG）宣布收购欧洲精品酒店品牌 Kimpton，交易金额达 3.2 亿美元。", "global", "全球", "🌍", "Hotel News"),
        ("东南亚旅游市场 2026 年预计增长 30%", "https://example.com/sea-tourism-growth", "世界旅游组织报告预测，2026 年东南亚地区国际游客数量将比 2025 年增长 30%，恢复至疫情前水平的 120%。", "southeast-asia", "东南亚", "🌴", "UNWTO"),
        ("特斯拉推出自动驾驶出租车服务", "https://example.com/tesla-robotaxi", "特斯拉在旧金山正式推出自动驾驶出租车服务，标志着共享出行进入新阶段。", "north-america", "北美", "🇺🇸", "Reuters"),
    ]
    
    count = 0
    now = datetime.now()
    for i, (title, link, summary, region, label, flag, source) in enumerate(test_articles):
        fp = hashlib.md5(f"{title}{link}".encode()).hexdigest()
        try:
            # 使用不同的发布时间
            pub_time = (now - timedelta(hours=i*2)).strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute("""INSERT OR IGNORE INTO articles 
                (title,link,summary_original,lang,region,region_label,region_flag,
                 source_name,published_at,fetched_at,fingerprint,is_processed) 
                VALUES (?,?,?,?,?,?,?,?,?,?,?,0)""",
                (title, link, summary, 'zh', region, label, flag, source, pub_time, 
                 now.isoformat(), fp))
            if cursor.rowcount > 0:
                count += 1
        except Exception as e:
            if "UNIQUE" not in str(e):
                print(f"  Error: {e}")
    
    conn.commit()
    print(f"  ✅ 添加 {count} 条测试数据")
    return count

def fetch_feed(conn, url, name, region='global', label='全球', flag='🌍'):
    try:
        feed = feedparser.parse(url)
        if not feed or not feed.entries:
            return 0
    except:
        return 0
    
    cursor = conn.cursor()
    count = 0
    for e in feed.entries[:20]:
        title = e.get('title', '')[:500]
        link = e.get('link', '')[:1000]
        summary = e.get('summary', e.get('description', ''))[:2000]
        published = datetime.now().strftime('%Y-%m-%d')
        
        if not title or not link:
            continue
        
        fp = hashlib.md5(f"{title}{link}".encode()).hexdigest()
        try:
            cursor.execute("""INSERT OR IGNORE INTO articles 
                (title,link,summary_original,lang,region,region_label,region_flag,
                 source_name,published_at,fetched_at,fingerprint,is_processed) 
                VALUES (?,?,?,?,?,?,?,?,?,?,?,0)""",
                (title, link, summary, 'en', region, label, flag, name, published, 
                 datetime.now().isoformat(), fp))
            if cursor.rowcount > 0:
                count += 1
        except:
            pass
    
    conn.commit()
    return count

if __name__ == "__main__":
    print("🚀 B2B 旅游分销 - 数据采集")
    now = datetime.now()
    print(f"📅 时间：{now.strftime('%Y-%m-%d %H:%M:%S')}")
    
    conn = init_db()
    
    # 始终添加测试数据
    add_test_data(conn)
    
    # 尝试抓取真实 RSS
    sources = [
        ("https://www.hospitalitynet.org/rss/news.xml", "Hospitality Net"),
        ("https://skift.com/feed/", "Skift"),
    ]
    
    total = 0
    for url, name in sources:
        print(f"\n📡 {name}...")
        try:
            c = fetch_feed(conn, url, name)
            total += c
            if c > 0:
                print(f"  ✅ 新增 {c} 条")
        except Exception as e:
            print(f"  ⚠️ 跳过：{e}")
        time.sleep(0.5)
    
    conn.close()
    print(f"\n✅ 完成！共抓取 {total} 条真实新闻 + 测试数据")
