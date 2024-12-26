import json
from pathlib import Path


class I18n:
    file_zh_cn = Path.cwd() / 'module' / 'config' / 'i18n' / 'zh-CN.json'

    @classmethod
    def trans_zh_cn(cls, text) -> str:
        cn_zh_data = cls.load_zh_cn()
        return cn_zh_data[text] if text in cn_zh_data else text

    @classmethod
    def save_zh_cn(cls, data) -> None:
        I18n.file_zh_cn.parent.mkdir(parents=True, exist_ok=True)
        with open(str(I18n.file_zh_cn), 'w', encoding='utf-8') as f:
            s = json.dumps(data, indent=2, ensure_ascii=False, sort_keys=False, default=str)
            f.write(s)

    @classmethod
    def load_zh_cn(cls) -> dict:
        if not I18n.file_zh_cn.exists():
            return {}
        with open(str(I18n.file_zh_cn), 'r', encoding='utf-8') as f:
            return json.load(f)

if __name__ == '__main__':
    print(I18n.load_zh_cn())