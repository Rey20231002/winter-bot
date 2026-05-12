#!/usr/bin/env python3
"""
Bilibili Winter (金冬天) 语录爬取工具

从 B 站视频中提取 Winter 相关的字幕和语录，用于扩充知识库。

用法:
    # 从单个 BV 号爬取
    python scrape_bilibili.py --bv BV1wJXJBdEfk

    # 从多个 BV 号批量爬取
    python scrape_bilibili.py --bv BV1wJXJBdEfk,BV1Xb421q7Sb,BV12Q4y1B7uc

    # 从包含 BV 号列表的文件读取
    python scrape_bilibili.py --file winter_videos.txt

    # 输出到指定文件
    python scrape_bilibili.py --bv BV1wJXJBdEfk --output winter_new_quotes.md

    # 交互式搜索并爬取 Winter 相关视频
    python scrape_bilibili.py --search "aespa Winter 采访"

依赖:
    pip install httpx yt-dlp pysrt

注意:
    - B 站字幕需要视频本身有 CC 字幕（人工或自动生成）
    - 如果没有字幕，此脚本无法提取文本
    - 请遵守 B 站用户协议，合理使用
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Optional

try:
    import httpx
except ImportError:
    print("请先安装 httpx: pip install httpx")
    sys.exit(1)

try:
    import pysrt
except ImportError:
    print("⚠️  pysrt 未安装，SRT 字幕解析功能不可用")
    print("   安装: pip install pysrt")

# ============================================================
# 配置
# ============================================================

# B 站 API 端点
BILIBILI_API_VIDEO_INFO = "https://api.bilibili.com/x/web-interface/view"
BILIBILI_API_SUBTITLE = "https://api.bilibili.com/x/player/v2"
BILIBILI_API_SEARCH = "https://api.bilibili.com/x/web-interface/search/type"
BILIBILI_VIDEO_URL = "https://www.bilibili.com/video/{}"

# 请求头（模拟浏览器）
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.bilibili.com/",
}

# Winter 相关关键词（用于匹配字幕中的 Winter 台词）
WINTER_KEYWORDS_CN = [
    "冬天", "金冬天", "冬冬", "玟庭", "旼炡",  # 中文称呼
]

WINTER_KEYWORDS_KR = [
    "윈터", "Winter", "winter", "민정", "김민정",  # 韩语/英文称呼
]

# 合并所有关键词
ALL_WINTER_KEYWORDS = WINTER_KEYWORDS_CN + WINTER_KEYWORDS_KR

# 搜索关键词建议（用于 --search 命令）
WINTER_SEARCH_QUERIES = [
    "aespa Winter 采访",
    "aespa 金冬天 综艺",
    "Winter 直播 语录",
    "aespa 冬天 高光",
    "Winter 金旼炡 剪辑",
    "aespa Winter 讲中文",
    "aespa Winter Bubble",
]


def get_video_info(bv: str) -> Optional[dict]:
    """获取 B 站视频信息"""
    params = {"bvid": bv}
    try:
        with httpx.Client(headers=HEADERS, timeout=30) as client:
            resp = client.get(BILIBILI_API_VIDEO_INFO, params=params)
            data = resp.json()

            if data["code"] != 0:
                print(f"  ⚠️  API 返回错误: {data.get('message', '未知错误')}")
                return None

            video_data = data["data"]
            return {
                "bvid": bv,
                "title": video_data["title"],
                "description": video_data.get("desc", ""),
                "duration": video_data.get("duration", 0),
                "owner": video_data.get("owner", {}).get("name", ""),
                "aid": video_data.get("aid", 0),
                "cid": video_data.get("cid", 0),
                "url": BILIBILI_VIDEO_URL.format(bv),
            }
    except Exception as e:
        print(f"  ❌ 获取视频信息失败: {e}")
        return None


def get_subtitle_info(aid: int, cid: int) -> Optional[dict]:
    """获取 B 站视频的字幕信息"""
    params = {"aid": aid, "cid": cid}
    try:
        with httpx.Client(headers=HEADERS, timeout=30) as client:
            resp = client.get(BILIBILI_API_SUBTITLE, params=params)
            data = resp.json()

            if data["code"] != 0:
                return None

            subtitle_data = data.get("data", {}).get("subtitle", {})
            if not subtitle_data:
                return None

            subtitles = subtitle_data.get("subtitles", [])
            if not subtitles:
                return None

            # 优先选择中文(自动生成) > 中文(人工) > 第一个可用字幕
            for sub in subtitles:
                lang = sub.get("lan_doc", "").lower()
                if "中文" in lang or "chinese" in lang or "zh" in lang:
                    return {
                        "subtitle_url": "https:" + sub["subtitle_url"]
                        if sub["subtitle_url"].startswith("//")
                        else sub["subtitle_url"],
                        "language": sub.get("lan_doc", ""),
                    }

            # 返回第一个可用的字幕
            first_sub = subtitles[0]
            return {
                "subtitle_url": "https:" + first_sub["subtitle_url"]
                if first_sub["subtitle_url"].startswith("//")
                else first_sub["subtitle_url"],
                "language": first_sub.get("lan_doc", ""),
            }

    except Exception as e:
        print(f"  ❌ 获取字幕信息失败: {e}")
        return None


def download_subtitle(subtitle_url: str) -> Optional[str]:
    """下载并解析 B 站 JSON 格式字幕"""
    try:
        with httpx.Client(headers=HEADERS, timeout=30) as client:
            resp = client.get(subtitle_url)
            data = resp.json()

            # B 站字幕格式: {"body": [{"from": 0.0, "to": 1.0, "content": "text"}, ...]}
            if isinstance(data, dict) and "body" in data:
                lines = []
                for item in data["body"]:
                    content = item.get("content", "").strip()
                    if content:
                        # 秒转时间戳
                        start_sec = item.get("from", 0)
                        end_sec = item.get("to", 0)
                        start_ts = f"{int(start_sec//60):02d}:{start_sec%60:05.2f}"
                        lines.append(f"[{start_ts}] {content}")
                return "\n".join(lines)

            return None

    except Exception as e:
        print(f"  ❌ 下载字幕失败: {e}")
        return None


def extract_winter_lines(subtitle_text: str) -> list[dict]:
    """从字幕文本中提取 Winter 相关的台词

    策略:
    1. 先找包含 Winter 关键词的附近几行（上下文）
    2. 尝试识别说话人标注（如"Winter："、"金冬天："）
    3. 返回提取到的台词及其时间戳
    """
    lines = subtitle_text.split("\n")
    extracted = []

    timestamp_pattern = re.compile(r"^\[(\d{2}:\d{2}\.\d{2})\]\s*(.*)")

    for i, line in enumerate(lines):
        match = timestamp_pattern.match(line)
        if not match:
            continue

        timestamp = match.group(1)
        content = match.group(2)

        # 检查是否包含 Winter 关键词
        if any(kw.lower() in content.lower() for kw in ALL_WINTER_KEYWORDS):
            # 获取上下文（前后各2行）
            context_before = []
            context_after = []

            for j in range(max(0, i - 2), i):
                cm = timestamp_pattern.match(lines[j])
                if cm:
                    context_before.append(f"[{cm.group(1)}] {cm.group(2)}")

            for j in range(i + 1, min(len(lines), i + 3)):
                cm = timestamp_pattern.match(lines[j])
                if cm:
                    context_after.append(f"[{cm.group(1)}] {cm.group(2)}")

            extracted.append(
                {
                    "timestamp": timestamp,
                    "content": content,
                    "context_before": context_before,
                    "context_after": context_after,
                }
            )

    return extracted


def format_quotes_markdown(video_info: dict, quotes: list[dict]) -> str:
    """将提取的语录格式化为 Markdown"""
    if not quotes:
        return f"## {video_info['title']}\n\n来源: {video_info['url']}\n\n_[未提取到 Winter 相关语录]_\n\n---\n"

    md = f"## {video_info['title']}\n\n"
    md += f"- **UP主**: {video_info['owner']}\n"
    md += f"- **时长**: {video_info['duration']//60}分{video_info['duration']%60}秒\n"
    md += f"- **链接**: {video_info['url']}\n\n"

    for i, quote in enumerate(quotes, 1):
        md += f"### 语录 {i} (时间戳: {quote['timestamp']})\n\n"

        if quote["context_before"]:
            md += "```\n上下文:\n"
            for ctx in quote["context_before"]:
                md += f"  {ctx}\n"
            md += "```\n\n"

        md += f"> {quote['content']}\n\n"

        if quote["context_after"]:
            md += "```\n后续:\n"
            for ctx in quote["context_after"]:
                md += f"  {ctx}\n"
            md += "```\n\n"

        md += "---\n\n"

    return md


def search_winter_videos(query: str, limit: int = 20) -> list[str]:
    """搜索 Winter 相关的 B 站视频，返回 BV 号列表"""
    params = {
        "search_type": "video",
        "keyword": query,
        "page": 1,
    }
    try:
        with httpx.Client(headers=HEADERS, timeout=30) as client:
            resp = client.get(BILIBILI_API_SEARCH, params=params)
            data = resp.json()

            if data["code"] != 0:
                print(f"  ⚠️  搜索失败: {data.get('message', '')}")
                return []

            results = data.get("data", {}).get("result", [])
            bv_list = []

            for video in results[:limit]:
                bvid = video.get("bvid", "")
                title = video.get("title", "").replace("<em>", "").replace("</em>", "")
                play = video.get("play", 0)
                if bvid:
                    bv_list.append(bvid)
                    print(f"  📺 [{bvid}] {title[:60]}... (播放:{play})")

            return bv_list

    except Exception as e:
        print(f"  ❌ 搜索失败: {e}")
        return []


def scrape_single_video(bv: str, output_dir: Path) -> Optional[str]:
    """处理单个视频：获取信息 → 下载字幕 → 提取台词"""
    print(f"\n{'='*60}")
    print(f"📹 处理视频: {bv}")

    # 1. 获取视频信息
    video_info = get_video_info(bv)
    if not video_info:
        return None

    print(f"  标题: {video_info['title']}")
    print(f"  UP主: {video_info['owner']}")

    # 2. 获取字幕
    subtitle_info = get_subtitle_info(video_info["aid"], video_info["cid"])
    if not subtitle_info:
        print(f"  ⚠️  该视频没有字幕，跳过")
        return None

    print(f"  字幕语言: {subtitle_info['language']}")

    # 3. 下载字幕
    subtitle_text = download_subtitle(subtitle_info["subtitle_url"])
    if not subtitle_text:
        print(f"  ⚠️  字幕下载失败，跳过")
        return None

    print(f"  字幕长度: {len(subtitle_text)} 字符")

    # 4. 提取 Winter 相关台词
    quotes = extract_winter_lines(subtitle_text)
    print(f"  提取到: {len(quotes)} 条 Winter 相关语录")

    # 5. 格式化为 Markdown
    markdown = format_quotes_markdown(video_info, quotes)

    # 6. 保存
    safe_title = re.sub(r'[\\/:*?"<>|]', "_", video_info["title"])[:50]
    output_file = output_dir / f"scraped_{bv}_{safe_title}.md"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(markdown)

    print(f"  ✅ 已保存到: {output_file}")
    return str(output_file)


def main():
    parser = argparse.ArgumentParser(
        description="BiliBili Winter (金冬天) 语录爬取工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python scrape_bilibili.py --bv BV1wJXJBdEfk
  python scrape_bilibili.py --bv BV1wJXJBdEfk,BV1Xb421q7Sb
  python scrape_bilibili.py --search "aespa Winter 采访"
  python scrape_bilibili.py --search-all
  python scrape_bilibili.py --file winter_videos.txt --output winter_new_quotes.md
        """,
    )

    parser.add_argument(
        "--bv",
        type=str,
        help="B站视频 BV 号，多个用逗号分隔",
    )
    parser.add_argument(
        "--file",
        type=str,
        help="包含 BV 号列表的文本文件（每行一个 BV 号）",
    )
    parser.add_argument(
        "--search",
        type=str,
        help="搜索关键词",
    )
    parser.add_argument(
        "--search-limit",
        type=int,
        default=10,
        help="搜索结果数量限制 (默认: 10)",
    )
    parser.add_argument(
        "--search-all",
        action="store_true",
        help="使用预设关键词批量搜索 Winter 相关视频",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="合并输出文件路径",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./scraped",
        help="单个视频的输出目录 (默认: ./scraped)",
    )

    args = parser.parse_args()

    # 创建输出目录
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    all_bvs = []

    # 收集 BV 号
    if args.bv:
        all_bvs.extend([bv.strip() for bv in args.bv.split(",") if bv.strip()])

    if args.file:
        file_path = Path(args.file)
        if file_path.exists():
            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    bv = line.strip()
                    if bv and not bv.startswith("#"):
                        # 支持直接 URL 和纯 BV 号
                        match = re.search(r"BV[a-zA-Z0-9]+", bv)
                        if match:
                            all_bvs.append(match.group(0))

    if args.search:
        print(f"\n🔍 搜索: {args.search}")
        bvs = search_winter_videos(args.search, args.search_limit)
        all_bvs.extend(bvs)

    if args.search_all:
        print("\n🔍 批量搜索 Winter 相关视频...")
        for query in WINTER_SEARCH_QUERIES:
            print(f"\n  搜索: {query}")
            bvs = search_winter_videos(query, max(3, args.search_limit // len(WINTER_SEARCH_QUERIES)))
            all_bvs.extend(bvs)
            time.sleep(1)  # 避免请求过快

    # 去重
    all_bvs = list(dict.fromkeys(all_bvs))  # 保持顺序去重

    if not all_bvs:
        print("\n❌ 没有指定任何视频")
        print("请使用 --bv, --file, --search, 或 --search-all 指定视频")
        sys.exit(1)

    print(f"\n📊 共 {len(all_bvs)} 个视频待处理")

    # 处理每个视频
    all_markdown_parts = []
    success_count = 0

    for bv in all_bvs:
        result = scrape_single_video(bv, output_dir)
        if result:
            success_count += 1
            with open(result, "r", encoding="utf-8") as f:
                all_markdown_parts.append(f.read())
        time.sleep(0.5)  # 请求间隔

    # 合并输出
    if args.output and all_markdown_parts:
        merged_file = Path(args.output)
        with open(merged_file, "w", encoding="utf-8") as f:
            f.write("# Winter (金冬天) B站语录合集\n\n")
            f.write(f"自动提取时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write("---\n\n")
            f.write("\n\n".join(all_markdown_parts))

        print(f"\n✅ 合并输出已保存到: {merged_file}")

    # 总结
    print(f"\n{'#'*60}")
    print(f"# 爬取完成: {success_count}/{len(all_bvs)} 个视频成功")
    print(f"{'#'*60}")

    if success_count == 0:
        print("\n💡 提示:")
        print("  - B站字幕功能需要视频本身有CC字幕（人工或自动生成）")
        print("  - 很多视频没有字幕功能，建议优先找标注了'字幕'或'CC'的视频")
        print("  - 可以先用 --search 搜索 'aespa Winter 中字' 来找到有字幕的视频")
        print("  - 或者手工观看视频后手动转录到 knowledge_base/winter_quotes.md")


if __name__ == "__main__":
    main()
