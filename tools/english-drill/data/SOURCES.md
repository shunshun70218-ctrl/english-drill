# 資料來源與授權

**這裡的每一個欄位都來自可查證的公開辭典或語料，沒有一項是 AI 生成的。**
會這樣堅持是因為：發音教錯比不教更糟，中譯錯了會一路錯到考場。

| 檔案 | 提供什麼 | 來源 | 授權 |
|---|---|---|---|
| `cmudict.dict` | 發音、重音落在第幾音節（美式） | [CMU Pronouncing Dictionary](https://github.com/cmusphinx/cmudict) | BSD 式，可再散布 |
| `hyph_en_US.dic` | Liang 斷字樣式（拼字怎麼切音節） | [LibreOffice dictionaries](https://github.com/LibreOffice/dictionaries) | LGPL / MPL |
| `ngsl.csv` | New General Service List 2809 字 + SFI 頻率排名 | Browne & Culligan, [newgeneralservicelist.org](https://www.newgeneralservicelist.org/) | CC BY-SA |
| `tsl.csv` | TOEIC Service List 1268 字 + 英文例句 | Browne & Culligan | CC BY-SA |
| `count_1w.txt` | 33 萬字詞頻表（Google Web 1T 語料） | [norvig.com/ngrams](https://norvig.com/ngrams/) | 公開 |
| `ecdict-subset.csv` | 中譯、詞性、考試標記（cet4/cet6/toefl/ielts/gre） | [ECDICT](https://github.com/skywind3000/ECDICT) | MIT |
| `tatoeba-cmn-eng.tsv` | 中英對照例句 32,028 組 | [Tatoeba](https://tatoeba.org/) 經 [manythings.org](https://www.manythings.org/anki/) | CC BY 2.0 FR |
| `STCharacters.txt` / `STPhrases.txt` | 簡體轉繁體對照 | [OpenCC](https://github.com/BYVoid/OpenCC) | Apache 2.0 |

`ecdict-subset.csv` 是從 ECDICT 完整的 66 MB `ecdict.csv` 抽出這 2000 字的三個欄位而來，
避免把整份辭典塞進 repo。單字表若有變動，重新抓完整檔再抽一次即可。

## 幾個關鍵決定，以及為什麼

**為什麼 NGSL 與 TSL 要合併？**
TSL 是設計來「補充」NGSL 的，收的是一般高頻表之外的多益商務字。
只取 NGSL 前 2000 字的話，多益專用字只會混進 3 個——等於白做。
所以做法是 TSL 1245 字全收，剩下 755 個名額才給 NGSL 高頻字。

**難度怎麼排？**
用 `count_1w.txt` 的實際語料詞頻，頻率越高排越前面。
不是照字母，也不是我憑感覺。實測結果：第 1 組是 page、search、information，
第 20 組是 brainstorm、signify、familiarize，坡度合理。
多益專用字的比例也從第 1 組的 8% 自然升到第 18–20 組的 100%。

**音節數對不上時怎麼辦？**
CMUdict 決定音節數與重音位置，斷字樣式去湊出同樣節數的拼字切分。
湊不出來就改用母音群備援演算法，還是不行就**誠實不標重音**，不猜。

**已知限制**
ECDICT 給的是該字的第一個釋義，不一定是這個例句裡的意思。
例如 `free` 取到「自由的」，但例句講的是「免費的」。
遇到這種要修，直接改 `wordbank/toeic-2000.json` 就好，重跑不會覆蓋手改的內容——
但要注意 `build_toeic2000.py` 會整份重產，手改前先確認不會再跑那支。
