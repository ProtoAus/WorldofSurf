// Map and zone downloads under their own names (Lex, 25 Nov 2026). play.proto.bar answers both with a 302 into
// R2, whose objects are named by their hash (and a .json would open as a page), so the bytes are fetched and saved
// here. Both hops send Access-Control-Allow-Origin: *. Pages under a connect-src 'self' CSP (the board) link to
// get.html instead of loading this.
(function () {
  'use strict';
  var HOST = 'https://play.proto.bar';
  var NAME = /^[A-Za-z0-9_-]{1,64}$/;          // surfd/maps.nginx's map and zone routes
  var made = {};                              // kind:map -> its button, so a redrawn list keeps its state

  function url(kind, map) {
    return kind === 'zones' ? HOST + '/ftesurf/maps/zones/local/' + map + '.json' : HOST + '/maps/' + map + '.bsp';
  }
  function fileName(kind, map) { return map + (kind === 'zones' ? '.json' : '.bsp'); }
  function mb(n) {
    return n < 1048576 ? Math.max(1, Math.round(n / 1024)) + ' KB' : (n / 1048576).toFixed(n < 10485760 ? 1 : 0) + ' MB';
  }

  function save(blob, name) {
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = name;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(function () { URL.revokeObjectURL(a.href); }, 60000);
  }

  // Resolves with the byte count once saved. A 404 rejects with err.missing set.
  function get(kind, map, progress) {
    if (!NAME.test(map)) { return Promise.reject(new Error('not a map name')); }
    return fetch(url(kind, map), { credentials: 'omit' }).then(function (r) {
      if (r.status === 404) { var e = new Error('not on the servers'); e.missing = true; throw e; }
      if (!r.ok) { throw new Error('HTTP ' + r.status); }
      var total = +r.headers.get('Content-Length') || 0;
      if (!r.body || !r.body.getReader) { return r.blob(); }
      var reader = r.body.getReader(), parts = [], done = 0;
      function pump() {
        return reader.read().then(function (s) {
          if (s.done) { return new Blob(parts, { type: 'application/octet-stream' }); }
          parts.push(s.value);
          done += s.value.length;
          if (progress) { progress(done, total); }
          return pump();
        });
      }
      return pump();
    }).then(function (blob) {
      save(blob, fileName(kind, map));
      return blob.size;
    });
  }

  // HEAD through the same redirect: its size in bytes (or true) when the file exists, false on 404, null when it
  // cannot tell.
  function exists(kind, map) {
    if (!NAME.test(map)) { return Promise.resolve(false); }
    return fetch(url(kind, map), { method: 'HEAD', credentials: 'omit' }).then(function (r) {
      return r.ok ? (+r.headers.get('Content-Length') || true) : r.status === 404 ? false : null;
    }, function () { return null; });
  }

  // A button that downloads on click and reports progress in its own label. Asking again for the same file and
  // class returns the same element, so a list that redraws keeps a running download; another class (the zoning
  // page's recent list beside its rows) gets its own, or appending it would move it out of the other list.
  function button(kind, map, label, cls) {
    var key = kind + ':' + map + ':' + (cls || '');
    if (made[key]) { return made[key]; }
    var b = made[key] = document.createElement('button'), running = false;
    b.type = 'button';
    b.className = cls || 'dlbtn';
    b.textContent = label;
    b.title = 'Save ' + fileName(kind, map);
    b.addEventListener('click', function () {
      if (running) { return; }
      running = true;
      b.disabled = true;
      b.textContent = 'Starting…';
      get(kind, map, function (done, total) {
        b.textContent = total ? Math.floor(100 * done / total) + '%' : mb(done);
      }).then(function (n) {
        b.textContent = 'Saved ✓';
        b.title = fileName(kind, map) + ', ' + mb(n);
      }, function (e) {
        b.textContent = e.missing ? (kind === 'zones' ? 'No zones yet' : 'Not on the servers') : 'Retry ' + label.toLowerCase();
        b.title = e.missing ? fileName(kind, map) + ' is not on the servers'
                            : 'The download failed (' + e.message + '). Click to try again.';
        b.disabled = !!e.missing;
      }).then(function () { running = false; if (!b.textContent.indexOf('Saved')) { b.disabled = false; } });
    });
    return b;
  }

  window.wosDownload = { get: get, exists: exists, button: button, url: url, fileName: fileName, NAME: NAME, mb: mb };
})();
