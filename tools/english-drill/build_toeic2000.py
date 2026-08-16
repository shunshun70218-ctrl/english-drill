#!/usr/bin/env python3
"""組出「多益常考 2000 字」單字庫，分 20 組、由簡單到困難。

    python3 tools/english-drill/build_toeic2000.py     # → wordbank/toeic-2000.json

**全部用免費的公開資料，沒有任何 API 呼叫、不花一毛錢。**
每個欄位的來源都是可查證的辭典或語料，不是模型即席生成的：

| 欄位 | 來源 |
|---|---|
| 單字表 | TOEIC Service List 全收 + New General Service List 高頻字補滿 |
| 難度排序 | 33 萬字詞頻表的實際語料頻率 |
| 音節／重音／音標 | CMUdict + Liang 斷字樣式（見 phonetics.py） |
| 詞性、中譯 | ECDICT 開源英漢辭典（MIT），簡體用 OpenCC 對照表轉繁 |
| 考試標記 | ECDICT（cet4 / cet6 / toefl / ielts / gre…） |
| 例句 | Tatoeba 中英對照句（CC-BY）優先；沒有的話用 TSL 的英文例句 |

詳見 data/SOURCES.md。
"""

import csv
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import phonetics  # noqa: E402
from make_unit import ROOT  # noqa: E402

DATA = Path(__file__).resolve().parent / "data"
OUT = ROOT / "wordbank" / "toeic-2000.json"

TARGET = 2000
PER_LEVEL = 100

# 功能詞：文法零件，當單字卡沒有意義
STOP = set("""the be and of a to in have it that for you he with on do say this they at but we his from not by she or as what go their can who
get if would her all my make about know will up one time there year so think when which them some me people take out into just see him your come
could than like other how then its our two more these want way look first also new because day use no man find here thing give many well only
those tell very even back any good woman through us life child work down may after should call world over school still try last ask need too feel
three state never become between high really something most another much family own leave put old while mean keep student why let great same big
group begin seem country help talk where turn every start hand might show part against place such again few case each right during play run small
off always move night live point hold today bring next without before large must home under room write area money young fact month different lot
since provide around friend father sit away until power hour often yet line among ever stand however member pay meet almost include continue set
later community name five once white least learn real change team best several idea kid body nothing ago lead social understand whether watch
together follow stop face anything create public already speak others read allow add spend door person sure within grow open morning walk reason
low win girl guy early moment himself air""".split())

POS_MAP = {"n": "n.", "v": "v.", "vt": "v.", "vi": "v.", "a": "adj.", "adj": "adj.",
           "ad": "adv.", "adv": "adv.", "prep": "prep.", "conj": "conj.", "pron": "pron."}


# ---------------------------------------------------------------- 簡轉繁

class Simplified2Traditional:
    """OpenCC 的對照表。先比對詞組（長的優先），再逐字轉。"""

    def __init__(self) -> None:
        self.phrases, self.chars = {}, {}
        for filename, table in (("STPhrases.txt", self.phrases), ("STCharacters.txt", self.chars)):
            for line in (DATA / filename).read_text(encoding="utf-8").splitlines():
                if line.startswith("#") or "\t" not in line:
                    continue
                key, value = line.split("\t", 1)
                table[key] = value.split(" ")[0]
        self.maxlen = max(len(k) for k in self.phrases)

    def __call__(self, text: str) -> str:
        out, i = [], 0
        while i < len(text):
            matched = None
            for size in range(min(self.maxlen, len(text) - i), 1, -1):
                segment = text[i:i + size]
                if segment in self.phrases:
                    matched = (segment, self.phrases[segment])
                    break
            if matched:
                out.append(matched[1])
                i += len(matched[0])
            else:
                out.append(self.chars.get(text[i], text[i]))
                i += 1
        return "".join(out)


# ---------------------------------------------------------------- 單字表

def usable(word: str) -> bool:
    return (word.isalpha() and len(word) >= 3 and word not in STOP
            and bool(phonetics.analyze(word)["ipa"]))


