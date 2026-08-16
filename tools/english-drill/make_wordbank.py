#!/usr/bin/env python3
"""把單字庫 JSON 變成可以背的字卡頁。

    python3 tools/english-drill/make_wordbank.py                    # 建置 + 打包
    python3 tools/english-drill/make_wordbank.py --no-example-audio # 不產例句音檔（檔案小很多）

流程：讀 wordbank/*.json → 用 phonetics.py 補音節/音標/重音 → say 產發音 → 產字卡頁。
你只需要在 JSON 裡填 term / pos / zh / example_en / example_zh，其餘欄位自動補。
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import phonetics  # noqa: E402
import tts  # noqa: E402
from make_unit import ROOT, TEMPLATES, embed_json  # noqa: E402

BANK_DIR = ROOT / "wordbank"
OUT_DIR = ROOT / "build"
WORD_RATE = 135          # 單字唸慢一點，每個音節聽得清楚
EXAMPLE_RATE = 155


def _digest(text: str, voice: str, rate: int) -> str:
    return hashlib.sha1(f"{text}|{voice}|{rate}".encode("utf-8")).hexdigest()


def load_banks() -> list[dict]:
    banks = []
    for path in sorted(BANK_DIR.glob("*.json")):
        bank = json.loads(path.read_text(encoding="utf-8"))
        bank["_path"] = path
        banks.append(bank)
    if not banks:
        raise SystemExit(f"{BANK_DIR} 底下沒有任何單字庫 JSON")
    return banks


def check_duplicates(bank: dict) -> None:
    seen: dict[str, str] = {}
    for theme in bank["themes"]:
        for word in theme["words"]:
            key = word["term"].lower()
            if key in seen:
                print(f"  ⚠️  「{word['term']}」同時出現在 {seen[key]} 與 {theme['name']}")
            seen[key] = theme["name"]


def enrich_words(bank: dict) -> tuple[int, int]:
    """補上音節、音標、重音。回傳 (總字數, 音標查不到的字數)。"""
    total = missing = 0
    for theme in bank["themes"]:
        for word in theme["words"]:
            info = phonetics.analyze(word["term"])
            word["syllables"] = info["syllables"]
            word["stress"] = info["stress"]
            word["ipa"] = info["ipa"]
            total += 1
            if not info["ipa"]:
                missing += 1
                print(f"  ⚠️  CMUdict 查不到「{word['term']}」，不會顯示音標")
    return total, missing


def build_audio(bank: dict, audio_dir: Path, with_examples: bool, force: bool) -> dict:
    audio_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = audio_dir / ".manifest.json"

    old = {}
    if manifest_path.exists() and not force:
        try:
            old = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            old = {}

    voice = bank.get("voice", "Samantha")
    manifest, made, reused = {}, 0, 0

    for theme in bank["themes"]:
        for index, word in enumerate(theme["words"], 1):
            jobs = [(f"{theme['slug']}-{index:02d}-w", word["term"], WORD_RATE)]
            if with_examples and word.get("example_en"):
                jobs.append((f"{theme['slug']}-{index:02d}-e", word["example_en"], EXAMPLE_RATE))

            for key, text, rate in jobs:
                filename = f"{key}.m4a"
                target = audio_dir / filename
                digest = _digest(text, voice, rate)
                cached = old.get(key)

                if cached and cached.get("hash") == digest and target.exists() and target.stat().st_size > 0:
                    manifest[key] = cached
                    reused += 1
                else:
                    tts.synthesize(text, voice, rate, target)
                    manifest[key] = {"hash": digest, "file": filename, "dur": tts.duration(target)}
                    made += 1

            word["audio_key"] = f"{theme['slug']}-{index:02d}"

    wanted = {entry["file"] for entry in manifest.values()}
    for stale in audio_dir.glob("*.m4a"):
        if stale.name not in wanted:
            stale.unlink()

    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  音檔：新產 {made}、沿用 {reused}")
    return manifest


def attach_audio(bank: dict, manifest: dict, audio_dir: Path) -> None:
    """把音檔轉成內嵌 data URI 掛回每個字。"""
    import base64

    cache: dict[str, str] = {}

    def uri(filename: str) -> str:
        if filename not in cache:
            raw = (audio_dir / filename).read_bytes()
            cache[filename] = "data:audio/mp4;base64," + base64.b64encode(raw).decode("ascii")
        return cache[filename]

    for theme in bank["themes"]:
        for word in theme["words"]:
            key = word.pop("audio_key")
            word["audio"] = uri(manifest[f"{key}-w"]["file"])
            example = manifest.get(f"{key}-e")
            if example:
                word["example_audio"] = uri(example["file"])


def render(banks: list[dict]) -> Path:
    css = (TEMPLATES / "player.css").read_text(encoding="utf-8")
    extra_css = (TEMPLATES / "wordbank.css").read_text(encoding="utf-8")
    js = (TEMPLATES / "wordbank.js").read_text(encoding="utf-8")

    payload = [
        {
            "title": bank["title"],
            "title_en": bank.get("title_en", ""),
            "themes": [
                {"slug": t["slug"], "name": t["name"], "words": t["words"]}
                for t in bank["themes"]
            ],
        }
        for bank in banks
    ]

    page = f"""<title>多益單字卡</title>
<style>
{css}
{extra_css}
</style>

<div class="wrap">
  <header class="top">
    <h1 class="top__title">多益單字卡</h1>
    <p class="top__en">TOEIC Vocabulary Flashcards</p>
    <div class="meta" id="bank-meta"></div>
  </header>
  <div id="app"></div>
  <p class="hint" style="margin-top:28px">
    手機上想當 app 用：Safari 分享鍵 → 加入主畫面。熟練度記在這台裝置上。
  </p>
</div>

<script id="bank-data" type="application/json">{embed_json(payload)}</script>
<script>
{js}
</script>
"""

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "wordbank.html"
    out.write_text(page, encoding="utf-8")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="產生多益單字卡頁")
    parser.add_argument("--no-example-audio", action="store_true", help="不產例句音檔，頁面會小很多")
    parser.add_argument("--force", action="store_true", help="忽略快取，音檔全部重產")
    args = parser.parse_args()

    banks = load_banks()
    for bank in banks:
        print(f"建置 {bank['title']}（{bank['_path'].name}）")
        check_duplicates(bank)
        total, missing = enrich_words(bank)
        audio_dir = OUT_DIR / "wordbank-audio" / bank["_path"].stem
        manifest = build_audio(bank, audio_dir, not args.no_example_audio, args.force)
        attach_audio(bank, manifest, audio_dir)
        themes = len(bank["themes"])
        print(f"  {themes} 個主題、{total} 個單字" + (f"、{missing} 個查不到音標" if missing else "、音標全部查得到"))

    out = render(banks)
    size_mb = out.stat().st_size / 1024 / 1024
    print(f"\n打包完成：{out}（{size_mb:.1f} MB）")
    if size_mb > 15:
        print("  ⚠️  超過 15 MB，接近發佈上限 16 MB。可以加 --no-example-audio 縮小。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
