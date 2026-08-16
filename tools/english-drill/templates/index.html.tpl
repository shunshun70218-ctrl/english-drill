<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>英文情境對話練習</title>
<link rel="stylesheet" href="tools/english-drill/templates/player.css">
</head>
<body>
<div class="wrap">

  <header class="top">
    <h1>英文情境對話練習</h1>
    <p class="top__en">每個單元一段約一分鐘的對話：盲聽 → 逐句對照 → 單字卡 → 跟讀 → 角色扮演</p>
    <div class="meta"><span>共 {{COUNT}} 個單元</span></div>
  </header>

  <div class="units">
{{CARDS}}
  </div>

  <section class="howto">
    <p>要新單元的時候，跟 Claude 說「幫我做一個⟨情境⟩的單元」就好。<br>
    手動重建：<code>python3 tools/english-drill/make_unit.py --all</code></p>
  </section>

</div>
</body>
</html>
