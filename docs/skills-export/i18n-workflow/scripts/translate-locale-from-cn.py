import json
import argparse
from pathlib import Path


def translate_from_cn(cn_text: str) -> str:
    term_map = {
        # ──────────────────────────────────────────────────────────────────
        # 术语映射表
        # 使用前请按目标语言填充：{ "中文术语": "目标语言翻译", ... }
        # 例（日文）: { "保存": "保存", "取消": "キャンセル", "删除": "削除", ... }
        # 例（英文）: { "保存": "Save", "取消": "Cancel", "删除": "Delete", ... }
        # ──────────────────────────────────────────────────────────────────
        # 在此添加项目术语映射
        # "取消": "キャンセル",
        # "删除": "削除",
        # "编辑": "編集",
        # ...
    }

    if cn_text in term_map:
        return term_map[cn_text]

    for cn_term, ja_term in term_map.items():
        if cn_term in cn_text:
            return cn_text.replace(cn_term, ja_term)

    return cn_text


def translate_value(value):
    if isinstance(value, str):
        return translate_from_cn(value)
    elif isinstance(value, dict):
        return {k: translate_value(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [translate_value(item) for item in value]
    else:
        return value


def count_translated(original, translated):
    if isinstance(original, str) and isinstance(translated, str):
        return 1 if translated != original else 0
    elif isinstance(original, dict) and isinstance(translated, dict):
        return sum(count_translated(original[k], translated[k]) for k in original if k in translated)
    elif isinstance(original, list) and isinstance(translated, list):
        return sum(count_translated(original[i], translated[i]) for i in range(min(len(original), len(translated))))
    else:
        return 0


def is_chinese(value):
    if isinstance(value, str):
        return '\u4e00' <= value <= '\u9fff'
    elif isinstance(value, dict):
        return any(is_chinese(v) for v in value.values())
    elif isinstance(value, list):
        return any(is_chinese(item) for item in value)
    else:
        return False


def translate_file(zh_file, dest_file, overwrite=False):
    with open(zh_file, 'r', encoding='utf-8') as f:
        zh_data = json.load(f)

    if dest_file.exists():
        with open(dest_file, 'r', encoding='utf-8') as f:
            dest_data = json.load(f)
    else:
        dest_data = {}

    if overwrite:
        translated_data = translate_value(zh_data)
        translated_count = count_translated(zh_data, translated_data)
    else:
        translated_data = {}
        translated_count = 0
        for key, cn_value in zh_data.items():
            if key in dest_data and not is_chinese(dest_data[key]):
                translated_data[key] = dest_data[key]
            else:
                translated_value = translate_value(cn_value)
                translated_data[key] = translated_value
                if isinstance(cn_value, str) and translated_value != cn_value:
                    translated_count += 1

    dest_file.parent.mkdir(parents=True, exist_ok=True)
    with open(dest_file, 'w', encoding='utf-8') as f:
        json.dump(translated_data, f, ensure_ascii=False, indent=2)

    return translated_count


def main():
    parser = argparse.ArgumentParser(description='Translate locale file from Chinese')
    parser.add_argument('--dest', required=True, help='Destination locale directory (e.g., ja-JP)')
    parser.add_argument('--modules', default=None,
                        help='modules 目录路径（默认: 自动检测 apps/web/src/modules）')
    parser.add_argument('--overwrite', action='store_true', help='Overwrite existing translations')
    args = parser.parse_args()

    if args.modules:
        modules_dir = Path(args.modules)
    else:
        project_root = Path(__file__).resolve().parent.parent.parent.parent.parent
        modules_dir = project_root / 'apps' / 'web' / 'src' / 'modules'

    total_translated = 0
    total_files = 0
    processed_modules = 0

    print(f'开始为 {args.dest} 翻译 locale 文件...')

    for module_dir in modules_dir.iterdir():
        if module_dir.is_dir():
            locales_dir = module_dir / 'locales'
            zh_dir = locales_dir / 'zh-CN'
            dest_dir = locales_dir / args.dest

            if zh_dir.exists():
                if not dest_dir.exists():
                    dest_dir.mkdir(parents=True, exist_ok=True)

                module_translated = 0
                module_files = 0

                for zh_file in zh_dir.iterdir():
                    if zh_file.is_file() and zh_file.suffix == '.json':
                        dest_file = dest_dir / zh_file.name
                        translated = translate_file(zh_file, dest_file, args.overwrite)
                        module_translated += translated
                        module_files += 1

                if module_files > 0:
                    print(f'  ✅ {module_dir.name}: {module_files} 个文件, 翻译 {module_translated} 个条目')
                    total_translated += module_translated
                    total_files += module_files
                    processed_modules += 1

    print(f'\n{"="*50}')
    print(f'✅ 翻译完成:')
    print(f'   处理模块数: {processed_modules}')
    print(f'   处理文件数: {total_files}')
    print(f'   翻译条目数: {total_translated}')


if __name__ == '__main__':
    main()
