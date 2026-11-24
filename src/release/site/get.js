// P1820: get.html?map=<name>&get=map|zones (dl.js does the saving).
(function () {
  'use strict';
  var D = window.wosDownload;
  var p = new URLSearchParams(location.search);
  var map = p.get('map') || '', want = p.get('get');
  var acts = document.getElementById('gacts'), status = document.getElementById('gstatus');
  if (!D.NAME.test(map)) {
    status.textContent = 'No map named. Open a map on the leaderboard and press Download there.';
    return;
  }
  document.title = 'Download ' + map + ' · World of Surf';
  document.getElementById('gname').textContent = map;
  document.getElementById('gback').href = 'board/#m=' + encodeURIComponent(map) + '&t=0&l=0&s=clean';
  var shot = document.getElementById('gshot'), probe = new Image();
  probe.onload = function () { shot.src = probe.src; shot.hidden = false; };
  probe.src = 'board/shot/' + encodeURIComponent(map);

  var bsp = D.button('map', map, 'Download map', 'pill');
  var zones = D.button('zones', map, 'Download zones', 'pill pill-quiet');
  acts.appendChild(bsp);
  acts.appendChild(zones);
  D.exists('map', map).then(function (n) {
    if (n === false) {
      bsp.disabled = true;
      bsp.textContent = 'Not on the servers';
      status.textContent = map + ' is not installed on the World of Surf servers, so there is nothing to download.';
    } else if (typeof n === 'number' && !status.textContent) {
      status.textContent = D.fileName('map', map) + ' is ' + D.mb(n) + '.';
    }
  });
  D.exists('zones', map).then(function (ok) {
    if (ok === false) {
      zones.disabled = true;
      zones.textContent = 'No zones yet';
      zones.title = 'Nobody has published zones for ' + map + ' yet';
    }
  });
  if (want === 'map') { bsp.click(); }
  else if (want === 'zones') { zones.click(); }
})();
