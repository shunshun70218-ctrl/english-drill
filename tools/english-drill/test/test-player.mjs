/* 在 jsdom 裡把播放器整個驅動一遍，檢查五個關卡的行為。
 *
 *   npm install jsdom      # 裝在任何暫存目錄，不要裝進專案資料夾
 *   node tools/english-drill/test/test-player.mjs [單元資料夾路徑]
 *
 * Audio 與 requestAnimationFrame 換成假的（虛擬時鐘），所以幾秒內就跑完整段流程。
 */

import fs from 'node:fs';
import { createRequire } from 'node:module';

// jsdom 刻意不裝進專案資料夾（會讓 Google Drive 同步幾萬個小檔）。
// 裝在任何暫存目錄，再用 JSDOM_HOME 指過去即可。
const require = createRequire(
  process.env.JSDOM_HOME ? process.env.JSDOM_HOME.replace(/\/?$/, '/') : import.meta.url,
);
const { JSDOM } = require('jsdom');

const DEFAULT_UNIT = '/Users/shun/Library/CloudStorage/GoogleDrive-shunshun70218@gmail.com/我的雲端硬碟/cloudai data/英文學習/units/2026-08-16-airport-check-in';
const UNIT = process.argv[2] || DEFAULT_UNIT;

// 把外部 player.js 直接內聯，jsdom 才會照順序執行到頁面底部的 mount。
// 替換字串一定要用 function 形式——player.js 裡的 $(' 與 $$( 在替換字串語法裡是特殊符號，
// 直接傳字串會被當成 $' / $$ 展開，把程式碼絞爛。
const html = fs.readFileSync(`${UNIT}/index.html`, 'utf8')
  .replace('<script src="player.js"></script>',
    () => `<script>${fs.readFileSync(`${UNIT}/player.js`, 'utf8')}</script>`);

const errors = [];
const dom = new JSDOM(html, {
  url: 'http://localhost/',
  runScripts: 'dangerously',
  beforeParse(win) {
    // ---- 虛擬時鐘：每個 rAF tick 前進 100ms，等待秒數瞬間跑完
    let vnow = 0;
    win.performance.now = () => vnow;
    win.requestAnimationFrame = (cb) => setTimeout(() => { vnow += 100; cb(vnow); }, 0);
    win.cancelAnimationFrame = (id) => clearTimeout(id);

    // ---- 假的 Audio：立刻「播完」，並記錄播了什麼、用什麼速度
    win.Audio = class FakeAudio {
      constructor() {
        win.__audioCount = (win.__audioCount || 0) + 1;
        this._h = {}; this.src = ''; this.playbackRate = 1; this.currentTime = 0; this._pending = null;
      }
      addEventListener(type, fn) { (this._h[type] ||= []).push(fn); }
      removeEventListener(type, fn) { this._h[type] = (this._h[type] || []).filter((f) => f !== fn); }
      _fire(type) { (this._h[type] || []).slice().forEach((fn) => fn()); }
      play() {
        win.__playLog.push({ src: this.src, rate: this.playbackRate });
        clearTimeout(this._pending);
        this._pending = setTimeout(() => this._fire('ended'), 0);
        return Promise.resolve();
      }
      pause() { clearTimeout(this._pending); this._pending = null; }
    };
    win.__playLog = [];
    win.addEventListener('error', (e) => errors.push(String(e.error || e.message)));
  },
});

const { window } = dom;
const playLog = window.__playLog;

const $ = (sel) => window.document.querySelector(sel);
const $$ = (sel) => Array.from(window.document.querySelectorAll(sel));
const click = (el) => el.dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
const tab = (name) => click($(`.tab[data-panel="${name}"]`));
const settle = async (ticks) => { for (let i = 0; i < ticks; i++) await new Promise((r) => setTimeout(r, 0)); };

const UNIT_DATA = JSON.parse($('#unit-data').textContent);
const nameOf = (src) => String(src).split('/').pop().replace('.m4a', '');
const lineKey = (i) => `line-${String(i + 1).padStart(2, '0')}`;

const results = [];
const check = (name, ok, detail = '') => {
  results.push({ name, ok });
  console.log(`${ok ? '✅' : '❌'} ${name}${detail ? ' — ' + detail : ''}`);
};

