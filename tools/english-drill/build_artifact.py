#!/usr/bin/env python3
"""把所有單元打包成一個自足的 HTML，用來發佈成線上版（手機可用）。

    python3 tools/english-drill/build_artifact.py

輸出：build/practice.html
CSS、JS 全部內聯，音檔轉成 base64 data URI，所以這一個檔案就是完整的 app，
不依賴任何外部檔案或網路資源。
"""

import base64
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_unit import ROOT, TEMPLATES, UNITS_DIR, embed_json, enrich, load_unit  # noqa: E402

OUT = ROOT / "build" / "practice.html"
PAGE_TITLE = "情境英語練習室"


def data_uri(path: Path) -> str:
    return "data:audio/mp4;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def collect_units() -> list[dict]:
    units = []
    for unit_json in sorted(UNITS_DIR.glob("*/unit.json")):
        audio_dir = unit_json.parent / "audio"
        manifest_path = audio_dir / ".manifest.json"
        if not manifest_path.exists():
            print(f"  ⚠️  {unit_json.parent.name} 還沒建置過，跳過（先跑 make_unit.py）")
            continue

        data = enrich(load_unit(unit_json), json.loads(manifest_path.read_text(encoding="utf-8")))

        # 相對路徑換成內嵌音檔
        for line in data["lines"]:
            line["audio"] = data_uri(audio_dir / Path(line["audio"]).name)
        for word in data["vocab"]:
            word["audio"] = data_uri(audio_dir / Path(word["audio"]).name)
            if "example_audio" in word:
                word["example_audio"] = data_uri(audio_dir / Path(word["example_audio"]).name)

        units.append(data)
    return units


def build() -> Path:
    units = collect_units()
    if not units:
        raise SystemExit("找不到任何已建置的單元")

    css = (TEMPLATES / "player.css").read_text(encoding="utf-8")
    js = (TEMPLATES / "player.js").read_text(encoding="utf-8")

    page = f"""<title>{PAGE_TITLE}</title>
<style>
{css}
</style>

<div class="wrap">
  <div class="switcher" id="switcher" role="group" aria-label="選擇單元"></div>
  <div id="app"></div>
  <p class="hint" style="margin-top:28px">
    手機上想當 app 用：Safari 分享鍵 → 加入主畫面。
  </p>
</div>

<script id="all-units" type="application/json">{embed_json(units)}</script>
<script>
{js}
</script>
<script>
(() => {{
  const units = JSON.parse(document.getElementById('all-units').textContent);
  const switcher = document.getElementById('switcher');
  const app = document.getElementById('app');

  const buttons = units.map((unit, index) => {{
    const btn = document.createElement('button');
    btn.className = 'switcher__btn';
    btn.type = 'button';
    btn.textContent = unit.title;
    btn.setAttribute('aria-pressed', 'false');
    btn.addEventListener('click', () => select(index));
    switcher.appendChild(btn);
    return btn;
  }});

  function select(index) {{
    buttons.forEach((btn, i) => btn.setAttribute('aria-pressed', i === index ? 'true' : 'false'));
    EnglishDrill.mount(units[index], app);
    window.scrollTo({{ top: 0, behavior: 'instant' }});
    try {{ localStorage.setItem('drill:unit', units[index].slug); }} catch (e) {{ /* 忽略 */ }}
  }}

  let start = 0;
  try {{
    const saved = localStorage.getItem('drill:unit');
    const found = units.findIndex((u) => u.slug === saved);
    if (found >= 0) start = found;
  }} catch (e) {{ /* 忽略 */ }}

  // 單元只有一個的話就不用顯示切換器
  if (units.length < 2) switcher.hidden = true;
  select(start);
}})();
</script>
"""

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(page, encoding="utf-8")

    size_mb = OUT.stat().st_size / 1024 / 1024
    print(f"打包完成：{OUT}")
    print(f"  {len(units)} 個單元、{sum(len(u['lines']) for u in units)} 句對話、{size_mb:.1f} MB")
    if size_mb > 15:
        print("  ⚠️  超過 15 MB，接近發佈上限 16 MB，要考慮拆成兩個頁面")
    return OUT


if __name__ == "__main__":
    build()
