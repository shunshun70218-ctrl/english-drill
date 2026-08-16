/* 多益單字卡
 *
 * 資料由 make_wordbank.py 內嵌（含音節、音標、重音節、發音 data URI）。
 * 熟練度分三段存在 localStorage：0 不會 / 1 有印象 / 2 熟了。
 *
 * 抽卡用「回合制佇列」而不是加權隨機：一輪把所有『不會』與『有印象』的字全排進去，
 * 『熟了』的只隨機抽兩成複習。純加權隨機在字多的時候會被稀釋——95 個熟字各佔一份權重，
 * 就算不熟的字權重是六倍，也只有 6% 機率被抽到，等於沒有優先練到不會的。
 */

(() => {
  'use strict';

  const BANKS = JSON.parse(document.getElementById('bank-data').textContent);
  let BANK = BANKS[0];
  const LEVEL_KEY = 'wordbank:levels';
  const BANK_KEY = 'wordbank:bank';
  const LEVEL_NAMES = ['不會', '有印象', '熟了'];
  const REVIEW_RATIO = 0.2;      // 一輪裡「熟了」的字複習兩成
  const RETRY_GAP = 4;           // 標「不會」的字，本輪隔幾張後再出現一次

  const app = document.getElementById('app');

  /* ---------- 播放（共用同一個 audio 元素，iOS 才不會第一次之後靜音） ---------- */

  let sharedAudio = null;
  function play(src) {
    if (!src) return;
    if (!sharedAudio) {
      sharedAudio = new Audio();
      sharedAudio.preload = 'auto';
    }
    sharedAudio.pause();
    sharedAudio.src = src;
    sharedAudio.currentTime = 0;
    sharedAudio.play().catch(() => {});
  }

  /* ---------- 熟練度 ---------- */

  let levels = {};
  try { levels = JSON.parse(localStorage.getItem(LEVEL_KEY) || '{}'); } catch (e) { levels = {}; }

  const levelOf = (word) => {
    const value = levels[word.term.toLowerCase()];
    return typeof value === 'number' ? value : null;
  };

  function setLevel(word, value) {
    levels[word.term.toLowerCase()] = value;
    try { localStorage.setItem(LEVEL_KEY, JSON.stringify(levels)); } catch (e) { /* 忽略 */ }
  }

  /* ---------- 共用小元件 ---------- */

  const el = (tag, cls, text) => {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text != null) node.textContent = text;
    return node;
  };

  /** 單字本身，原樣不動 */
  function termView(word) {
    return el('div', 'term', word.term);
  }

  /** 音節拆解：con · fi · DEN · tial，重音節上色加粗 */
  function syllableView(word) {
    const box = el('div', 'syls');
    const parts = word.syllables && word.syllables.length ? word.syllables : [word.term];
    parts.forEach((part, i) => {
      if (i > 0) box.appendChild(el('span', 'syl-dot', '·'));
      box.appendChild(el('span', word.stress === i ? 'syl syl--stress' : 'syl', part));
    });
    return box;
  }

  /** 沒給 label 就是 44×44 的方形圖示鈕；給了 label 要用會自動撐寬的樣式，不然文字會爆出框外 */
  function playButton(src, label) {
    const btn = el('button', label ? 'btn btn--audio' : 'btn btn--play');
    btn.type = 'button';
    btn.appendChild(el('span', 'btn__icon', '▶'));
    if (label) btn.appendChild(el('span', null, label));
    btn.addEventListener('click', (event) => { event.stopPropagation(); play(src); });
    return btn;
  }

  /* ---------- 主題選擇 ---------- */

  let THEMES = [];
  let theme = null;
  let mode = 'card';

  const meta = document.getElementById('bank-meta');
  const bankRow = el('div', 'mode-row');
  const switcher = el('div', 'switcher');

  // 字庫切換（只有一個字庫就不顯示）
  const bankButtons = BANKS.map((item) => {
    const btn = el('button', 'mode-btn', item.title);
    btn.type = 'button';
    btn.addEventListener('click', () => selectBank(item));
    bankRow.appendChild(btn);
    return btn;
  });
  bankRow.hidden = BANKS.length < 2;

  function buildThemes() {
    const all = { slug: '__all', name: '全部', words: BANK.themes.flatMap((t) => t.words) };
    THEMES = [all, ...BANK.themes];
    theme = all;

    meta.innerHTML = '';
    meta.append(
      el('span', 'pill', BANK.title_en || 'TOEIC'),
      el('span', null, `${BANK.themes.length} 組`),
      el('span', null, `${all.words.length} 個單字`),
    );

    switcher.innerHTML = '';
    THEMES.forEach((item) => {
      const btn = el('button', 'switcher__btn', item.name);
      btn.type = 'button';
      btn.setAttribute('aria-pressed', item === theme ? 'true' : 'false');
      btn.addEventListener('click', () => {
        theme = item;
        Array.from(switcher.children).forEach((other, i) =>
          other.setAttribute('aria-pressed', THEMES[i] === item ? 'true' : 'false'));
        resetRound();    // 換組就重新排一輪，不然會停在別組的字上
        render();
      });
      switcher.appendChild(btn);
    });
  }

  function selectBank(item) {
    BANK = item;
    bankButtons.forEach((btn, i) => btn.setAttribute('aria-pressed', BANKS[i] === item ? 'true' : 'false'));
    try { localStorage.setItem(BANK_KEY, item.title); } catch (e) { /* 忽略 */ }
    buildThemes();
    resetRound();
    render();
  }

  const modeRow = el('div', 'mode-row');
  const modeButtons = [['card', '字卡'], ['list', '列表']].map(([key, label]) => {
    const btn = el('button', 'mode-btn', label);
    btn.type = 'button';
    btn.setAttribute('aria-pressed', key === mode ? 'true' : 'false');
    btn.addEventListener('click', () => {
      mode = key;
      modeButtons.forEach((other) => other.setAttribute('aria-pressed', other === btn ? 'true' : 'false'));
      render();
    });
    modeRow.appendChild(btn);
    return btn;
  });

  const view = el('div');
  app.append(bankRow, switcher, modeRow, view);

  /* ---------- 字卡 ---------- */

  let current = null;
  let flipped = false;
  let queue = [];
  let roundSize = 0;

  function shuffle(list) {
    const out = list.slice();
    for (let i = out.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [out[i], out[j]] = [out[j], out[i]];
    }
    return out;
  }

  /** 一輪＝全部不熟的字 + 兩成已熟的字複習。 */
  function buildQueue(words) {
    const weak = words.filter((w) => (levelOf(w) ?? 0) === 0);
    const shaky = words.filter((w) => levelOf(w) === 1);
    const known = words.filter((w) => levelOf(w) === 2);
    const review = shuffle(known).slice(0, Math.round(known.length * REVIEW_RATIO));
    const round = shuffle([...weak, ...shaky, ...review]);
    return round.length ? round : shuffle(words);
  }

  function startRound() {
    queue = buildQueue(theme.words);
    roundSize = queue.length;
    current = queue.shift() || null;
    flipped = false;
  }

  function resetRound() {
    queue = [];
    roundSize = 0;
    current = null;
    flipped = false;
  }

  /** 標「不會」→ 本輪隔幾張後再考一次 */
  function requeue(word) {
    queue.splice(Math.min(RETRY_GAP, queue.length), 0, word);
    roundSize += 1;
  }

  function advance() {
    current = queue.shift() || null;
    flipped = false;
  }

  function renderCard() {
    const words = theme.words;
    view.innerHTML = '';
    if (!words.length) {
      view.appendChild(el('p', 'fc__done', '這個主題還沒有單字。'));
      return;
    }

    if (!current && queue.length === 0 && roundSize === 0) startRound();

    // 這一輪跑完了
    if (!current) {
      const done = el('div', 'fc');
      const stats = el('div', 'fc__stats');
      [0, 1, 2].forEach((lv) => {
        const count = words.filter((w) => levelOf(w) === lv).length;
        stats.appendChild(el('span', `fc__chip fc__chip--${lv}`, `${LEVEL_NAMES[lv]} ${count}`));
      });
      done.appendChild(stats);

      const box = el('div', 'card');
      const message = el('p', 'fc__done');
      const weak = words.filter((w) => (levelOf(w) ?? 0) === 0).length;
      message.textContent = weak
        ? `這輪練完了，還有 ${weak} 個字標著「不會」。再來一輪？`
        : '這輪練完了，沒有標著「不會」的字了 👏';
      box.appendChild(message);
      done.appendChild(box);

      const again = el('button', 'btn btn--big', '▶ 再來一輪');
      again.type = 'button';
      again.addEventListener('click', () => { startRound(); renderCard(); });
      done.appendChild(again);

      view.appendChild(done);
      return;
    }

    const wrap = el('div', 'fc');

    // 熟練度統計 + 本輪進度
    const stats = el('div', 'fc__stats');
    [0, 1, 2].forEach((lv) => {
      const count = words.filter((w) => levelOf(w) === lv).length;
      stats.appendChild(el('span', `fc__chip fc__chip--${lv}`, `${LEVEL_NAMES[lv]} ${count}`));
    });
    stats.appendChild(el('span', 'fc__remain', `本輪 ${roundSize - queue.length} / ${roundSize}`));
    wrap.appendChild(stats);

    // 卡片：正面只放原本的單字，音節拆解跟音標留到翻面才出現
    const card = el('div', 'card fc__card');
    card.appendChild(termView(current));
    card.appendChild(playButton(current.audio, '聽發音'));

    const back = el('div', 'fc__back');
    back.hidden = !flipped;
    back.appendChild(syllableView(current));
    if (current.ipa) back.appendChild(el('div', 'fc__ipa ipa', `/${current.ipa}/`));
    const zhRow = el('div');
    zhRow.appendChild(el('span', 'fc__zh', current.zh));
    if (current.pos) zhRow.appendChild(el('span', 'fc__pos', current.pos));
    back.appendChild(zhRow);

    if (current.example_en) {
      const ex = el('div', 'fc__ex');
      if (current.example_audio) ex.appendChild(playButton(current.example_audio));
      const body = el('div');
      body.appendChild(el('div', 'fc__ex-en', current.example_en));
      if (current.example_zh) body.appendChild(el('div', 'fc__ex-zh', current.example_zh));
      ex.appendChild(body);
      back.appendChild(ex);
    }
    card.appendChild(back);

    const tap = el('p', 'fc__tap', flipped ? '選一個熟練度，會自動換下一張' : '點卡片看答案');
    card.appendChild(tap);
    card.addEventListener('click', () => { if (!flipped) { flipped = true; renderCard(); } });
    wrap.appendChild(card);

    // 熟練度按鈕
    const levelRow = el('div', 'fc__levels');
    levelRow.hidden = !flipped;
    [0, 1, 2].forEach((lv) => {
      const btn = el('button', `lv lv--${lv}`);
      btn.type = 'button';
      btn.appendChild(document.createTextNode(LEVEL_NAMES[lv]));
      btn.appendChild(el('small', null, ['常常出現', '偶爾出現', '很少出現'][lv]));
      btn.addEventListener('click', () => {
        setLevel(current, lv);
        if (lv === 0) requeue(current);
        advance();
        renderCard();
      });
      levelRow.appendChild(btn);
    });
    wrap.appendChild(levelRow);

    view.appendChild(wrap);
  }

  /* ---------- 列表 ---------- */

  function renderList() {
    view.innerHTML = '';
    const list = el('div', 'wb-list');

    theme.words.forEach((word) => {
      const item = el('div', 'card wb-item');
      const lv = levelOf(word);
      item.appendChild(el('div', `lvdot lvdot--${lv === null ? 'none' : lv}`));
      item.appendChild(playButton(word.audio));

      const body = el('div', 'wb-item__body');
      body.appendChild(termView(word));
      const breakdown = el('div', 'wb-item__breakdown');
      breakdown.appendChild(syllableView(word));
      if (word.ipa) breakdown.appendChild(el('span', 'ipa', `/${word.ipa}/`));
      body.appendChild(breakdown);

      const zhRow = el('div', 'wb-item__zh');
      zhRow.appendChild(document.createTextNode(word.zh));
      if (word.pos) zhRow.appendChild(el('span', 'wb-item__pos', word.pos));
      body.appendChild(zhRow);

      if (word.example_en) {
        const ex = el('div', 'wb-item__ex');
        if (word.example_audio) ex.appendChild(playButton(word.example_audio));
        const exBody = el('div');
        exBody.appendChild(el('div', 'fc__ex-en', word.example_en));
        if (word.example_zh) exBody.appendChild(el('div', 'fc__ex-zh', word.example_zh));
        ex.appendChild(exBody);
        body.appendChild(ex);
      }

      item.appendChild(body);
      list.appendChild(item);
    });

    view.appendChild(list);
  }

  function render() {
    if (mode === 'card') renderCard();
    else renderList();
  }

  /* ---------- 鍵盤（桌機用） ---------- */

  document.addEventListener('keydown', (event) => {
    if (mode !== 'card' || !current) return;
    if (event.code === 'Space') {
      event.preventDefault();
      if (!flipped) { flipped = true; renderCard(); }
      else play(current.audio);
      return;
    }
    if (flipped && ['Digit1', 'Digit2', 'Digit3'].includes(event.code)) {
      event.preventDefault();
      const lv = Number(event.code.slice(-1)) - 1;
      setLevel(current, lv);
      if (lv === 0) requeue(current);
      advance();
      renderCard();
    }
  });

  // 記住上次選的字庫
  let startBank = BANKS[0];
  try {
    const saved = localStorage.getItem(BANK_KEY);
    const found = BANKS.find((b) => b.title === saved);
    if (found) startBank = found;
  } catch (e) { /* 忽略 */ }
  selectBank(startBank);
})();
