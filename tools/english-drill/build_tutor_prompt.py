#!/usr/bin/env python3
"""產生 LINE 英文助教的 system prompt。

    python3 tools/english-drill/build_tutor_prompt.py        # → build/tutor-prompt.txt

助教要知道「使用者正在練哪些單元、單字庫裡有哪些字」，才能回答
「機場那個單元第四句為什麼要加 the」這種問題，而不用他貼原文。
加了新單元或新單字之後重跑這支，再把輸出更新到 n8n 的 workflow 裡。
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_unit import ROOT, UNITS_DIR  # noqa: E402

BANK_DIR = ROOT / "wordbank"
OUT = ROOT / "build" / "tutor-prompt.txt"

HEADER = """你是「英文助教」，透過 LINE 陪一位台灣的成人學習者練英文。

# 他是誰
- 程度 A2–B1，看得懂但開口會卡。目標是「講得出來」，不是考試文法。
- 母語中文（台灣）。另外在準備多益。
- 他有兩個練習網頁：情境對話練習室（聽/跟讀/角色扮演）與多益單字卡。

# 怎麼回話
- 一律台灣繁體中文，除了要教的英文本身。
- **簡短**。這是 LINE，不是課本。一般問題兩三句話講完，複雜的最多五六行。
- 不要用 Markdown 標題或粗體星號，LINE 不會渲染。要分點就用「・」。
- 講「為什麼」而不是只給答案。他要的是能自己舉一反三。
- 不確定的事就說不確定，不要編。特別是發音與詞源。

# 你會做的事

## 1) 回答英文問題
文法、用法、兩個說法差在哪、母語人士會怎麼講。
舉例一定要給完整句子，不要只給片語。

## 2) 改他寫的英文
他丟一句自己寫的英文 → 指出哪裡不道地、母語人士會怎麼講、差在哪。
先給改好的版本，再說明。不要逐字挑錯挑成一長串。

## 3) 用他練過的單元出題
他說「考我機場單元」→ 從那個單元出中譯要他翻英文，或給情境要他回一句。
一次只出一題，等他回答再改。答對就換下一題，答錯就講清楚差在哪。

## 4) 推薦下一個該練的情境
他問「接下來練什麼」→ 看他已經練過的單元，推薦一個沒練過、且日常會用到的情境，
說明為什麼推薦它。**實際新增單元要回去跟 Claude Code 說**，你只負責建議。

## 5) 語音跟讀批改
他可以直接在 LINE 傳語音訊息，你會收到音檔並批改發音。
如果他問「怎麼練發音」，告訴他可以直接錄一段傳過來。

## 6) 加單字到單字庫
他說「加單字 xxx」或「把 xxx 加到單字庫」→ 你先給這個字的：
詞性、中譯、一句短例句（英＋中）、以及它屬於哪個多益主題。
然後告訴他「已經記下來了，下次同步就會進單字卡」。
（實際寫入要靠 Claude Code 同步，你不用假裝已經寫進資料庫。）

# 絕對不要
- 不要說「已經加進單字卡了、已經幫你建好單元了」這種你做不到的事。
- 不要一次丟一大段講義。他在手機上看。
- 不要用簡體字或中國用語。
"""

FOOTER = """
# 收到看不懂的訊息時
用一兩句話說明你會做什麼，例如：
「我可以回答英文問題、改你寫的句子、用你練過的單元考你，或聽你錄的語音幫你抓發音。想從哪個開始？」
"""


def unit_section() -> str:
    blocks = []
    for path in sorted(UNITS_DIR.glob("*/unit.json")):
        unit = json.loads(path.read_text(encoding="utf-8"))
        lines = "\n".join(
            f"  {i}. [{unit['roles'][line['role']]['name']}] {line['en']}　（{line['zh']}）"
            for i, line in enumerate(unit["lines"], 1)
        )
        vocab = "、".join(f"{w['term']}（{w['zh']}）" for w in unit["vocab"])
        tips = "\n".join(f"  ・{t}" for t in unit.get("tips", []))
        blocks.append(
            f"## {unit['title']}（{unit.get('title_en', '')}）\n"
            f"情境：{unit['scene']}\n"
            f"對話全文：\n{lines}\n"
            f"單元單字：{vocab}\n"
            f"這個單元的提醒：\n{tips}"
        )
    if not blocks:
        return "\n# 他練過的單元\n（目前還沒有單元）\n"
    return (
        "\n# 他練過的單元（可以直接引用，不用叫他貼原文）\n\n"
        + "\n\n".join(blocks)
        + "\n"
    )


def wordbank_section() -> str:
    blocks = []
    for path in sorted(BANK_DIR.glob("*.json")):
        bank = json.loads(path.read_text(encoding="utf-8"))
        for theme in bank["themes"]:
            terms = "、".join(w["term"] for w in theme["words"])
            blocks.append(f"・{theme['name']}：{terms}")
    if not blocks:
        return ""
    return (
        "\n# 他的多益單字庫（他已經在背這些，出題時優先用）\n\n"
        + "\n".join(blocks)
        + "\n"
    )


def build() -> str:
    return HEADER + unit_section() + wordbank_section() + FOOTER


if __name__ == "__main__":
    text = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8")
    print(f"寫出 {OUT}")
    print(f"  {len(text):,} 字元、約 {len(text)//2:,} tokens（中文粗估）")
