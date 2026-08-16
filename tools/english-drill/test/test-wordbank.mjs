import fs from 'node:fs';
import { createRequire } from 'node:module';

// jsdom 刻意不裝進專案資料夾（會讓 Google Drive 同步幾萬個小檔）。
// 裝在任何暫存目錄，再用 JSDOM_HOME 指過去即可。
const require = createRequire(
  process.env.JSDOM_HOME ? process.env.JSDOM_HOME.replace(/\/?$/, '/') : import.meta.url,
);
const { JSDOM } = require('jsdom');

const html = fs.readFileSync('/Users/shun/Library/CloudStorage/GoogleDrive-shunshun70218@gmail.com/我的雲端硬碟/cloudai data/英文學習/build/wordbank.html', 'utf8');
const errors = [];
const dom = new JSDOM(html, { url:'http://localhost/', runScripts:'dangerously', beforeParse(win){
  win.__audioCount = 0; win.__playLog = [];
  win.Audio = class { constructor(){ win.__audioCount++; this.src=''; this.currentTime=0; }
    pause(){} play(){ win.__playLog.push(this.src.slice(0,30)); return Promise.resolve(); } };
  win.addEventListener('error', e => errors.push(String(e.error||e.message)));
}});
const w = dom.window, $ = s => w.document.querySelector(s), $$ = s => [...w.document.querySelectorAll(s)];
const click = el => el.dispatchEvent(new w.MouseEvent('click',{bubbles:true}));
const out=[]; const check=(n,ok,d='')=>{out.push(ok);console.log(`${ok?'✅':'❌'} ${n}${d?' — '+d:''}`)};

const DATA = JSON.parse($('#bank-data').textContent)[0];
const allWords = DATA.themes.flatMap(t=>t.words);

check('載入沒有丟錯', errors.length===0, errors.join('; '));
check('標題正確', w.document.title==='多益單字卡', w.document.title);
check(`主題按鈕 = 全部 + ${DATA.themes.length} 主題`, $$('.switcher__btn').length===DATA.themes.length+1, $$('.switcher__btn').map(b=>b.textContent).join('/'));
check(`共 ${allWords.length} 個單字`, allWords.length >= 96, String(allWords.length));
check('每個字都有音節與發音', allWords.every(x=>x.syllables?.length && x.audio?.startsWith('data:audio/mp4')));
check('每個字都有 IPA', allWords.every(x=>x.ipa), `缺 ${allWords.filter(x=>!x.ipa).map(x=>x.term).join(',')}`);

// confidential 這個字的音節與重音要正確
const conf = allWords.find(x=>x.term==='confidential');
check('confidential 切成 4 音節', conf.syllables.join('·')==='con·fi·den·tial', conf.syllables.join('·'));
check('confidential 重音在第 3 節 (den)', conf.stress===2 && conf.syllables[2]==='den', `stress=${conf.stress}`);
check('confidential 音標含輕音 schwa', conf.ipa.includes('ə'), conf.ipa);

// 字卡：翻卡
const card = $('.fc__card');
check('字卡預設不顯示答案', $('.fc__back').hidden === true);
{
  const withStress = allWords.filter(x=>x.stress!==null).length;
  check('九成以上的字標得出重音節', withStress/allWords.length >= 0.9,
    `${withStress}/${allWords.length} = ${Math.round(100*withStress/allWords.length)}%`);
  const term = $('.fc__card .term').textContent;
  const shown = allWords.find(x => x.term === term);
  check('正面顯示完整單字，沒有被切開', !!shown && !term.includes('·'), term);
  check('正面看不到音節拆解與音標', $('.fc__back').hidden === true && $('.fc__card .syls') !== null);
}
click(card);
check('點卡片後顯示答案', $('.fc__back').hidden === false);
{
  const term = $('.fc__card .term').textContent;
  const shown = allWords.find(x => x.term === term);
  const syls = $('.fc__back .syls');
  check('答案區才出現音節拆解', !!syls && syls.textContent.replace(/·/g,'') === shown.syllables.join(''),
    `${term} → ${syls?.textContent}`);
  check('音節拆解的重音標示與資料一致',
    ($$('.fc__back .syl--stress').length===1) === (shown.stress!==null),
    `stress=${shown.stress}`);
}
check('翻面後出現三段熟練度按鈕', $$('.lv').length===3 && !$('.fc__levels').hidden, $$('.lv').map(b=>b.firstChild.textContent).join('/'));

