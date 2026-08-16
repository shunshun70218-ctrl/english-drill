#!/usr/bin/env python3
"""音節切分與音標產生。

音標不是我編的，來源是兩份公開資料，都放在 data/：
  cmudict.dict    CMU Pronouncing Dictionary（發音 + 重音位置，美式）
  hyph_en_US.dic  Liang 斷字樣式（拼字要怎麼切音節）

兩邊各管一件事：CMUdict 管「怎麼唸、重音在哪一節」，斷字樣式管「字母怎麼分段」。
音節數對得起來時才會標重音節，對不上就誠實不標，不亂猜。

自我測試：python3 tools/english-drill/phonetics.py
"""

import re
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"

# ---------------------------------------------------------------- 斷字（拼字音節）


class Hyphenator:
    """Liang 斷字演算法（TeX / Hunspell 用的那一套）。"""

    def __init__(self, dic_path: Path):
        self.patterns: dict[str, list[int]] = {}
        lines = dic_path.read_text(encoding="utf-8", errors="replace").splitlines()

        for raw in lines:
            line = raw.strip()
            # 跳過編碼宣告、設定行、註解、以及帶 / 的非標準斷字樣式
            if not line or line.startswith("%") or "/" in line:
                continue
            if re.match(r"^[A-Z]+(\s|$)", line) or line.upper() == line and line.isalpha():
                continue

            letters = re.sub(r"\d", "", line)
            if not letters:
                continue

            # 把樣式拆成「字母序列」與「每個間隙的優先值」
            values = [0] * (len(letters) + 1)
            index = 0
            for char in line:
                if char.isdigit():
                    values[index] = int(char)
                else:
                    index += 1
            self.patterns[letters] = values

    @lru_cache(maxsize=8192)
    def candidates(self, word: str) -> tuple[tuple[int, int], ...]:
        """回傳所有可切點 (位置, 優先值)，優先值越大越該切。

        刻意不套用 LEFTHYPHENMIN / RIGHTHYPHENMIN——那是「排版換行」的規則
        （避免行尾只掛一兩個字母），不是音節規則。套下去 a-gen-da 會整個切不開。
        """
        lowered = "." + word.lower() + "."
        points = [0] * (len(lowered) + 1)

        for start in range(len(lowered)):
            for end in range(start + 1, len(lowered) + 1):
                values = self.patterns.get(lowered[start:end])
                if values:
                    for offset, value in enumerate(values):
                        pos = start + offset
                        if value > points[pos]:
                            points[pos] = value

        return tuple(
            (i, points[i + 1])
            for i in range(1, len(word))
            if points[i + 1] % 2 == 1
        )

    @staticmethod
    def _cut(word: str, positions: list[int]) -> list[str]:
        parts, prev = [], 0
        for point in sorted(positions):
            parts.append(word[prev:point])
            prev = point
        parts.append(word[prev:])
        return [p for p in parts if p]

    @staticmethod
    def _has_vowel(part: str) -> bool:
        return any(c in "aeiouyAEIOUY" for c in part)

    def syllables(self, word: str, want: int | None = None) -> list[str]:
        """切成音節。給了 want（來自音標的音節數）就湊到剛好那麼多節。

        每一節都必須含母音字母——這是「p·re·sen·tation」那種錯法的守門員。
        排版用的 LEFTHYPHENMIN 在這裡不適用（會害 a·gen·da 整個切不開），
        真正的規則是「單獨一個子音不成音節，單獨一個母音可以」。
        """
        ranked = sorted(self.candidates(word), key=lambda b: (-b[1], b[0]))
        limit = (want - 1) if want is not None else len(ranked)

        chosen: list[int] = []
        for position, _value in ranked:
            if len(chosen) >= limit:
                break
            trial = chosen + [position]
            if all(self._has_vowel(p) for p in self._cut(word, trial)):
                chosen.append(position)

        return self._cut(word, chosen) if chosen else [word]


# ---------------------------------------------------------------- 發音（CMUdict）

ARPA_VOWELS = {
    "AA", "AE", "AH", "AO", "AW", "AY", "EH", "ER",
    "EY", "IH", "IY", "OW", "OY", "UH", "UW",
}

ARPA_TO_IPA = {
    "AA": "ɑ", "AE": "æ", "AH": "ʌ", "AO": "ɔ", "AW": "aʊ", "AY": "aɪ",
    "B": "b", "CH": "tʃ", "D": "d", "DH": "ð", "EH": "ɛ", "ER": "ɜr",
    "EY": "eɪ", "F": "f", "G": "ɡ", "HH": "h", "IH": "ɪ", "IY": "i",
    "JH": "dʒ", "K": "k", "L": "l", "M": "m", "N": "n", "NG": "ŋ",
    "OW": "oʊ", "OY": "ɔɪ", "P": "p", "R": "r", "S": "s", "SH": "ʃ",
    "T": "t", "TH": "θ", "UH": "ʊ", "UW": "u", "V": "v", "W": "w",
    "Y": "j", "Z": "z", "ZH": "ʒ",
}

