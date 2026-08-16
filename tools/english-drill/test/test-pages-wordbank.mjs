import fs from 'node:fs';
import { createRequire } from 'node:module';
const require = createRequire(process.env.JSDOM_HOME ? process.env.JSDOM_HOME.replace(/\/?$/, '/') : import.meta.url);
const { JSDOM } = require('jsdom');

const BASE = '/Users/shun/Library/CloudStorage/GoogleDrive-shunshun70218@gmail.com/我的雲端硬碟/cloudai data/英文學習/docs';
const html = fs.readFileSync(`${BASE}/wordbank/index.html`, 'utf8');
const errors = [];
const dom = new JSDOM(html, { url:'http://localhost/', runScripts:'dangerously', beforeParse(w){
  w.__audioCount = 0; w.__playLog = [];
  w.Audio = class { constructor(){ w.__audioCount++; this.src=''; this.currentTime=0; } pause(){} play(){ w.__playLog.push(this.src); return Promise.resolve(); } };
  w.addEventListener('error', e => errors.push(String(e.error||e.message)));
}});
const w = dom.window, $ = s => w.document.querySelector(s), $$ = s => [...w.document.querySelectorAll(s)];
const click = el => el.dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
const out=[]; const check=(n,ok,d='')=>{out.push(ok);console.log(`${ok?'✅':'❌'} ${n}${d?' — '+d:''}`)};

const BANKS = JSON.parse($('#bank-data').textContent);
check('載入沒有丟錯', errors.length===0, errors.join('; '));
check('有兩個字庫', BANKS.length===2, BANKS.map(b=>`${b.title}(${b.themes.reduce((a,t)=>a+t.words.length,0)}字)`).join(' / '));

const bankBtns = $$('.mode-row')[0].querySelectorAll('.mode-btn');
check('字庫切換列顯示出來', [...bankBtns].length===2 && $$('.mode-row')[0].hidden===false,
  [...bankBtns].map(b=>b.textContent).join(' / '));

const core = BANKS.find(b=>b.themes.length===9), big = BANKS.find(b=>b.themes.length===20);
check('2000 字分成 20 組', !!big && big.themes.length===20, big?.themes.map(t=>t.name).slice(0,3).join(','));
check('每組 100 字', big.themes.every(t=>t.words.length===100));
const all = big.themes.flatMap(t=>t.words);
check('2000 字全部有中譯與音檔', all.every(x=>x.zh && x.audio), `缺: ${all.filter(x=>!x.zh||!x.audio).length}`);
check('2000 字全部有音節與 IPA', all.every(x=>x.syllables?.length && x.ipa), `缺: ${all.filter(x=>!x.ipa).length}`);
check('音檔是相對路徑不是 base64', all[0].audio.startsWith('audio/toeic-2000/'), all[0].audio);
check('2000 字沒有例句音檔（刻意的）', all.every(x=>!x.example_audio));
check('核心 98 字仍保有例句音檔', core.themes.flatMap(t=>t.words).every(x=>x.example_audio));

// 音檔實際存在
const missing = all.filter(x => !fs.existsSync(`${BASE}/wordbank/${x.audio}`));
check('2000 個音檔實際都在磁碟上', missing.length===0, `缺 ${missing.length} 個`);

// 切到 2000 字字庫
const bigBtnIndex = BANKS.indexOf(big);
click(bankBtns[bigBtnIndex]);
check('切到 2000 字後出現 21 顆組別按鈕（全部＋20組）', $$('.switcher__btn').length===21, String($$('.switcher__btn').length));
check('切換後 meta 更新成 20 組', $('#bank-meta').textContent.includes('20 組'), $('#bank-meta').textContent);
const shownTerm = $('.fc__card .term')?.textContent;
check('切換後抽到的是 2000 字庫裡的字', all.some(x=>x.term===shownTerm), shownTerm);

// 點某一組
click($$('.switcher__btn')[3]);
const t3 = big.themes[2];
const shown2 = $('.fc__card .term')?.textContent;
check('選第 3 組後只從該組抽字', t3.words.some(x=>x.term===shown2), `第3組: ${shown2}`);

// 切回核心字庫
click(bankBtns[BANKS.indexOf(core)]);
check('切回核心字庫，組別按鈕變 10 顆', $$('.switcher__btn').length===10, String($$('.switcher__btn').length));

check('全程只建立 1 個 audio 元素', w.__audioCount<=1, `共 ${w.__audioCount} 個`);
console.log(`\n${out.filter(Boolean).length} / ${out.length} 通過`);
process.exit(out.every(Boolean)?0:1);
