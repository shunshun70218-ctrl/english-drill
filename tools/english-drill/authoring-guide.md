# 寫 unit.json 的內容準則

> 給 Claude 看的。每次要新增單元時先讀這份，讓所有單元的難度與風格一致。

## 學習者設定

- 程度 **A2–B1**：看得懂大部分句子，但開口會卡
- 目標是**救急能講**，不是閱讀理解 —— 選字準則永遠是「他當下講得出來嗎」
- 母語中文（台灣）

## 對話

- **12–16 句**，念完約 40–60 秒
- 每句 **6–15 個字**。超過 15 字的句子在跟讀時會斷掉，要拆。
- A 是情境裡的「對方」（店員、地勤、櫃檯、同事），B 是「你」
- 一定要放進**這個情境真的會聽到的固定說法**：`Aisle or window?`、`Just the one.`、`Here you go.`、`Sounds good.`
- 數字、時間一律**拼成英文字**（`twenty-two kilos`、`ten forty`），不要寫 `22 kilos` —— TTS 唸阿拉伯數字容易出錯
- 座位號、班機號這種真的長那樣的代號可以保留（`24C`、`gate B12`）
- 結尾要收乾淨（道謝、道別），不要斷在半空
- 中譯用**自然的中文口語**，不要逐字對譯

## 單字

- **8–12 個**，都要是這段對話裡真的出現過、或直接對應的字
- 優先收：情境專有名詞（`boarding pass`）、動詞片語（`check a bag`、`go through security`）
- 可以補 1–2 個對話沒出現但同情境一定會用到的對照字（例如收了 `aisle seat` 就順手收 `window seat`）
- 每個字都要有 `example_en` / `example_zh`，例句要**比對話原句更短更好記**，不要直接抄對話
- `pos` 用 `n.` / `v.` / `adj.` / `phr.`

## tips

- **3–5 條**，針對台灣學習者
- 優先寫這三類：
  1. **發音陷阱**（`aisle` 的 s 不發音）
  2. **中式英文**（托運不是 send，是 check a bag）
  3. **道地語感**（`Just the one.` 的 the 帶有「就只有這件」的語氣）
- 不要寫文法課本抄得到的東西

## 欄位格式

```jsonc
{
  "slug": "airport-check-in",          // 英文 kebab-case，跟資料夾名的日期後半段一致
  "title": "機場報到櫃檯",
  "title_en": "Checking In at the Airport",
  "level": "A2–B1",
  "date": "2026-08-16",                 // 建立日期
  "scene": "兩三句中文，說清楚你是誰、要辦成什麼事",
  "roles": {
    "A": { "name": "Agent", "zh": "地勤人員", "voice": "Samantha", "rate": 155 },
    "B": { "name": "You",   "zh": "旅客（你）", "voice": "Daniel",  "rate": 155 }
  },
  "lines": [{ "role": "A", "en": "...", "zh": "..." }],
  "vocab": [{ "term": "...", "pos": "n.", "zh": "...",
              "example_en": "...", "example_zh": "..." }],
  "tips": ["..."]
}
```

- 資料夾命名：`units/YYYY-MM-DD-<slug>/unit.json`
- `roles.A.name` 隨情境換（`Barista`、`Agent`、`Receptionist`），`roles.B.name` 固定 `You`
- `voice` 只能填 `Samantha`（美 女）或 `Daniel`（英 男），填錯產生器會直接擋下來
- `rate` 155 是預設。要更慢就調到 140，不要低於 130（會變得不自然）

## 寫完之後

```bash
python3 tools/english-drill/make_unit.py units/<資料夾>/unit.json
```

產生器會擋掉缺欄位、角色對不上、音色不存在這些錯誤。跑完把單元頁路徑給使用者。
