"""TTS 抽象層。

目前用 macOS 內建的 `say`（免費、離線、瞬間產檔）。
日後想換成 OpenAI gpt-4o-mini-tts，只要把 `_openai()` 填完、把 BACKEND 改掉，
其餘程式與所有 unit.json 內容都不用動。
"""

import re
import shutil
import subprocess
from pathlib import Path

# "say" | "openai"
BACKEND = "say"

# 這台 Mac 上唯一兩個自然音色（其餘 en_US/en_GB 音色是機器人特效音）。
# 想加音色：系統設定 → 輔助使用 → 朗讀內容 → 系統聲音 → 管理聲音，下載 Premium 版本。
KNOWN_GOOD_VOICES = ("Samantha", "Daniel")


class TTSError(RuntimeError):
    pass


def synthesize(text: str, voice: str, rate: int, out_path) -> Path:
    """把 text 合成語音存到 out_path（.m4a）。回傳 Path。"""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if BACKEND == "say":
        return _say(text, voice, rate, out_path)
    if BACKEND == "openai":
        return _openai(text, voice, rate, out_path)
    raise TTSError(f"不認得的 TTS backend：{BACKEND}")


def _say(text: str, voice: str, rate: int, out_path: Path) -> Path:
    if shutil.which("say") is None:
        raise TTSError("找不到 `say` 指令——這支工具只能在 macOS 上跑。")

    result = subprocess.run(
        [
            "say",
            "-v", voice,
            "-r", str(rate),
            "-o", str(out_path),
            "--data-format=aac",
            text,
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise TTSError(
            f"say 失敗（voice={voice}）：{result.stderr.strip() or '沒有錯誤訊息'}\n"
            f"文字：{text[:60]}"
        )
    if not out_path.exists() or out_path.stat().st_size == 0:
        raise TTSError(f"say 回報成功但沒產出檔案：{out_path}")
    return out_path


def _openai(text: str, voice: str, rate: int, out_path: Path) -> Path:
    raise NotImplementedError(
        "OpenAI TTS 還沒接。要接的話：讀 ~/.openai.env 取 OPENAI_API_KEY，"
        "呼叫 audio/speech（model=gpt-4o-mini-tts、response_format=aac），"
        "把回傳的 bytes 寫進 out_path 即可，其他地方都不用改。"
    )


def duration(path) -> float:
    """回傳音檔長度（秒）。跟讀留白時間要靠它，所以建置期就先算好存進 unit 資料。"""
    path = Path(path)
    if shutil.which("afinfo"):
        result = subprocess.run(["afinfo", str(path)], capture_output=True, text=True)
        match = re.search(r"estimated duration:\s*([\d.]+)\s*sec", result.stdout)
        if match:
            return round(float(match.group(1)), 3)
    # afinfo 不在或格式變了：用檔案大小粗估（AAC 約 24 kB/s），總比整個爛掉好。
    return round(max(0.8, path.stat().st_size / 24000), 3)


def available_voices() -> list[str]:
    """列出系統實際裝了哪些英文音色，用來檢查 unit.json 指定的音色存不存在。"""
    if shutil.which("say") is None:
        return []
    result = subprocess.run(["say", "-v", "?"], capture_output=True, text=True)
    voices = []
    for line in result.stdout.splitlines():
        parts = line.split()
        if parts:
            voices.append(parts[0])
    return voices
