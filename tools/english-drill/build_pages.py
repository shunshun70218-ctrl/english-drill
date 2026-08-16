#!/usr/bin/env python3
"""組裝要放上 GitHub Pages 的靜態網站。

    python3 tools/english-drill/build_pages.py

輸出到 docs/（GitHub Pages 可以直接指向 main branch 的 /docs）。

跟 build_artifact.py / make_wordbank.py 的差別：
那兩支把音檔 base64 內嵌成單一 HTML（發佈成 Artifact 需要），
這支把音檔當成獨立檔案放旁邊——手機用行動網路開的時候，
不用一次下載十幾 MB，點到哪一句才載哪一句。
"""

import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_unit import ROOT, TEMPLATES, UNITS_DIR, embed_json, enrich, load_unit  # noqa: E402
from make_wordbank import BANK_DIR, OUT_DIR, attach_audio, build_audio, enrich_words  # noqa: E402

DOCS = ROOT / "docs"


def clean() -> None:
    if DOCS.exists():
        shutil.rmtree(DOCS)
    DOCS.mkdir(parents=True)
    (DOCS / ".nojekyll").write_text("", encoding="utf-8")   # 別讓 Jekyll 處理，會吃掉底線開頭的檔


def copy_units() -> list[dict]:
    """把已經建好的單元頁原樣搬過去（它們本來就是相對路徑，天生適合靜態託管）。"""
    metas = []
    for unit_json in sorted(UNITS_DIR.glob("*/unit.json")):
        folder = unit_json.parent
        target = DOCS / "units" / folder.name
        shutil.copytree(
            folder, target,
            ignore=shutil.ignore_patterns("unit.json", ".manifest.json"),
        )
        unit = json.loads(unit_json.read_text(encoding="utf-8"))
        metas.append({
            "folder": folder.name,
            "title": unit["title"],
            "title_en": unit.get("title_en", ""),
            "scene": unit["scene"],
            "level": unit["level"],
            "lines": len(unit["lines"]),
            "vocab": len(unit["vocab"]),
        })
    return metas