# 合法的英語音節起首（決定子音群要歸給前一節的尾巴還是後一節的開頭）
ONSETS_3 = {("S", "P", "R"), ("S", "T", "R"), ("S", "K", "R"), ("S", "P", "L"), ("S", "K", "W")}
ONSETS_2 = {
    ("P", "L"), ("P", "R"), ("B", "L"), ("B", "R"), ("T", "R"), ("D", "R"),
    ("K", "L"), ("K", "R"), ("G", "L"), ("G", "R"), ("F", "L"), ("F", "R"),
    ("TH", "R"), ("SH", "R"), ("S", "L"), ("S", "W"), ("S", "M"), ("S", "N"),
    ("S", "P"), ("S", "T"), ("S", "K"), ("K", "W"), ("HH", "Y"), ("P", "Y"),
    ("B", "Y"), ("K", "Y"), ("F", "Y"), ("M", "Y"), ("V", "Y"),
}


class Pronouncer:
    def __init__(self, dict_path: Path):
        self.entries: dict[str, list[str]] = {}
        for raw in dict_path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.split("#")[0].strip()
            if not line:
                continue
            head, _, rest = line.partition(" ")
            # cat(2) 這種是同一個字的第二種唸法，只留第一種
            if head.endswith(")"):
                continue
            self.entries.setdefault(head.lower(), rest.split())

    def phones(self, word: str) -> list[str] | None:
        return self.entries.get(word.lower().strip())


def split_phone_syllables(phones: list[str]) -> list[list[str]]:
    """依「最大起首原則」把音素切成音節。"""
    vowel_positions = [i for i, p in enumerate(phones) if p[:2] in ARPA_VOWELS]
    if not vowel_positions:
        return [phones]

    syllables = []
    start = 0
    for n, vowel_index in enumerate(vowel_positions):
        if n == len(vowel_positions) - 1:
            syllables.append(phones[start:])
            break

        cluster_start = vowel_index + 1
        cluster_end = vowel_positions[n + 1]
        cluster = [re.sub(r"\d", "", p) for p in phones[cluster_start:cluster_end]]

        # 從最長開始試，找出能合法當作下一節起首的後綴
        onset_len = 0
        for size in (3, 2, 1):
            if len(cluster) >= size:
                tail = tuple(cluster[-size:])
                if size == 3 and tail in ONSETS_3:
                    onset_len = 3
                    break
                if size == 2 and tail in ONSETS_2:
                    onset_len = 2
                    break
                if size == 1:
                    onset_len = 1
                    break

        split_at = cluster_end - onset_len
        syllables.append(phones[start:split_at])
        start = split_at

    return [s for s in syllables if s]


def phones_to_ipa(syllable: list[str]) -> tuple[str, int]:
    """回傳 (該音節的 IPA, 重音等級 0/1/2)。"""
    stress = 0
    out = []
    for phone in syllable:
        match = re.match(r"^([A-Z]+)(\d)?$", phone)
        if not match:
            continue
        base, digit = match.group(1), match.group(2)
        level = int(digit) if digit else 0
        if level > 0:
            stress = level
        # 無重音的 AH 是輕音 schwa，ER 同理——CMUdict 用同一個符號表示，要靠重音數字分辨
        if base == "AH" and level == 0:
            out.append("ə")
        elif base == "ER" and level == 0:
            out.append("ər")
        else:
            out.append(ARPA_TO_IPA.get(base, base.lower()))
    return "".join(out), stress


VOWEL_LETTERS = "aeiouy"

# 這些雙字母代表單一個音，不能從中間切開
DIGRAPHS = {"ch", "sh", "th", "ph", "wh", "gh", "ck", "ng", "qu"}


def _vowel_groups(word: str) -> list[tuple[int, int]]:
    """找出母音字母群（連續的 aeiouy），回傳 [(起, 迄), ...]。"""
    groups, start = [], None
    for i, char in enumerate(word.lower()):
        if char in VOWEL_LETTERS:
            if start is None:
                start = i
        elif start is not None:
            groups.append((start, i))
            start = None
    if start is not None:
        groups.append((start, len(word)))
    return groups


