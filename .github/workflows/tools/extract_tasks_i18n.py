#!/usr/bin/env python3
"""
提取 tasks 目录下子任务名称的翻译

从两个源文件提取：
1. module/config/i18n/zh_CN.xml (本仓库)
2. https://raw.githubusercontent.com/runhey/OASX/master/lib/config/translation/i18n_cn.dart (外部仓库)

输出到 .github/workflows/assets/tasks-i18n-{YYYY-MM-DD}.md
"""

import os
import re
import urllib.request
from pathlib import Path
import datetime

date = datetime.datetime.now().strftime("%Y-%m-%d")

# paths
SCRIPT_DIR = Path(__file__).parent.resolve()
REPO_ROOT = SCRIPT_DIR.parent.parent.parent
TASKS_DIR = REPO_ROOT / "tasks"
ZH_CN_XML = REPO_ROOT / "module/config/i18n/zh_CN.xml"
OASX_I18N_URL = "https://raw.githubusercontent.com/runhey/OASX/master/lib/config/translation/i18n_cn.dart"
OUTPUT_FILE = SCRIPT_DIR.parent / "assets" / f"tasks-i18n-{date}.md"


def get_tasks_directories():
    """获取 tasks 目录下的所有子目录名"""
    if not TASKS_DIR.exists():
        print(f"Warning: {TASKS_DIR} not found")
        return []

    dirs = [d.name for d in TASKS_DIR.iterdir() if d.is_dir()]
    return sorted(dirs)


def extract_from_zh_cn_xml():
    """从 zh_CN.xml 提取翻译"""
    translations = {}

    if not ZH_CN_XML.exists():
        print(f"Warning: {ZH_CN_XML} not found")
        return translations

    content = ZH_CN_XML.read_text(encoding="utf-8")

    # 从 TaskList 和 FluTreeView 上下文中提取
    # 格式: <message><source>DailyTrifles</source><translation>每日琐事</translation></message>
    pattern = r'<source>([A-Za-z]+)</source>\s*<translation>([^<]+)</translation>'

    for match in re.finditer(pattern, content):
        key, value = match.groups()
        translations[key] = value.strip()

    return translations


def extract_from_oasx():
    """从 OASX 的 i18n_cn.dart 提取翻译"""
    translations = {}

    try:
        print(f"Fetching {OASX_I18N_URL}...")
        with urllib.request.urlopen(OASX_I18N_URL, timeout=30) as response:
            content = response.read().decode("utf-8")
    except Exception as e:
        print(f"Warning: Failed to fetch OASX i18n: {e}")
        return translations

    # 格式1: I18n.daily_trifles: '每日琐事',  (snake_case key -> PascalCase)
    pattern1 = r"I18n\.([a-z_]+):\s*'([^']+)'"
    for match in re.finditer(pattern1, content):
        key, value = match.groups()
        dir_name = "".join(word.capitalize() for word in key.split("_"))
        translations[dir_name] = value.strip()

    # 格式2: 'AbyssShadows': '狭间暗域',  (PascalCase key，直接)
    pattern2 = r"'([A-Z][a-zA-Z]+)':\s*'([^']+)'"
    for match in re.finditer(pattern2, content):
        key, value = match.groups()
        # 只保留看起来像目录名的 key（PascalCase，多个单词）
        if len(key) > 3 and key[0].isupper():
            translations[key] = value.strip()

    return translations


def merge_translations(tasks_dirs, zh_cn_translations, oasx_translations):
    """合并翻译结果"""
    result = {}

    for dir_name in tasks_dirs:
        # 优先级：zh_CN.xml > OASX > 未知
        if dir_name in zh_cn_translations:
            result[dir_name] = zh_cn_translations[dir_name]
        elif dir_name in oasx_translations:
            result[dir_name] = oasx_translations[dir_name]
        else:
            result[dir_name] = ""  # 未找到翻译

    return result


def generate_markdown(translations):
    """生成 Markdown 格式输出"""
    lines = [
        "# Tasks 子目录翻译",
        "",
        "自动生成文件 - 请勿手动修改",
        "",
        "| 目录 | 中文 |",
        "|------|------|",
    ]

    for dir_name in sorted(translations.keys()):
        chinese = translations[dir_name] or "（未找到翻译）"
        lines.append(f"| {dir_name} | {chinese} |")

    lines.append("")
    lines.append("## 来源说明")
    lines.append(f"- `{ZH_CN_XML.relative_to(REPO_ROOT)}` - 本仓库")
    lines.append(f"- {OASX_I18N_URL} - 外部仓库 (OASX)")

    return "\n".join(lines)


def main():
    print("=== Tasks 翻译提取工具 ===\n")
    print(f"Repo root: {REPO_ROOT}")

    # 1. 获取 tasks 子目录
    print("1. 获取 tasks 子目录...")
    tasks_dirs = get_tasks_directories()
    print(f"   找到 {len(tasks_dirs)} 个子目录")

    # 2. 从 zh_CN.xml 提取
    print("2. 从 zh_CN.xml 提取翻译...")
    zh_cn_translations = extract_from_zh_cn_xml()
    print(f"   找到 {len(zh_cn_translations)} 条翻译")

    # 3. 从 OASX 提取
    print("3. 从 OASX i18n_cn.dart 提取翻译...")
    oasx_translations = extract_from_oasx()
    print(f"   找到 {len(oasx_translations)} 条翻译")

    # 4. 合并结果
    print("4. 合并翻译结果...")
    merged = merge_translations(tasks_dirs, zh_cn_translations, oasx_translations)

    # 5. 生成输出
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    print(f"5. 生成输出到 {OUTPUT_FILE}...")
    output_content = generate_markdown(merged)
    OUTPUT_FILE.write_text(output_content, encoding="utf-8")

    # 6. 统计
    found = sum(1 for v in merged.values() if v)
    print(f"\n完成！找到翻译: {found}/{len(merged)}")

    # 打印未找到翻译的目录
    missing = [k for k, v in merged.items() if not v]
    if missing:
        print(f"\n未找到翻译的目录: {', '.join(missing)}")


if __name__ == "__main__":
    main()