def build_pool() -> list[dict]:
    ngsl = {}
    with open(DATA / "ngsl.csv", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            ngsl[row["Lemma"].strip().lower()] = int(row["SFI Rank"])

    tsl = {}
    with open(DATA / "tsl.csv", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            tsl[row["entry"].strip().lower()] = row["example_sentence"].strip()

    picked: dict[str, dict] = {}
    for term, example in tsl.items():          # 多益專用字優先全收
        if usable(term):
            picked[term] = {"term": term, "toeic": True, "tsl_example": example}
    for term, _rank in sorted(ngsl.items(), key=lambda kv: kv[1]):
        if len(picked) >= TARGET:
            break
        if term not in picked and usable(term):
            picked[term] = {"term": term, "toeic": False, "tsl_example": ""}

    freq = {}
    with open(DATA / "count_1w.txt", encoding="utf-8", errors="replace") as f:
        for line in f:
            parts = line.split("\t")
            if len(parts) == 2:
                try:
                    freq[parts[0].strip()] = int(parts[1])
                except ValueError:
                    pass

    words = sorted(picked.values(), key=lambda w: (-freq.get(w["term"], 0), w["term"]))[:TARGET]
    for i, word in enumerate(words):
        word["level"] = i // PER_LEVEL + 1
    return words


# ---------------------------------------------------------------- 中譯與例句

def attach_meanings(words: list[dict], s2t: Simplified2Traditional) -> int:
    entries = {}
    with open(DATA / "ecdict-subset.csv", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            entries[row["word"]] = row

    missing = 0
    for word in words:
        row = entries.get(word["term"])
        if not row:
            word["pos"], word["zh"], word["tag"] = "", "", ""
            missing += 1
            continue

        pos, meaning = "", ""
        for line in (row.get("translation") or "").replace("\\n", "\n").split("\n"):
            line = line.strip()
            if not line:
                continue
            match = re.match(r"^([a-z]+)\.\s*(.+)$", line)
            if match and match.group(1) in POS_MAP:
                pos, meaning = POS_MAP[match.group(1)], match.group(2)
            else:
                meaning = meaning or line
            if meaning:
                break

        meaning = re.split(r"[；;]", meaning)[0]
        parts = [p.strip() for p in re.split(r"[,，、]", meaning) if p.strip()][:2]
        word["pos"] = pos
        word["zh"] = s2t("、".join(parts))[:20]
        word["tag"] = (row.get("tag") or "").strip()
        if not word["zh"]:
            missing += 1
    return missing


def variants(term: str) -> set[str]:
    forms = {term, term + "s", term + "es", term + "d", term + "ed", term + "ing", term + "ly"}
    if term.endswith("e"):
        forms |= {term[:-1] + "ing", term + "d"}
    if term.endswith("y"):
        forms |= {term[:-1] + "ies", term[:-1] + "ied"}
    return forms


def attach_examples(words: list[dict], s2t: Simplified2Traditional) -> tuple[int, int, int]:
    index: dict[str, list[tuple[str, str]]] = {}
    with open(DATA / "tatoeba-cmn-eng.tsv", encoding="utf-8") as f:
        for line in f:
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            english, chinese = parts[0].strip(), parts[1].strip()
            if not (18 <= len(english) <= 75) or len(chinese) > 34:
                continue
            for token in set(re.findall(r"[a-z]+", english.lower())):
                index.setdefault(token, []).append((english, chinese))

    both = english_only = none = 0
    for word in words:
        candidates = []
        for form in variants(word["term"]):
            candidates += index.get(form, [])
        if candidates:
            # 挑長度最接近 42 字元的——太短沒有情境，太長在手機上難讀
            english, chinese = min(candidates, key=lambda c: abs(len(c[0]) - 42))
            word["example_en"], word["example_zh"] = english, s2t(chinese)
            both += 1
        elif word["tsl_example"]:
            word["example_en"], word["example_zh"] = word["tsl_example"], ""
            english_only += 1
        else:
            word["example_en"] = word["example_zh"] = ""
            none += 1
    return both, english_only, none


# ---------------------------------------------------------------- 輸出

def write_bank(words: list[dict]) -> None:
    levels: dict[int, list[dict]] = {}
    for word in words:
        entry = {"term": word["term"], "pos": word["pos"], "zh": word["zh"]}
        if word["example_en"]:
            entry["example_en"] = word["example_en"]
        if word["example_zh"]:
            entry["example_zh"] = word["example_zh"]
        if word["tag"]:
            entry["tag"] = word["tag"]
        if word["toeic"]:
            entry["toeic"] = True
        levels.setdefault(word["level"], []).append(entry)

    bank = {
        "title": "多益常考 2000 字",
        "title_en": "TOEIC 2000",
        "note": "由 build_toeic2000.py 從公開辭典與語料產生，不要手改。來源見 tools/english-drill/data/SOURCES.md。",
        "voice": "Samantha",
        "example_audio": False,        # 2000 字只產單字發音；例句音檔會讓檔案大四倍
        "themes": [
            {"slug": f"lv{level:02d}", "name": f"第 {level} 組", "words": items}
            for level, items in sorted(levels.items())
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(bank, ensure_ascii=False, indent=1), encoding="utf-8")


def main() -> int:
    s2t = Simplified2Traditional()

    words = build_pool()
    print(f"單字表：{len(words)} 字、{max(w['level'] for w in words)} 組"
          f"（多益專用 {sum(1 for w in words if w['toeic'])}）")

    missing = attach_meanings(words, s2t)
    print(f"中譯：ECDICT 補上 {len(words) - missing} 筆" + (f"、{missing} 筆查不到" if missing else "、全部查得到"))

    both, english_only, none = attach_examples(words, s2t)
    print(f"例句：中英對照 {both}、只有英文 {english_only}、沒有 {none}")

    words = [w for w in words if w["zh"]]
    write_bank(words)
    print(f"\n寫出 {OUT}（{len(words)} 字）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