def build_wordbank() -> int:
    """單字卡：音檔獨立成檔，不做 base64。多個字庫會併成一頁，靠切換器選。"""
    out_dir = DOCS / "wordbank"
    audio_out = out_dir / "audio"
    audio_out.mkdir(parents=True, exist_ok=True)

    payload, flat, total = [], [], 0

    # 小的字庫排前面（核心 98 字先出現，2000 字在後）
    for bank_path in sorted(BANK_DIR.glob("*.json"), key=lambda p: p.stat().st_size):
        bank = json.loads(bank_path.read_text(encoding="utf-8"))
        bank["_path"] = bank_path
        count, _missing = enrich_words(bank)
        total += count

        # 2000 字的字庫關掉例句音檔——不然檔案數與體積都會多四倍
        with_examples = bank.get("example_audio", True)
        audio_src = OUT_DIR / "wordbank-audio" / bank_path.stem
        manifest = build_audio(bank, audio_src, with_examples=with_examples, force=False)

        prefix = bank_path.stem          # 不同字庫的音檔放在各自的子資料夾，避免撞名
        (audio_out / prefix).mkdir(parents=True, exist_ok=True)
        for theme in bank["themes"]:
            for word in theme["words"]:
                key = word.pop("audio_key")
                for suffix, field in (("w", "audio"), ("e", "example_audio")):
                    entry = manifest.get(f"{key}-{suffix}")
                    if not entry:
                        continue
                    shutil.copyfile(audio_src / entry["file"], audio_out / prefix / entry["file"])
                    word[field] = f"audio/{prefix}/{entry['file']}"

        payload.append({
            "title": bank["title"],
            "title_en": bank.get("title_en", ""),
            "themes": [{"slug": t["slug"], "name": t["name"], "words": t["words"]} for t in bank["themes"]],
        })

        # 給 n8n 每日推播用的扁平清單，所有字庫累加進同一份。
        # 音檔長度一定要帶——LINE 的語音訊息少了 duration 會被直接退回。
        for theme in bank["themes"]:
            for index, word in enumerate(theme["words"], 1):
                key = f"{theme['slug']}-{index:02d}"
                entry = {
                    "term": word["term"],
                    "syllables": word["syllables"],
                    "stress": word["stress"],
                    "ipa": word["ipa"],
                    "pos": word.get("pos", ""),
                    "zh": word["zh"],
                    "bank": bank["title"],
                    "theme": theme["name"],
                    "example_en": word.get("example_en", ""),
                    "example_zh": word.get("example_zh", ""),
                    "audio": word["audio"],
                    "audio_ms": int(round(manifest[f"{key}-w"]["dur"] * 1000)),
                }
                example = manifest.get(f"{key}-e")
                if example:
                    entry["example_audio"] = word["example_audio"]
                    entry["example_ms"] = int(round(example["dur"] * 1000))
                flat.append(entry)

    (out_dir / "words.json").write_text(
        json.dumps({"count": len(flat), "words": flat}, ensure_ascii=False),
        encoding="utf-8",
    )

    css = (TEMPLATES / "player.css").read_text(encoding="utf-8")
    extra = (TEMPLATES / "wordbank.css").read_text(encoding="utf-8")
    js = (TEMPLATES / "wordbank.js").read_text(encoding="utf-8")

    (out_dir / "index.html").write_text(f"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="單字卡">
<title>多益單字卡</title>
<style>
{css}
{extra}
</style>
</head>
<body>
<div class="wrap">
  <header class="top">
    <a class="top__back" href="../index.html">← 回目錄</a>
    <h1 class="top__title">多益單字卡</h1>
    <p class="top__en">TOEIC Vocabulary Flashcards</p>
    <div class="meta" id="bank-meta"></div>
  </header>
  <div id="app"></div>
  <p class="hint" style="margin-top:28px">熟練度記在這台裝置上。</p>
</div>
<script id="bank-data" type="application/json">{embed_json(payload)}</script>
<script>
{js}
</script>
</body>
</html>
""", encoding="utf-8")

    return total


INDEX_TEMPLATE = """<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="英文練習">
<meta name="robots" content="noindex">
<title>英文練習</title>
<style>
{css}
</style>
</head>
<body>
<div class="wrap">
  <header class="top">
    <h1 class="top__title">英文練習</h1>
    <p class="top__en">情境對話與多益單字</p>
    <div class="meta"><span>{unit_count} 個情境</span><span>{word_count} 個單字</span></div>
  </header>

  <a class="unit-card" href="wordbank/index.html">
    <div class="unit-card__title">🗂️ 多益單字卡</div>
    <div class="unit-card__en">TOEIC Vocabulary Flashcards</div>
    <div class="unit-card__scene">音節拆解、重音、音標與發音。三段熟練度，優先考不熟的字。</div>
    <div class="unit-card__meta"><span class="pill">TOEIC</span><span>{word_count} 個單字</span></div>
  </a>

  <h2 style="font-size:13px;letter-spacing:.06em;text-transform:uppercase;color:var(--ink-faint);margin:26px 0 12px">情境對話練習</h2>
  <div class="units">
{cards}
  </div>

  <section class="howto">
    <p>手機上想當 app 用：Safari 分享鍵 → 加入主畫面。</p>
  </section>
</div>
</body>
</html>
"""


def build_index(units: list[dict], word_count: int) -> None:
    import html

    cards = "\n".join(
        f'''    <a class="unit-card" href="units/{html.escape(u["folder"])}/index.html">
      <div class="unit-card__title">{html.escape(u["title"])}</div>
      <div class="unit-card__en">{html.escape(u["title_en"])}</div>
      <div class="unit-card__scene">{html.escape(u["scene"])}</div>
      <div class="unit-card__meta">
        <span class="pill">{html.escape(u["level"])}</span>
        <span>{u["lines"]} 句</span>
        <span>{u["vocab"]} 個單字</span>
      </div>
    </a>'''
        for u in units
    )

    (DOCS / "index.html").write_text(
        INDEX_TEMPLATE.format(
            css=(TEMPLATES / "player.css").read_text(encoding="utf-8"),
            cards=cards,
            unit_count=len(units),
            word_count=word_count,
        ),
        encoding="utf-8",
    )


def main() -> int:
    clean()
    units = copy_units()
    word_count = build_wordbank()
    build_index(units, word_count)

    files = sum(1 for _ in DOCS.rglob("*") if _.is_file())
    size = sum(f.stat().st_size for f in DOCS.rglob("*") if f.is_file()) / 1024 / 1024
    biggest = max((f for f in DOCS.rglob("*.html")), key=lambda f: f.stat().st_size)

    print(f"docs/ 組好了：{len(units)} 個情境、{word_count} 個單字")
    print(f"  {files} 個檔案、共 {size:.1f} MB")
    print(f"  最大的 HTML：{biggest.relative_to(DOCS)} {biggest.stat().st_size / 1024:.0f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
