# English Drill — 英文情境對話練習產生器

指定一個情境 → 產生一段約一分鐘的對話 → 變成一個可以直接用瀏覽器打開練習的單元頁。

## 平常怎麼用

跟 Claude 說「**幫我做一個〈情境〉的單元**」就好。Claude 會寫 `unit.json`、跑產生器、告訴你檔案在哪。

要自己動手的話：

```bash
cd "英文學習"
python3 tools/english-drill/make_unit.py units/2026-08-16-airport-check-in/unit.json
```

| 指令 | 用途 |
|---|---|
| `make_unit.py <unit.json>` | 建置單一單元 |
| `make_unit.py --all` | 重建所有單元 |
| `make_unit.py --index` | 只重建總目錄頁 |
| `make_unit.py <unit.json> --force` | 忽略快取，音檔全部重產 |
| `build_artifact.py` | 把所有單元打包成 `build/practice.html`（手機線上版） |

產完直接用瀏覽器打開 `英文學習/index.html`。不需要 server。

## 手機版

`build_artifact.py` 會把 CSS、JS、以及全部音檔（base64）壓成**一個自足的 HTML**，
發佈之後就是一個可以在手機上開的網址，Safari 分享 →「加入主畫面」會像 app 一樣。

```bash
python3 tools/english-drill/build_artifact.py     # → build/practice.html
```

加了新單元要重跑這支，然後請 Claude 用**同一個檔案路徑**重新發佈，網址不會變。
目前 2 個單元約 3.9 MB，發佈上限 16 MB，大概還能再塞六七個單元。

⚠️ **iOS 的地雷**：Safari 只讓「使用者手勢解鎖過的那一個」audio 元素繼續播放。
所以 `player.js` 全程共用同一個 audio 元素、只換 `src`（見 `getAudio()`）。
如果哪天改成每句 `new Audio()`，桌機看起來一切正常，但手機會在第一句之後整段安靜。
回歸測試有一項專門守這件事。

## 單元頁的五個關卡

1. **盲聽** — 不看字整段聽，先訓練耳朵抓大意
2. **逐句對照** — 逐句點播、慢速 0.75x、重複 ×2／×3，中譯預設收起
3. **單字卡** — 單字與例句都能單獨播
4. **跟讀** — 播一句 → 留白等你唸 → 下一句（留白長度 = 該句長度 × 1.3）
5. **角色扮演** — 選一個角色，他的台詞會靜音只給中文提示，留白等你講

分頁停在哪一關會記在 `localStorage`。跟讀與角色扮演可用**空白鍵**暫停／繼續。

## 檔案怎麼分工

```
tools/english-drill/
├── make_unit.py          # 主程式：驗證 → 產音檔 → 產頁面 → 重建目錄
├── tts.py                # TTS 抽象層（目前 macOS say）
├── authoring-guide.md    # 寫 unit.json 的內容準則
└── templates/            # 頁面骨架與播放器（改這裡，跑 --all 套用到所有單元）

units/<日期>-<slug>/
├── unit.json             # ← 唯一的內容真相來源，只有這個要手改
├── index.html            # 產生物
├── player.js / player.css# 產生物（從 templates 複製）
└── audio/                # 產生物，含 .manifest.json 快取記錄
```

`unit.json` 以外全是產生物。整個 `audio/` 跟 `index.html` 刪掉再跑一次就會回來。

音檔採**增量產生**：文字／音色／語速沒變就不重跑 `say`。改幾句話只會重產那幾句。

## 音色

這台電腦目前只有兩個自然音色可用：

| 角色 | 音色 | 口音 |
|---|---|---|
| A | Samantha | 美式女聲 |
| B | Daniel | 英式男聲 |

其餘 `say -v '?'` 列出的英文音色多半是機器人特效音（Bells、Zarvox…），不要用。

**想要更好的音質**：系統設定 → 輔助使用 → 朗讀內容 → 系統聲音 → 管理聲音，
下載 Ava、Tom、Evan、Nicky 的 **Premium** 版本，然後把 `unit.json` 的 `roles.X.voice` 換掉、跑 `--force` 重產。

## 之後想換成 OpenAI TTS

`tts.py` 裡的 `_openai()` 是留好的空位。填完那個函式、把 `BACKEND` 改成 `"openai"`，
其他程式跟所有 `unit.json` 都不用動。API key 已經在 `~/.openai.env`。

## 多益單字庫

```bash
python3 tools/english-drill/make_wordbank.py                    # → build/wordbank.html
python3 tools/english-drill/make_wordbank.py --no-example-audio # 不產例句音檔，檔案小 4 倍
```

內容在 `wordbank/*.json`。**只要填 `term` / `pos` / `zh` / `example_en` / `example_zh`**，
音節、音標、重音位置由 `phonetics.py` 自動產生，不要手填。

字卡用回合制：一輪排入所有「不會」與「有印象」的字，加上兩成「熟了」的字複習；
標「不會」的字會在本輪隔四張後再考一次。熟練度存在瀏覽器的 localStorage。

### 音標怎麼來的

| 資料 | 檔案 | 負責 |
|---|---|---|
| CMU Pronouncing Dictionary | `data/cmudict.dict` | 怎麼唸、重音在第幾個音節（美式） |
| Liang 斷字樣式 | `data/hyph_en_US.dic` | 字母怎麼分段 |

兩份都是公開資料，音標**不是 AI 生的**。流程是：CMUdict 決定音節數與重音位置 →
斷字樣式去湊出同樣節數的拼字切分 → 湊不出來就改用母音群備援演算法 → 還是不行就誠實不標重音。

目前 96 個字裡 94 個（98%）標得出重音。`phonetics.py` 可以單獨執行看切分結果：

```bash
python3 tools/english-drill/phonetics.py
```

三條守則寫在程式裡，改動時不要拿掉：
- **每個音節必須含母音字母** —— 否則會切出 `p·re·sen·tation`
- **不從雙字母組合中間切開**（ch/sh/th…）—— 否則會切出 `broc·hure`
- **音節數對不上就不標重音** —— 寧可不標，不要標錯位置

## 改了 templates 之後要跑的回歸測試

`test/test-player.mjs` 會在 jsdom 裡把播放器整個驅動一遍（Audio 與計時器換成假的，幾秒跑完），
檢查五個關卡的行為：單句播放、慢速 0.75x、重複次數、盲聽順序、按停真的會停、角色扮演靜音的是正確角色。

```bash
cd /tmp/drill-test && npm install jsdom     # 裝在任何暫存目錄，不要裝進這個資料夾
                                            # （Google Drive 會被幾萬個小檔拖垮）
export JSDOM_HOME=/tmp/drill-test
node tools/english-drill/test/test-player.mjs "units/2026-08-16-airport-check-in"   # 25 項
node tools/english-drill/test/test-artifact.mjs                                     # 12 項
node tools/english-drill/test/test-wordbank.mjs                                     # 25 項
```

`test-player.mjs` 不給單元路徑就跑機場那一單元。
**動過 `templates/` 底下任何東西就跑一次**——網頁沒有 server 也不會報錯，壞掉只會安靜地不出聲。

`test-artifact.mjs` 跟 `test-wordbank.mjs` 讀的是 `build/` 底下打包好的檔案，
所以要先跑 `build_artifact.py` / `make_wordbank.py` 再測。

## 已知限制

- 只能在 macOS 跑（靠內建的 `say` 與 `afinfo`）
- 沒有錄音回放、沒有發音評分、沒有跨單元的單字庫與複習排程 —— 刻意不做，先把單元本身練起來
