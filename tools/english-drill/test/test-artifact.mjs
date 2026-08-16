import fs from 'node:fs';
import { createRequire } from 'node:module';

// jsdom 刻意不裝進專案資料夾（會讓 Google Drive 同步幾萬個小檔）。
// 裝在任何暫存目錄，再用 JSDOM_HOME 指過去即可。
const require = createRequire(
  process.env.JSDOM_HOME ? process.env.JSDOM_HOME.replace(/\/?$/, '/') : import.meta.url,
);
const { JSDOM } = require('jsdom');

const html = fs.readFileSync('/Users/shun/Library/CloudStorage/GoogleDrive-shunshun70218@gmail.com/我的雲端硬碟/cloudai data/英文學習/build/practice.html', 'utf8');
const errors = [];
const dom = new JSDOM(html, { url: 'http://localhost/', runScripts: 'dangerously', beforeParse(win) {
  let vnow = 0;
  win.performance.now = () => vnow;
  win.requestAnimationFrame = (cb) => setTimeout(() => { vnow += 100; cb(vnow); }, 0);
  win.cancelAnimationFrame = (id) => clearTimeout(id);
  win.__playLog = [];
  win.Audio = class { constructor(){ win.__audioCount=(win.__audioCount||0)+1; this._h={}; this.src=''; this.playbackRate=1; this.currentTime=0; this._p=null; }
    addEventListener(t,f){ (this._h[t] ||= []).push(f); }
    removeEventListener(t,f){ this._h[t]=(this._h[t]||[]).filter(x=>x!==f); }
    _fire(t){ (this._h[t]||[]).slice().forEach(f=>f()); }
    play(){ win.__playLog.push(this.src.slice(0,40)); clearTimeout(this._p); this._p=setTimeout(()=>this._fire('ended'),0); return Promise.resolve(); }
    pause(){ clearTimeout(this._p); this._p=null; } };
  win.scrollTo = () => {};
  win.addEventListener('error', e => errors.push(String(e.error||e.message)));
}});
const w = dom.window, $ = s => w.document.querySelector(s), $$ = s => [...w.document.querySelectorAll(s)];
const click = el => el.dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
const settle = async n => { for (let i=0;i<n;i++) await new Promise(r=>setTimeout(r,0)); };
const out=[]; const check=(n,ok,d='')=>{out.push(ok);console.log(`${ok?'✅':'❌'} ${n}${d?' — '+d:''}`)};

check('載入沒有丟錯', errors.length===0, errors.join('; '));
check('標題是 情境英語練習室', w.document.title === '情境英語練習室', w.document.title);
const UNITS = JSON.parse($('#all-units').textContent);
const btns = $$('.switcher__btn');
check(`切換器有 ${UNITS.length} 個單元`, btns.length===UNITS.length, btns.map(b=>b.textContent).join(' / '));
check('預設掛載第一個單元', $('.top__title').textContent === btns[0].textContent, $('.top__title').textContent);
check('第一顆是 pressed 狀態', btns[0].getAttribute('aria-pressed')==='true');

// 開始播放後切換單元，確認舊的播放有被切斷
click($('.tab[data-panel="blind"]'));
click($('#blind-play'));
await settle(30);
const before = w.__playLog.length;
check('盲聽有在播', before > 0, `已播 ${before} 句`);
click(btns[btns.length-1]);
await settle(5);
const atSwitch = w.__playLog.length;
await settle(400);
check('切換單元會切斷前一個單元的播放', w.__playLog.length === atSwitch, `切換時 ${atSwitch} → 現在 ${w.__playLog.length}`);
check('切換後標題換成該單元', $('.top__title').textContent === btns[btns.length-1].textContent, $('.top__title').textContent);
check('切換後只有被點的那顆是 pressed', btns[btns.length-1].getAttribute('aria-pressed')==='true' && btns[0].getAttribute('aria-pressed')==='false');
check('切換後沒有殘留舊單元的句子列', $$('#script-list .line').length > 0);
check('全程仍然只有 1 個 audio 元素', w.__audioCount === 1, `共 ${w.__audioCount} 個`);
check('音檔是內嵌 data URI', w.__playLog[0]?.startsWith('data:audio/mp4;base64,'), w.__playLog[0]?.slice(0,30));

console.log(`\n${out.filter(Boolean).length} / ${out.length} 通過`);
process.exit(out.every(Boolean)?0:1);
