/* 英文情境對話練習 — 播放器
 *
 * 用法：EnglishDrill.mount(unitData, rootElement, { backHref })
 *   unitData  make_unit.py 產出的單元資料（每句已帶 audio 路徑與 dur 長度）
 *   rootElement  掛載點，內容會被整個換掉
 *   backHref  「所有單元」返回連結；不給就不顯示
 *
 * 之所以做成可掛載，是因為線上版要在同一頁切換單元。本機版與線上版共用這一份實作。
 * 每句音檔長度在建置期就算好存在 line.dur，跟讀留白才能算得準。
 */

(() => {
  'use strict';

  /* ================================================ 播放引擎
   * 同一時間只跑一個序列。每個序列開始時拿一個號碼牌；
   * 號碼牌被換掉（按停、切分頁、切單元）時，序列的每一步都會自己收攤。
   */

  const CANCELLED = Symbol('cancelled');
  const engine = { token: 0, audio: null, waiter: null, paused: false };

  function stopMedia() {
    if (engine.audio) { engine.audio.pause(); engine.audio = null; }
    if (engine.waiter) { engine.waiter.cancel(); engine.waiter = null; }
  }

  function begin() {
    stopMedia();
    engine.paused = false;
    return ++engine.token;
  }

  function stopAll() {
    engine.token++;
    stopMedia();
    engine.paused = false;
  }

  function check(token) {
    if (token !== engine.token) throw CANCELLED;
  }

  /* 全程共用同一個 audio 元素，只換 src。
   * 這是為了 iOS：Safari 只讓「使用者手勢解鎖過的那個」audio 元素繼續播，
   * 每句都 new Audio() 的話，手機上第一句之後會整段安靜。 */
  let sharedAudio = null;

  function getAudio() {
    if (!sharedAudio) {
      sharedAudio = new Audio();
      sharedAudio.preload = 'auto';
      sharedAudio.preservesPitch = true;
      sharedAudio.mozPreservesPitch = true;
      sharedAudio.webkitPreservesPitch = true;
    }
    return sharedAudio;
  }

  function playAudio(src, rate, token) {
    return new Promise((resolve, reject) => {
      const audio = getAudio();

      const cleanup = () => {
        audio.removeEventListener('ended', onEnded);
        audio.removeEventListener('error', onError);
      };
      function onEnded() {
        cleanup();
        if (engine.audio === audio) engine.audio = null;
        if (token !== engine.token) reject(CANCELLED); else resolve();
      }
      function onError() {
        cleanup();
        if (engine.audio === audio) engine.audio = null;
        reject(new Error('讀不到音檔：' + String(src).slice(0, 60)));
      }

      audio.addEventListener('ended', onEnded);
      audio.addEventListener('error', onError);

      audio.pause();
      audio.src = src;
      audio.currentTime = 0;
      audio.playbackRate = rate;
      engine.audio = audio;

      audio.play().then(
        // 換 src 時瀏覽器會把 playbackRate 打回 1，開播後要再設一次
        () => { audio.playbackRate = rate; },
        (err) => {
          cleanup();
          if (token !== engine.token) reject(CANCELLED); else reject(err);
        },
      );
    });
  }

  /** 可暫停、可取消的等待。onProgress 收到 0→1。 */
  function wait(ms, onProgress) {
    return new Promise((resolve, reject) => {
      let elapsed = 0;
      let last = performance.now();
      let frame = 0;
      let dead = false;

      const waiter = {
        cancel() { dead = true; cancelAnimationFrame(frame); reject(CANCELLED); },
      };
      engine.waiter = waiter;

      function step(now) {
        if (dead) return;
        const delta = now - last;
        last = now;
        if (!engine.paused) elapsed += delta;
        if (onProgress) onProgress(Math.min(1, elapsed / ms));
        if (elapsed >= ms) {
          if (engine.waiter === waiter) engine.waiter = null;
          resolve();
          return;
        }
        frame = requestAnimationFrame(step);
      }
      frame = requestAnimationFrame(step);
    });
  }

  function setPaused(paused) {
    engine.paused = paused;
    if (engine.audio) {
      if (paused) engine.audio.pause();
      else engine.audio.play().catch(() => {});
    }
  }

  function run(fn, onDone) {
    const token = begin();
    (async () => {
      try {
        await fn(token);
      } catch (err) {
        if (err === CANCELLED) return;
        console.error(err);
        if (onDone) onDone(err);
        return;
      }
      if (onDone) onDone(null);
    })();
  }

  const isRunning = () => Boolean(engine.audio || engine.waiter);
  const setBar = (el, ratio) => { el.style.width = (Math.max(0, Math.min(1, ratio)) * 100) + '%'; };

  /* ================================================ 頁面骨架 */

  const SKELETON = `
  <header class="top">
    <a class="top__back" hidden>← 所有單元</a>
    <h1 class="top__title"></h1>
    <p class="top__en"></p>
    <div class="meta">
      <span class="pill top__level"></span>
      <span class="top__lines"></span>
      <span class="top__dur"></span>
    </div>
  </header>

  <div class="tabs" role="tablist">
    <button class="tab" role="tab" data-panel="blind"><b>1</b> 盲聽</button>
    <button class="tab" role="tab" data-panel="script"><b>2</b> 逐句對照</button>
    <button class="tab" role="tab" data-panel="vocab"><b>3</b> 單字卡</button>
    <button class="tab" role="tab" data-panel="shadow"><b>4</b> 跟讀</button>
    <button class="tab" role="tab" data-panel="roleplay"><b>5</b> 角色扮演</button>
  </div>

  <section class="panel" id="panel-blind" role="tabpanel">
    <p class="panel__intro">先不要看字。整段聽一次，抓得到他們在處理什麼事就夠了。聽不懂很正常，再聽一次。</p>
    <button class="btn btn--big" id="blind-play">▶ 播放整段對話</button>
    <div class="bar"><div class="bar__fill" id="blind-bar"></div></div>
    <p class="status" id="blind-status"></p>
    <p class="blind__hint">聽出來他們在做什麼了嗎？</p>
    <div class="center"><button class="btn" id="blind-reveal">看情境說明</button></div>
    <div class="scene-box" id="blind-scene" hidden></div>
  </section>

  <section class="panel" id="panel-script" role="tabpanel">
    <p class="panel__intro">中譯預設收起來——先靠耳朵撐一下，真的卡住再打開。</p>
    <div class="controls">
      <button class="btn" id="script-zh">顯示中譯</button>
      <span class="controls__label">重複次數</span>
      <button class="btn" data-repeat="2">×2</button>
      <button class="btn" data-repeat="3">×3</button>
    </div>
    <div class="card" id="script-list"></div>
  </section>

  <section class="panel" id="panel-vocab" role="tabpanel">
    <p class="panel__intro">每個字先聽三遍再跟著唸。例句是這個字真正會出現的樣子，一起記。</p>
    <div class="controls">
      <button class="btn" id="vocab-all">▶ 全部依序唸一遍</button>
      <button class="btn" id="vocab-stop">■ 停</button>
    </div>
    <div class="words" id="vocab-list"></div>
  </section>

  <section class="panel" id="panel-shadow" role="tabpanel">
    <p class="panel__intro">播一句 → 留白等你唸 → 下一句。跟著語調走，不要只唸對單字。</p>
    <div class="controls">
      <span class="controls__label">速度</span>
      <button class="btn is-on" id="shadow-normal">原速</button>
      <button class="btn" id="shadow-slow">🐢 0.75x</button>
      <span class="controls__label">每句</span>
      <button class="btn is-on" data-shadow-repeat="1">聽 1 次</button>
      <button class="btn" data-shadow-repeat="2">聽 2 次</button>
    </div>
    <div class="card">
      <div class="stage" id="shadow-stage"><p class="stage__idle">按下方按鈕開始</p></div>
      <div class="bar"><div class="bar__fill bar__fill--you" id="shadow-bar"></div></div>
    </div>
    <button class="btn btn--big" id="shadow-toggle">▶ 開始跟讀</button>
    <p class="hint">空白鍵可以暫停／繼續</p>
  </section>

  <section class="panel" id="panel-roleplay" role="tabpanel">
    <p class="panel__intro">選一個角色。輪到你時只會出現中文提示與留白，你要自己講出來。</p>
    <div class="controls">
      <span class="controls__label">我要演</span>
      <button class="btn" data-role="A" id="rp-role-a"></button>
      <button class="btn" data-role="B" id="rp-role-b"></button>
    </div>
    <div class="card">
      <div class="stage" id="rp-stage"><p class="stage__idle">選好角色後按下方按鈕開始</p></div>
      <div class="bar"><div class="bar__fill bar__fill--you" id="rp-bar"></div></div>
    </div>
    <button class="btn btn--big" id="rp-toggle">▶ 開始對戲</button>
    <p class="hint">空白鍵可以暫停／繼續</p>
  </section>

  <section class="tips" id="tips" hidden>
    <h2>這個單元要注意的地方</h2>
    <ul id="tips-list"></ul>
  </section>`;

  /* ================================================ 掛載 */

  let ctx = null;   // 目前掛載的單元，給全域快捷鍵用

  function mount(unit, root, opts = {}) {
    stopAll();
    root.innerHTML = SKELETON;

    const LINES = unit.lines;
    const VOCAB = unit.vocab;
    const ROLES = unit.roles;
    const STORE_KEY = 'drill:' + unit.slug + ':tab';

    const $ = (sel) => root.querySelector(sel);
    const $$ = (sel) => Array.from(root.querySelectorAll(sel));

    /* ---------- 頁首 ---------- */

    if (opts.backHref) {
      const back = $('.top__back');
      back.href = opts.backHref;
      back.hidden = false;
    }
    $('.top__title').textContent = unit.title;
    $('.top__en').textContent = unit.title_en || '';
    $('.top__level').textContent = unit.level;
    $('.top__lines').textContent = LINES.length + ' 句對話';
    $('.top__dur').textContent = '約 ' + Math.round(unit.total_dur) + ' 秒';

    /* ---------- 分頁 ---------- */

    const tabs = $$('.tab');
    const panels = {};
    tabs.forEach((tab) => { panels[tab.dataset.panel] = $('#panel-' + tab.dataset.panel); });

    function showTab(name) {
      stopAll();
      resetAllPanels();
      tabs.forEach((tab) => {
        const on = tab.dataset.panel === name;
        tab.setAttribute('aria-selected', on ? 'true' : 'false');
        panels[tab.dataset.panel].classList.toggle('is-active', on);
      });
      try { localStorage.setItem(STORE_KEY, name); } catch (e) { /* 無痕模式，不記就算了 */ }
    }

    tabs.forEach((tab) => tab.addEventListener('click', () => showTab(tab.dataset.panel)));

    function currentTab() {
      const tab = tabs.find((t) => t.getAttribute('aria-selected') === 'true');
      return tab ? tab.dataset.panel : null;
    }

    /* ---------- 1 盲聽 ---------- */

    const blindPlay = $('#blind-play');
    const blindBar = $('#blind-bar');
    const blindStatus = $('#blind-status');

    $('#blind-scene').textContent = unit.scene;
    $('#blind-reveal').addEventListener('click', () => {
      const box = $('#blind-scene');
      box.hidden = !box.hidden;
      $('#blind-reveal').textContent = box.hidden ? '看情境說明' : '收起情境說明';
    });

    function resetBlind() {
      blindPlay.textContent = '▶ 播放整段對話';
      blindPlay.classList.remove('is-on');
      setBar(blindBar, 0);
      blindStatus.textContent = '';
    }

    blindPlay.addEventListener('click', () => {
      if (isRunning()) { stopAll(); resetBlind(); return; }
      blindPlay.textContent = '■ 停止';
      blindPlay.classList.add('is-on');

      run(async (token) => {
        for (let i = 0; i < LINES.length; i++) {
          check(token);
          blindStatus.textContent = `第 ${i + 1} / ${LINES.length} 句`;
          setBar(blindBar, i / LINES.length);
          await playAudio(LINES[i].audio, 1, token);
          check(token);
          if (i < LINES.length - 1) await wait(400);
        }
        setBar(blindBar, 1);
      }, (err) => {
        blindPlay.textContent = '▶ 再聽一次';
        blindPlay.classList.remove('is-on');
        blindStatus.textContent = err ? err.message : '播完了。聽得出重點了嗎？';
      });
    });

    /* ---------- 2 逐句對照 ---------- */

    const scriptList = $('#script-list');
    let showZh = false;
    let repeatCount = 1;

    LINES.forEach((line) => {
      const row = document.createElement('div');
      row.className = 'line';
      row.innerHTML = `
        <div class="line__role line__role--${line.role}"></div>
        <div>
          <div class="line__en"></div>
          <div class="line__zh" hidden></div>
          <div class="line__tools">
            <button class="btn btn--play" data-rate="1" title="原速播放">▶</button>
            <button class="btn btn--play" data-rate="0.75" title="慢速播放">🐢</button>
          </div>
        </div>`;
      row.querySelector('.line__role').textContent = ROLES[line.role].name;
      row.querySelector('.line__en').textContent = line.en;
      row.querySelector('.line__zh').textContent = line.zh;

      Array.from(row.querySelectorAll('.btn--play')).forEach((btn) => {
        btn.addEventListener('click', () => {
          $$('.line').forEach((el) => el.classList.remove('is-current'));
          row.classList.add('is-current');
          const rate = parseFloat(btn.dataset.rate);
          run(async (token) => {
            for (let r = 0; r < repeatCount; r++) {
              check(token);
              await playAudio(line.audio, rate, token);
              check(token);
              if (r < repeatCount - 1) await wait(500);
            }
          }, () => row.classList.remove('is-current'));
        });
      });

      scriptList.appendChild(row);
    });

    $('#script-zh').addEventListener('click', () => {
      showZh = !showZh;
      $('#script-zh').textContent = showZh ? '隱藏中譯' : '顯示中譯';
      $('#script-zh').classList.toggle('is-on', showZh);
      $$('.line__zh').forEach((el) => { el.hidden = !showZh; });
    });

    $$('[data-repeat]').forEach((btn) => {
      btn.addEventListener('click', () => {
        const value = parseInt(btn.dataset.repeat, 10);
        const turningOff = repeatCount === value;
        repeatCount = turningOff ? 1 : value;
        $$('[data-repeat]').forEach((other) => {
          other.classList.toggle('is-on', !turningOff && other === btn);
        });
      });
    });

    const resetScript = () => $$('.line').forEach((el) => el.classList.remove('is-current'));

    /* ---------- 3 單字卡 ---------- */

    const vocabList = $('#vocab-list');

    VOCAB.forEach((word) => {
      const card = document.createElement('div');
      card.className = 'card word';
      card.innerHTML = `
        <div class="word__head">
          <button class="btn btn--play">▶</button>
          <span class="word__term"></span>
          <span class="word__pos"></span>
          <span class="word__zh"></span>
        </div>`;
      card.querySelector('.word__term').textContent = word.term;
      card.querySelector('.word__pos').textContent = word.pos || '';
      card.querySelector('.word__zh').textContent = word.zh;
      card.querySelector('.btn--play').addEventListener('click', () => {
        run((token) => playAudio(word.audio, 1, token));
      });

      if (word.example_en) {
        const ex = document.createElement('div');
        ex.className = 'word__ex';
        ex.innerHTML = `
          <button class="btn btn--play">▶</button>
          <div>
            <div class="word__ex-text"></div>
            <div class="word__ex-zh"></div>
          </div>`;
        ex.querySelector('.word__ex-text').textContent = word.example_en;
        ex.querySelector('.word__ex-zh').textContent = word.example_zh || '';
        ex.querySelector('.btn--play').addEventListener('click', () => {
          run((token) => playAudio(word.example_audio, 1, token));
        });
        card.appendChild(ex);
      }

      vocabList.appendChild(card);
    });

    $('#vocab-all').addEventListener('click', () => {
      run(async (token) => {
        for (const word of VOCAB) {
          check(token);
          await playAudio(word.audio, 1, token);
          check(token);
          await wait(350);
          if (word.example_audio) {
            check(token);
            await playAudio(word.example_audio, 1, token);
            check(token);
          }
          await wait(650);
        }
      });
    });

    $('#vocab-stop').addEventListener('click', stopAll);

    /* ---------- 畫面中央的提示 ---------- */

    function stageView(stage, { role, en, zh, cue }) {
      stage.innerHTML = '';
      const add = (cls, text) => {
        const el = document.createElement('div');
        el.className = cls;
        el.textContent = text;
        stage.appendChild(el);
      };
      if (role) add('stage__role line__role--' + role.key, role.label);
      if (en) add('stage__en', en);
      if (zh) add('stage__zh', zh);
      if (cue) add('stage__cue', cue);
    }

    function stageIdle(stage, text) {
      stage.innerHTML = '';
      const el = document.createElement('p');
      el.className = 'stage__idle';
      el.textContent = text;
      stage.appendChild(el);
    }

    const roleTag = (key) => ({ key, label: ROLES[key].name + '（' + ROLES[key].zh + '）' });

    /* ---------- 4 跟讀 ---------- */

    const shadowStage = $('#shadow-stage');
    const shadowBar = $('#shadow-bar');
    const shadowToggle = $('#shadow-toggle');
    let shadowRate = 1;
    let shadowRepeat = 1;

    $('#shadow-normal').addEventListener('click', () => {
      shadowRate = 1;
      $('#shadow-normal').classList.add('is-on');
      $('#shadow-slow').classList.remove('is-on');
    });
    $('#shadow-slow').addEventListener('click', () => {
      shadowRate = 0.75;
      $('#shadow-slow').classList.add('is-on');
      $('#shadow-normal').classList.remove('is-on');
    });
    $$('[data-shadow-repeat]').forEach((btn) => {
      btn.addEventListener('click', () => {
        shadowRepeat = parseInt(btn.dataset.shadowRepeat, 10);
        $$('[data-shadow-repeat]').forEach((o) => o.classList.toggle('is-on', o === btn));
      });
    });

    function resetShadow() {
      shadowToggle.textContent = '▶ 開始跟讀';
      shadowToggle.classList.remove('is-on');
      setBar(shadowBar, 0);
      stageIdle(shadowStage, '按下方按鈕開始');
    }

    shadowToggle.addEventListener('click', () => {
      if (isRunning()) { stopAll(); resetShadow(); return; }
      shadowToggle.textContent = '■ 停止';
      shadowToggle.classList.add('is-on');

      run(async (token) => {
        for (const line of LINES) {
          check(token);
          stageView(shadowStage, { role: roleTag(line.role), en: line.en, zh: line.zh, cue: '仔細聽' });
          setBar(shadowBar, 0);

          for (let r = 0; r < shadowRepeat; r++) {
            check(token);
            await playAudio(line.audio, shadowRate, token);
            check(token);
            await wait(250);
          }

          check(token);
          stageView(shadowStage, { role: roleTag(line.role), en: line.en, zh: line.zh, cue: '↑ 換你唸' });
          await wait((line.dur / shadowRate) * 1300, (p) => setBar(shadowBar, p));
        }
      }, (err) => {
        setBar(shadowBar, 0);
        shadowToggle.textContent = '▶ 再跑一次';
        shadowToggle.classList.remove('is-on');
        stageIdle(shadowStage, err ? err.message : '整段跟完了。換個速度再跑一次？');
      });
    });

    /* ---------- 5 角色扮演 ---------- */

    const rpStage = $('#rp-stage');
    const rpBar = $('#rp-bar');
    const rpToggle = $('#rp-toggle');
    let myRole = 'B';

    ['A', 'B'].forEach((key) => {
      const btn = $('#rp-role-' + key.toLowerCase());
      btn.textContent = ROLES[key].name + '（' + ROLES[key].zh + '）';
      btn.addEventListener('click', () => {
        myRole = key;
        stopAll();
        resetRoleplay();
        $$('[data-role]').forEach((o) => o.classList.toggle('is-on', o.dataset.role === key));
      });
    });
    $('#rp-role-b').classList.add('is-on');

    function resetRoleplay() {
      rpToggle.textContent = '▶ 開始對戲';
      rpToggle.classList.remove('is-on');
      setBar(rpBar, 0);
      stageIdle(rpStage, '選好角色後按下方按鈕開始');
    }

    rpToggle.addEventListener('click', () => {
      if (isRunning()) { stopAll(); resetRoleplay(); return; }
      rpToggle.textContent = '■ 停止';
      rpToggle.classList.add('is-on');

      run(async (token) => {
        for (const line of LINES) {
          check(token);
          if (line.role === myRole) {
            // 輪到你：只給中文提示與留白，講完再對答案
            stageView(rpStage, { role: roleTag(line.role), zh: line.zh, cue: '換你講 —— 用英文' });
            await wait(line.dur * 1400, (p) => setBar(rpBar, p));
            check(token);
            stageView(rpStage, { role: roleTag(line.role), en: line.en, zh: line.zh, cue: '↑ 你剛剛講的一樣嗎？' });
            await wait(1600);
          } else {
            stageView(rpStage, { role: roleTag(line.role), en: line.en, zh: line.zh });
            setBar(rpBar, 0);
            await playAudio(line.audio, 1, token);
            check(token);
            await wait(300);
          }
        }
      }, (err) => {
        setBar(rpBar, 0);
        rpToggle.textContent = '▶ 再演一次';
        rpToggle.classList.remove('is-on');
        stageIdle(rpStage, err ? err.message : '整場演完了。換另一個角色試試？');
      });
    });

    /* ---------- 提醒 ---------- */

    if (unit.tips && unit.tips.length) {
      $('#tips').hidden = false;
      const list = $('#tips-list');
      unit.tips.forEach((tip) => {
        const li = document.createElement('li');
        li.textContent = tip;
        list.appendChild(li);
      });
    }

    /* ---------- 收尾 ---------- */

    function resetAllPanels() {
      resetBlind();
      resetScript();
      resetShadow();
      resetRoleplay();
    }

    ctx = { currentTab };

    let saved = null;
    try { saved = localStorage.getItem(STORE_KEY); } catch (e) { /* 忽略 */ }
    showTab(panels[saved] ? saved : 'blind');
  }

  // 全域快捷鍵只掛一次，避免每次 mount 都多疊一層
  document.addEventListener('keydown', (event) => {
    if (event.code !== 'Space' || !ctx) return;
    const tab = ctx.currentTab();
    if (tab !== 'shadow' && tab !== 'roleplay') return;
    if (!isRunning()) return;
    event.preventDefault();
    setPaused(!engine.paused);
  });

  window.EnglishDrill = { mount, stopAll };
})();