// ---------- 掛載 ----------
check('掛載沒有丟錯', errors.length === 0, errors.join('; '));
check(`逐句對照渲染出 ${UNIT_DATA.lines.length} 列`, $$('#script-list .line').length === UNIT_DATA.lines.length);
check(`單字卡渲染出 ${UNIT_DATA.vocab.length} 張`, $$('#vocab-list .card').length === UNIT_DATA.vocab.length);
check(`提醒區列出 ${UNIT_DATA.tips.length} 條`, $$('#tips-list li').length === UNIT_DATA.tips.length);
check('頁首帶入單元標題', $('.top__title').textContent === UNIT_DATA.title);
check('預設停在「盲聽」', $('#panel-blind').classList.contains('is-active'));
check('角色按鈕帶入角色名', $('#rp-role-a').textContent.includes(UNIT_DATA.roles.A.name));

// ---------- 關卡 2：單句播放、慢速、重複 ----------
tab('script');
playLog.length = 0;
const firstRow = $('#script-list .line');
click(firstRow.querySelector('[data-rate="1"]'));
await settle(20);
check('點單句 ▶ 播放正確音檔', playLog.length === 1 && nameOf(playLog[0].src) === 'line-01', JSON.stringify(playLog[0]));

playLog.length = 0;
click(firstRow.querySelector('[data-rate="0.75"]'));
await settle(20);
check('🐢 慢速用 playbackRate 0.75', playLog[0]?.rate === 0.75);

playLog.length = 0;
click($('[data-repeat="3"]'));
click(firstRow.querySelector('[data-rate="1"]'));
await settle(200);
check('設定 ×3 後同一句播三次', playLog.length === 3, `實際 ${playLog.length} 次`);
click($('[data-repeat="3"]'));

check('中譯預設收起來', $('#script-list .line__zh').hidden === true);
click($('#script-zh'));
check('點「顯示中譯」後展開', $('#script-list .line__zh').hidden === false);

// ---------- 關卡 1：盲聽整段 ----------
tab('blind');
playLog.length = 0;
click($('#blind-play'));
await settle(1500);
const blindOrder = playLog.map((p) => nameOf(p.src));
check(`盲聽照順序播完 ${UNIT_DATA.lines.length} 句`,
  JSON.stringify(blindOrder) === JSON.stringify(UNIT_DATA.lines.map((_, i) => lineKey(i))),
  `播了 ${blindOrder.length} 句`);
check('播完後按鈕回到可再播', $('#blind-play').textContent.includes('再聽一次'), $('#blind-play').textContent);

// ---------- 關卡 4：跟讀 ----------
tab('shadow');
playLog.length = 0;
click($('#shadow-slow'));
click($('#shadow-toggle'));
await settle(60);
check('跟讀慢速設定生效', playLog[0]?.rate === 0.75);
check('跟讀畫面出現提示', /換你唸|仔細聽/.test($('#shadow-stage').textContent),
  $('#shadow-stage').textContent.trim().slice(0, 36));
click($('#shadow-toggle'));
const afterStop = playLog.length;
await settle(300);
check('按停之後確實不再播', playLog.length === afterStop, `停時 ${afterStop} → 現在 ${playLog.length}`);

// ---------- 關卡 5：角色扮演 ----------
tab('roleplay');
playLog.length = 0;
click($('[data-role="A"]'));      // 我演 A，所以 A 的句子應該全部靜音
click($('#rp-toggle'));
await settle(4000);
const played = new Set(playLog.map((p) => nameOf(p.src)));
const leakedA = UNIT_DATA.lines.map((l, i) => ({ ...l, key: lineKey(i) })).filter((l) => l.role === 'A' && played.has(l.key));
const missingB = UNIT_DATA.lines.map((l, i) => ({ ...l, key: lineKey(i) })).filter((l) => l.role === 'B' && !played.has(l.key));
check('演 A 時，A 的句子全部靜音', leakedA.length === 0, leakedA.map((l) => l.key).join(','));
check('演 A 時，B 的句子照常播出', missingB.length === 0, missingB.map((l) => l.key).join(','));

// ---------- 分頁記憶 ----------
check('分頁選擇寫進 localStorage',
  window.localStorage.getItem(`drill:${UNIT_DATA.slug}:tab`) === 'roleplay',
  String(window.localStorage.getItem(`drill:${UNIT_DATA.slug}:tab`)));

// ---------- 手機關鍵：整段只用同一個 audio 元素 ----------
check('全程只建立 1 個 audio 元素（iOS 才不會第一句之後靜音）',
  window.__audioCount === 1,
  `這輪播了 ${playLog.length}+ 次，共建立 ${window.__audioCount} 個 audio 元素`);

const failed = results.filter((r) => !r.ok);
console.log(`\n${results.length - failed.length} / ${results.length} 通過`);
process.exit(failed.length ? 1 : 0);