def split_by_vowel_groups(word: str, want: int) -> list[str] | None:
    """備援切法：以母音群當音節核心切字。

    Liang 樣式是為了「排版斷行」設計的，像 venue、rental、brochure 這類字它根本不給切點，
    但我們要的是音節。這裡改用「一個母音群 = 一個音節核心」，
    再把中間的子音群留一個當下一節的開頭（英語音節傾向以子音起首）。

    切不出剛好 want 節就回傳 None，不硬湊。
    """
    lowered = word.lower()
    groups = _vowel_groups(lowered)

    # 字尾的不發音 e（如 time、chure）不算一個音節核心
    while len(groups) > want and groups and groups[-1][1] == len(lowered) \
            and lowered[groups[-1][0]:] == "e":
        groups.pop()

    # 還是太多 → 把相鄰、中間沒有子音隔開的母音群併起來
    while len(groups) > want:
        merged = False
        for i in range(len(groups) - 1):
            if groups[i][1] == groups[i + 1][0]:
                groups[i] = (groups[i][0], groups[i + 1][1])
                groups.pop(i + 1)
                merged = True
                break
        if not merged:
            break

    if len(groups) != want:
        return None

    cuts = []
    for i in range(len(groups) - 1):
        coda_start = groups[i][1]           # 前一個母音群結束的位置
        onset_end = groups[i + 1][0]        # 下一個母音群開始的位置
        consonants = onset_end - coda_start

        if consonants == 0:
            cut = onset_end
        else:
            # 前一節的尾巴最多留一個子音（ren·tal），其餘都給下一節當開頭（chil·dren）
            cut = min(onset_end - 1, coda_start + 1)

        # 不可以從雙字母組合中間切開（ch / sh / th …）
        if 0 < cut < len(lowered) and lowered[cut - 1:cut + 1] in DIGRAPHS:
            cut -= 1

        if cut <= (cuts[-1] if cuts else 0) or cut >= len(word):
            return None
        cuts.append(cut)

    parts, prev = [], 0
    for cut in cuts:
        parts.append(word[prev:cut])
        prev = cut
    parts.append(word[prev:])
    return parts if all(p for p in parts) else None


_hyphenator: Hyphenator | None = None
_pronouncer: Pronouncer | None = None


def _load():
    global _hyphenator, _pronouncer
    if _hyphenator is None:
        _hyphenator = Hyphenator(DATA / "hyph_en_US.dic")
    if _pronouncer is None:
        _pronouncer = Pronouncer(DATA / "cmudict.dict")
    return _hyphenator, _pronouncer


def analyze(term: str) -> dict:
    """回傳一個字（或片語）的音節與音標資訊。

    {
      "syllables":  ["con","fi","den","tial"],   拼字音節
      "stress":     2,                            主重音落在第幾節（0 起算），None = 對不上不標
      "ipa":        "ˌkɑn.fɪˈdɛn.ʃəl",
      "source":     "cmudict" | "hyphenation-only"
    }
    """
    hyphenator, pronouncer = _load()
    words = term.split()

    # 片語：逐字處理再合起來
    if len(words) > 1:
        parts = [analyze(w) for w in words]
        return {
            "syllables": [s for p in parts for s in p["syllables"]],
            "stress": None,
            "ipa": " ".join(p["ipa"] for p in parts if p["ipa"]),
            "source": "phrase",
        }

    clean = re.sub(r"[^A-Za-z'-]", "", term)

    phones = pronouncer.phones(clean)
    if not phones:
        return {
            "syllables": hyphenator.syllables(clean) if clean else [term],
            "stress": None,
            "ipa": "",
            "source": "hyphenation-only",
        }

    phone_syllables = split_phone_syllables(phones)
    want = len(phone_syllables)

    # 音標的音節數是基準，拼字切分去湊它：先試 Liang 樣式，湊不到就用母音群備援
    syllables = hyphenator.syllables(clean, want=want)
    if len(syllables) != want:
        fallback = split_by_vowel_groups(clean, want)
        if fallback:
            syllables = fallback
    pieces = [phones_to_ipa(s) for s in phone_syllables]

    ipa_parts = []
    stress_index = None
    for i, (sound, stress) in enumerate(pieces):
        mark = "ˈ" if stress == 1 else ("ˌ" if stress == 2 else "")
        ipa_parts.append(mark + sound)
        if stress == 1 and stress_index is None:
            stress_index = i

    ipa = "." .join(ipa_parts).replace(".ˈ", "ˈ").replace(".ˌ", "ˌ")

    # 只有兩邊音節數一致時，重音節的位置才對得上拼字音節
    if len(phone_syllables) != len(syllables):
        stress_index = None

    return {
        "syllables": syllables,
        "stress": stress_index,
        "ipa": ipa,
        "source": "cmudict",
    }


# ---------------------------------------------------------------- 自我測試

if __name__ == "__main__":
    cases = [
        "confidential", "negotiation", "invoice", "warehouse", "receipt",
        "itinerary", "reimbursement", "colleague", "schedule", "agenda",
        "maintenance", "subsidiary", "questionnaire", "inventory", "deadline",
    ]
    print(f"{'字':<16} {'音節':<28} {'音標':<26} 重音節")
    print("-" * 82)
    for word in cases:
        info = analyze(word)
        syls = info["syllables"]
        shown = " · ".join(
            s.upper() if info["stress"] == i else s for i, s in enumerate(syls)
        )
        stress = syls[info["stress"]] if info["stress"] is not None else "（對不上，不標）"
        print(f"{word:<16} {shown:<28} /{info['ipa']}/{'':<4} {stress}")