// 標記熟練度會換下一張並存檔
const before = $('.fc__card .syls').textContent;
click($('.lv--2'));
const stored = JSON.parse(w.localStorage.getItem('wordbank:levels')||'{}');
check('標記「熟了」有寫進 localStorage', Object.values(stored).includes(2), JSON.stringify(stored));
check('標記後自動換下一張並收起答案', $('.fc__back').hidden===true);
check('換到不同的字', $('.fc__card .syls').textContent !== before, `${before} → ${$('.fc__card .syls').textContent}`);

// 回合制佇列：把 95 個字標成「熟了」，只留 1 個不熟 → 一輪應該只有少數幾張，且必含那個字
{
  const levels = {}; allWords.forEach((x,i)=>{ if(i>0) levels[x.term.toLowerCase()]=2; });
  const dom2 = new JSDOM(html, { url:'http://localhost/', runScripts:'dangerously', beforeParse(win){
    win.Audio = class { constructor(){} pause(){} play(){ return Promise.resolve(); } };
    win.localStorage.setItem('wordbank:levels', JSON.stringify(levels));
  }});
  const w2 = dom2.window;
  const target = allWords[0].term;
  const progress = w2.document.querySelector('.fc__remain').textContent;
  const roundSize = Number(progress.split('/')[1].trim());
  check('一輪只排不熟的字 + 兩成複習', roundSize >= 15 && roundSize <= 25,
    `95 個熟字 + 1 個不熟 → 本輪 ${roundSize} 張（預期 1 + 95*0.2 ≈ 20）`);

  // 走完整輪，確認那個不熟的字一定會出現
  const seen = new Set();
  for (let i=0;i<roundSize;i++){
    const card = w2.document.querySelector('.fc__card');
    if (!card) break;
    seen.add(w2.document.querySelector('.fc__card .syls').textContent.replace(/·/g,''));
    card.dispatchEvent(new w2.MouseEvent('click',{bubbles:true}));
    w2.document.querySelector('.lv--2').dispatchEvent(new w2.MouseEvent('click',{bubbles:true}));
  }
  check('本輪一定考到那個不熟的字', seen.has(target), `本輪出現 ${seen.size} 個不同的字`);
  check('走完一輪會出現「再來一輪」', /再來一輪/.test(w2.document.getElementById('app').textContent));
}

// 標「不會」會在本輪稍後再出現一次
{
  const dom3 = new JSDOM(html, { url:'http://localhost/', runScripts:'dangerously', beforeParse(win){
    win.Audio = class { constructor(){} pause(){} play(){ return Promise.resolve(); } };
  }});
  const w3 = dom3.window;
  const sizeBefore = Number(w3.document.querySelector('.fc__remain').textContent.split('/')[1].trim());
  const word = w3.document.querySelector('.fc__card .syls').textContent.replace(/·/g,'');
  w3.document.querySelector('.fc__card').dispatchEvent(new w3.MouseEvent('click',{bubbles:true}));
  w3.document.querySelector('.lv--0').dispatchEvent(new w3.MouseEvent('click',{bubbles:true}));
  const sizeAfter = Number(w3.document.querySelector('.fc__remain').textContent.split('/')[1].trim());
  check('標「不會」會把該字排回本輪', sizeAfter === sizeBefore + 1, `${sizeBefore} → ${sizeAfter}`);

  let reappeared = false;
  for (let i=0;i<6;i++){
    if (w3.document.querySelector('.fc__card .syls').textContent.replace(/·/g,'') === word) { reappeared = true; break; }
    w3.document.querySelector('.fc__card').dispatchEvent(new w3.MouseEvent('click',{bubbles:true}));
    w3.document.querySelector('.lv--2').dispatchEvent(new w3.MouseEvent('click',{bubbles:true}));
  }
  check('標「不會」的字幾張之後真的再出現', reappeared, `追蹤「${word}」`);
}

// 列表模式
click($$('.mode-btn')[1]);
check(`列表模式列出全部 ${allWords.length} 個字`, $$('.wb-item').length===allWords.length, String($$('.wb-item').length));
check('列表有熟練度圓點', $$('.lvdot').length===allWords.length);
check('列表也是完整單字在上、拆解在下', $$('.wb-item .term').length===allWords.length
  && $$('.wb-item .term').every(e=>!e.textContent.includes('·'))
  && $$('.wb-item__breakdown .syls').length===allWords.length,
  `${$$('.wb-item .term')[0]?.textContent} / ${$$('.wb-item__breakdown')[0]?.textContent.trim()}`);

check('全程只建立 1 個 audio 元素', w.__audioCount<=1, `共 ${w.__audioCount} 個`);

console.log(`\n${out.filter(Boolean).length} / ${out.length} 通過`);
process.exit(out.every(Boolean)?0:1);
