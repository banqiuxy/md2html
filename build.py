#!/usr/bin/env python3
"""通用 Markdown 转 HTML 阅读器。

读取 content 目录下的 .md 文件（支持单个文件、单个文件切分为多章、
或整个目录按文件名排序合并），把正文与书籍信息内嵌进 index_template.html，
生成 index.generated.html。不修改模板和任何 Markdown 原文。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_TEMPLATE = BASE_DIR / "index_template.html"
DEFAULT_OUTPUT = BASE_DIR / "index.generated.html"
DEFAULT_CONTENT_DIR = BASE_DIR / "content"
DEFAULT_CONFIG = BASE_DIR / "book.json"

MARKDOWN_SUFFIXES = {".md", ".markdown", ".mdown", ".txt"}
# 目录内需要忽略的文件，避免把说明文档当成正文。
IGNORED_NAMES = {"readme.md", "book.json", "book.md"}

CHAPTER_SPLIT_PATTERN = re.compile(r"^(#{1,2})\s+(.+)$", re.MULTILINE)
PLACEHOLDER_PATTERN = re.compile(r"\{\{([A-Z_]+)\}\}")
SAFE_TOKEN = re.compile(r"^[A-Za-z0-9_]+$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="把 Markdown 内容转成单文件 HTML 阅读器，不修改模板和原文。"
    )
    parser.add_argument(
        "--content",
        type=Path,
        default=None,
        help="Markdown 文件或目录；默认读取 content 目录",
    )
    parser.add_argument(
        "--template",
        type=Path,
        default=DEFAULT_TEMPLATE,
        help=f"页面模板，默认：{DEFAULT_TEMPLATE.name}",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"生成文件，默认：{DEFAULT_OUTPUT.name}",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help=f"书籍信息配置，默认：{DEFAULT_CONFIG.name}",
    )
    parser.add_argument(
        "--title",
        default=None,
        help="书名，覆盖配置文件",
    )
    parser.add_argument(
        "--description",
        default=None,
        help="简介，覆盖配置文件",
    )
    parser.add_argument(
        "--eyebrow",
        default=None,
        help="侧栏顶部小字，覆盖配置文件",
    )
    parser.add_argument(
        "--split",
        action="store_true",
        help="按每个文件的一级/二级标题拆分为多章",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="允许覆盖已存在的输出文件",
    )
    return parser.parse_args()


def read_text(path: Path) -> str:
    try:
        # utf-8-sig 同时兼容普通 UTF-8 与带 BOM 的 UTF-8。
        return path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError(f"{path.name} 不是有效的 UTF-8 文件，请转换编码后重试") from error


def load_config(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        data = json.loads(read_text(path))
    except json.JSONDecodeError as error:
        raise ValueError(f"{path.name} 不是合法的 JSON：{error}") from error
    if not isinstance(data, dict):
        raise ValueError(f"{path.name} 顶层必须是对象")
    return {str(key): str(value) for key, value in data.items() if value is not None}


def collect_markdown_files(target: Path) -> list[Path]:
    if target.is_file():
        return [target]
    if not target.is_dir():
        raise ValueError(f"内容路径不存在：{target}")

    files = [
        path
        for path in sorted(target.iterdir(), key=lambda p: p.name)
        if path.is_file()
        and path.suffix.lower() in MARKDOWN_SUFFIXES
        and path.name.lower() not in IGNORED_NAMES
    ]
    if not files:
        raise ValueError(f"{target} 中没有找到 Markdown 文件")
    return files


def split_into_chapters(content: str, source_name: str) -> list[dict[str, str]]:
    """按一级或二级标题把单个文件切成若干章节。

    切片保持原始边界且不做裁剪，拼接后可还原原文，便于生成后校验。
    """
    matches = list(CHAPTER_SPLIT_PATTERN.finditer(content))
    if len(matches) < 2:
        return []

    chapters: list[dict[str, str]] = []
    preamble = content[: matches[0].start()]
    if preamble.strip():
        chapters.append(
            {
                "id": f"{source_name}-intro",
                "name": source_name,
                "content": preamble,
            }
        )
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
        body = content[start:end]
        if not body.strip():
            continue
        chapters.append(
            {
                "id": f"{source_name}-{index + 1}",
                "name": source_name,
                "content": body,
            }
        )
    return chapters


def build_chapters(files: list[Path], split: bool) -> list[dict[str, str]]:
    chapters: list[dict[str, str]] = []
    for path in files:
        content = read_text(path)
        if not content.strip():
            raise ValueError(f"{path.name} 是空文件，已停止生成")
        if split:
            parts = split_into_chapters(content, path.name)
            if parts:
                chapters.extend(parts)
                continue
        chapters.append(
            {"id": path.stem, "name": path.name, "content": content}
        )
    if not chapters:
        raise ValueError("没有可用的正文")
    return chapters


def encode_json(payload: object) -> str:
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    # 防止正文中的 </script> 提前闭合脚本；解析 JSON 后会还原为原字符。
    return text.replace("<", "\\u003c").replace(" ", "\\u2028").replace(" ", "\\u2029")


def fill_template(template: str, chapters: list[dict[str, str]], book: dict[str, str]) -> str:
    values = {
        "BOOK_TITLE": book.get("title", "未命名文档"),
        "BOOK_DESCRIPTION": book.get("description", ""),
        "BOOK_EYEBROW": book.get("eyebrow", "文档"),
        "BOOK_DATA": encode_json(book),
        "NOVEL_DATA": encode_json(chapters),
    }

    def substitute(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in values:
            raise ValueError(f"模板中存在未知占位符：{key}")
        return values[key]

    # 先校验模板里出现的占位符都在已知范围内；替换后的正文可能含有同形文本，不能再全篇扫描。
    for name in set(PLACEHOLDER_PATTERN.findall(template)):
        if name not in values:
            raise ValueError(f"模板中存在未知占位符：{name}")

    filled = PLACEHOLDER_PATTERN.sub(substitute, template)
    return filled


def verify_output(output: Path, chapters: list[dict[str, str]], sources: dict[str, str]) -> None:
    generated = read_text(output)
    match = re.search(
        r'<script\b[^>]*id="novel-data"[^>]*>(.*?)</script\s*>',
        generated,
        re.IGNORECASE | re.DOTALL,
    )
    if not match:
        raise ValueError("生成后的 HTML 缺少 novel-data 数据块")
    embedded = json.loads(match.group(1))
    if len(embedded) != len(chapters):
        raise ValueError("生成后的章节数量不一致")

    for item, chapter in zip(embedded, chapters):
        if item.get("name") != chapter["name"]:
            raise ValueError(f"生成后的文件名不匹配：{chapter['name']}")
        if item.get("content") != chapter["content"]:
            raise ValueError(f"生成后的正文与原文不一致：{chapter['name']}")

    # 逐个源文件核对：同一文件的所有片段拼起来应与原文一致（仅首尾空白被裁剪）。
    grouped: dict[str, list[str]] = {}
    for item in embedded:
        grouped.setdefault(item.get("name", ""), []).append(item.get("content", ""))
    for name, original in sources.items():
        rebuilt = "".join(grouped.get(name, []))
        if original.strip() != rebuilt.strip():
            raise ValueError(f"原文未完整写入生成文件：{name}")


def main() -> int:
    args = parse_args()
    template_path = args.template.resolve()
    output_path = args.output.resolve()
    content_target = (
        args.content.resolve()
        if args.content
        else DEFAULT_CONTENT_DIR.resolve()
    )

    try:
        if template_path == output_path:
            raise ValueError("输出文件不能与模板相同；本脚本不会覆盖 index_template.html")
        if output_path.suffix.lower() not in {".html", ".htm"}:
            raise ValueError("输出文件必须使用 .html 或 .htm 扩展名")
        if output_path.exists() and not args.force:
            raise ValueError(f"输出文件已存在：{output_path}；确认后可用 --force 覆盖")

        if not template_path.exists():
            raise ValueError(f"模板不存在：{template_path}")

        book = load_config(args.config.resolve())
        for key, value in (
            ("title", args.title),
            ("description", args.description),
            ("eyebrow", args.eyebrow),
        ):
            if value is not None:
                book[key] = value

        files = collect_markdown_files(content_target)
        chapters = build_chapters(files, args.split)
        sources = {path.name: read_text(path) for path in files}

        template = read_text(template_path)
        result = fill_template(template, chapters, book)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(result, encoding="utf-8", newline="")
        verify_output(output_path, chapters, sources)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"生成失败：{error}", file=sys.stderr)
        return 1

    print(f"生成成功：{output_path}")
    print(f"来源：{content_target}")
    print(f"共 {len(chapters)} 篇，正文逐字校验通过。")
    for chapter in chapters:
        words = len("".join(chapter["content"].split()))
        print(f"  {chapter['name']}：{words} 字符（不含空白）")
    print("模板与所有 Markdown 原文均未修改，请人工审核生成文件。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
