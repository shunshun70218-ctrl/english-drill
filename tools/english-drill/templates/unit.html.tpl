<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{TITLE}}｜英文情境練習</title>
<link rel="stylesheet" href="player.css">
</head>
<body>
<div class="wrap" id="app"></div>

<script id="unit-data" type="application/json">{{UNIT_JSON}}</script>
<script src="player.js"></script>
<script>
  EnglishDrill.mount(
    JSON.parse(document.getElementById('unit-data').textContent),
    document.getElementById('app'),
    { backHref: '../../index.html' }
  );
</script>
</body>
</html>
