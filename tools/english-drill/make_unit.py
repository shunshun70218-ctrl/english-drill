#!/usr/bin/env python3
"""把 unit.json 變成一個可以直接用瀏覽器打開練習的單元頁。

用法：
    python3 tools/english-drill/make_unit.py units/2026-08-16-airport-check-in/unit.json
    python3 tools/english-drill/make_unit.py --all        # 重建所有單元
    python3 tools/english-drill/make_unit.py --index      # 只重建總目錄頁

音檔採增量產生：文字／音色／語速沒變就不重跑 say。
"""

import argparse
import hashlib
import html
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tts  # noqa: E402

TOOL_DIR = Path(__file__).resolve().parent
TEMPLATES = TOOL_DIR / "templates"
ROOT = TOOL_DIR.parent.parent          # 英文學習/
UNITS_DIR = ROOT / "units"

REQUIRED_TOP = ("slug", "title", "level", "date", "scene", "roles", "lines", "vocab")
WORD_RATE_OFFSET = -20                  # 單字唸慢一點，聽清楚每個音節


class UnitError(RuntimeError):
    pass


# ---------------------------------------------------------------- 驗證

def load_unit(path: Path) -> dict:
    try:
        unit = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise UnitError(f"{path} 不是合法 JSON：{exc}") from exc

    missing = [k for k in REQUIRED_TOP if k not in unit]
    if missing:
        raise UnitError(f"{path} 缺少欄位：{', '.join(missing)}")

    roles = unit["roles"]
    for key in ("A", "B"):
        if key not in roles:
            raise UnitError(f"roles 少了 \"{key}\"")
        for field in ("name", "zh", "voice"):
            if not roles[key].get(field):
                raise UnitError(f"roles.{key} 缺少 {field}")
        roles[key].setdefault("rate", 160)

    installed = tts.available_voices()
    if installed:
        for key in ("A", "B"):
            voice = roles[key]["voice"]
            if voice not in installed:
                raise UnitError(
                    f"這台電腦沒有音色 \"{voice}\"（roles.{key}）。"
                    f"目前可用的自然音色：{', '.join(v for v in tts.KNOWN_GOOD_VOICES if v in installed)}"
                )

    if not unit["lines"]:
        raise UnitError("lines 是空的")
    for i, line in enumerate(unit["lines"], 1):
        if line.get("role") not in roles:
            raise UnitError(f"第 {i} 句的 role 是 \"{line.get('role')}\"，但 roles 裡沒有")
        for field in ("en", "zh"):
            if not line.get(field):
                raise UnitError(f"第 {i} 句缺少 {field}")

    for i, word in enumerate(unit["vocab"], 1):
        for field in ("term", "zh"):
            if not word.get(field):
                raise UnitError(f"第 {i} 個單字缺少 {field}")

    unit.setdefault("tips", [])
    unit.setdefault("title_en", "")
    return unit


# ---------------------------------------------------------------- 音檔

def _digest(text: str, voice: str, rate: int) -> str:
    return hashlib.sha1(f"{text}|{voice}|{rate}".encode("utf-8")).hexdigest()


def collect_jobs(unit: dict) -> list[dict]:
    """列出這個單元需要的所有音檔。"""
    roles = unit["roles"]
    jobs = []

    for i, line in enumerate(unit["lines"], 1):
        role = roles[line["role"]]
        jobs.append({
            "key": f"line-{i:02d}",
            "text": line["en"],
            "voice": role["voice"],
            "rate": int(role["rate"]),
        })

    narrator = roles["A"]
    for i, word in enumerate(unit["vocab"], 1):
        jobs.append({
            "key": f"word-{i:02d}",
            "text": word["term"],
            "voice": narrator["voice"],
            "rate": int(narrator["rate"]) + WORD_RATE_OFFSET,
        })
        if word.get("example_en"):
            jobs.append({
                "key": f"ex-{i:02d}",
                "text": word["example_en"],
                "voice": narrator["voice"],
                "rate": int(narrator["rate"]),
            })

    return jobs


def build_audio(unit: dict, unit_dir: Path, force: bool = False) -> dict:
    """產生（或沿用）所有音檔，回傳 {key: {"file":…, "dur":…}}。"""
    audio_dir = unit_dir / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = audio_dir / ".manifest.json"

    old = {}
    if manifest_path.exists() and not force:
        try:
            old = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            old = {}

    manifest, made, reused = {}, 0, 0
    for job in collect_jobs(unit):
        key = job["key"]
        filename = f"{key}.m4a"
        target = audio_dir / filename
        digest = _digest(job["text"], job["voice"], job["rate"])

        cached = old.get(key)
        if cached and cached.get("hash") == digest and target.exists() and target.stat().st_size > 0:
            manifest[key] = cached
            reused += 1
            continue

        tts.synthesize(job["text"], job["voice"], job["rate"], target)
        manifest[key] = {
            "hash": digest,
            "file": filename,
            "dur": tts.duration(target),
        }
        made += 1

    # 清掉已經不需要的舊音檔（例如刪了幾個單字）
    wanted = {entry["file"] for entry in manifest.values()}
    for stale in audio_dir.glob("*.m4a"):
        if stale.name not in wanted:
            stale.unlink()

    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  音檔：新產 {made}、沿用 {reused}")
    return manifest


# ---------------------------------------------------------------- 產頁面

def enrich(unit: dict, manifest: dict) -> dict:
    """把音檔路徑與長度塞進資料，前端就不必再去問檔案。"""
    data = json.loads(json.dumps(unit, ensure_ascii=False))  # 深拷貝，不動原檔

    for i, line in enumerate(data["lines"], 1):
        entry = manifest[f"line-{i:02d}"]
        line["audio"] = f"audio/{entry['file']}"
        line["dur"] = entry["dur"]

    for i, word in enumerate(data["vocab"], 1):
        entry = manifest[f"word-{i:02d}"]
        word["audio"] = f"audio/{entry['file']}"
        word["dur"] = entry["dur"]
        ex = manifest.get(f"ex-{i:02d}")
        if ex:
            word["example_audio"] = f"audio/{ex['file']}"
            word["example_dur"] = ex["dur"]

    data["total_dur"] = round(sum(line["dur"] for line in data["lines"]), 1)
    return data


def embed_json(data: dict) -> str:
    """安全地把 JSON 放進 <script> —— 關鍵是不能讓 </script> 提早結束標籤。"""
    raw = json.dumps(data, ensure_ascii=False)
    return raw.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def render_unit(data: dict, unit_dir: Path) -> Path:
    template = (TEMPLATES / "unit.html.tpl").read_text(encoding="utf-8")
    page = (
        template
        .replace("{{TITLE}}", html.escape(data["title"]))
        .replace("{{TITLE_EN}}", html.escape(data.get("title_en") or ""))
        .replace("{{LEVEL}}", html.escape(data["level"]))
        .replace("{{UNIT_JSON}}", embed_json(data))
    )
    out = unit_dir / "index.html"
    out.write_text(page, encoding="utf-8")

    for asset in ("player.js", "player.css"):
        shutil.copyfile(TEMPLATES / asset, unit_dir / asset)
    return out


def rebuild_index() -> Path:
    template = (TEMPLATES / "index.html.tpl").read_text(encoding="utf-8")

    units = []
    for unit_json in sorted(UNITS_DIR.glob("*/unit.json")):
        try:
            unit = json.loads(unit_json.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print(f"  ⚠️  跳過壞掉的 {unit_json}")
            continue
        units.append((unit_json.parent.name, unit))

    units.sort(key=lambda item: (item[1].get("date", ""), item[0]), reverse=True)

    if units:
        cards = "\n".join(
            f'''      <a class="unit-card" href="units/{html.escape(folder)}/index.html">
        <div class="unit-card__title">{html.escape(unit.get("title", folder))}</div>
        <div class="unit-card__en">{html.escape(unit.get("title_en", ""))}</div>
        <div class="unit-card__scene">{html.escape(unit.get("scene", ""))}</div>
        <div class="unit-card__meta">
          <span class="pill">{html.escape(unit.get("level", ""))}</span>
          <span>{len(unit.get("lines", []))} 句</span>
          <span>{len(unit.get("vocab", []))} 個單字</span>
          <span class="unit-card__date">{html.escape(unit.get("date", ""))}</span>
        </div>
      </a>'''
            for folder, unit in units
        )
    else:
        cards = '      <p class="empty">還沒有任何單元。跟 Claude 說「幫我做一個 ⟨情境⟩ 的單元」就會出現在這裡。</p>'

    page = template.replace("{{CARDS}}", cards).replace("{{COUNT}}", str(len(units)))
    out = ROOT / "index.html"
    out.write_text(page, encoding="utf-8")
    print(f"總目錄頁已更新：{out}（{len(units)} 個單元）")
    return out


# ---------------------------------------------------------------- 進入點

def build_one(unit_json: Path, force: bool = False) -> None:
    unit_dir = unit_json.parent
    print(f"建置 {unit_dir.name}")
    unit = load_unit(unit_json)
    manifest = build_audio(unit, unit_dir, force=force)
    data = enrich(unit, manifest)
    page = render_unit(data, unit_dir)
    print(f"  單元頁：{page}（對話全長約 {data['total_dur']} 秒）")


def main() -> int:
    parser = argparse.ArgumentParser(description="產生英文情境對話練習單元")
    parser.add_argument("unit_json", nargs="?", help="單元的 unit.json 路徑")
    parser.add_argument("--all", action="store_true", help="重建所有單元")
    parser.add_argument("--index", action="store_true", help="只重建總目錄頁")
    parser.add_argument("--force", action="store_true", help="忽略快取，全部音檔重產")
    args = parser.parse_args()

    try:
        if args.index:
            rebuild_index()
            return 0

        if args.all:
            targets = sorted(UNITS_DIR.glob("*/unit.json"))
            if not targets:
                print(f"{UNITS_DIR} 底下找不到任何 unit.json")
                return 1
        elif args.unit_json:
            targets = [Path(args.unit_json).resolve()]
            if not targets[0].exists():
                print(f"找不到檔案：{targets[0]}", file=sys.stderr)
                return 1
        else:
            parser.print_help()
            return 1

        for target in targets:
            build_one(target, force=args.force)
        rebuild_index()
        return 0

    except (UnitError, tts.TTSError) as exc:
        print(f"\n❌ {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
