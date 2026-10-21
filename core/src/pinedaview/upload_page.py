# SPDX-License-Identifier: Apache-2.0
"""The standalone "scan to add photos" page.

Served at ``/upload`` for anyone on the LAN who scans the QR shown on the
photo card. Deliberately *not* part of the SPA: it is a single self-contained
HTML document so it stays tiny, loads instantly on an old phone, and works
before setup is complete. Uploads go to the public ``POST /api/photos``.
"""

from __future__ import annotations

UPLOAD_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
<meta name="theme-color" content="#000000" />
<title>Add photos · PinedaDisplay</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; margin: 0; }
  body {
    min-height: 100dvh;
    background: #000;
    color: #f4efe5;
    font: 16px/1.5 "Helvetica Neue", system-ui, sans-serif;
    padding: max(24px, env(safe-area-inset-top)) 20px
      max(24px, env(safe-area-inset-bottom));
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 22px;
  }
  h1 { font-size: 1.5rem; font-weight: 300; text-align: center; }
  p.sub { color: rgba(244, 239, 229, 0.6); text-align: center; font-size: 0.95rem; }
  label.pick {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 100%;
    max-width: 420px;
    padding: 18px;
    border-radius: 999px;
    background: #e7a34a;
    color: #000;
    font-weight: 600;
    cursor: pointer;
  }
  label.pick.busy { opacity: 0.55; pointer-events: none; }
  input[type=file] { position: absolute; width: 1px; height: 1px; opacity: 0; }
  ul {
    list-style: none;
    padding: 0;
    width: 100%;
    max-width: 420px;
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(88px, 1fr));
    gap: 8px;
  }
  li {
    position: relative;
    aspect-ratio: 1;
    border-radius: 10px;
    overflow: hidden;
    background: rgba(244, 239, 229, 0.08);
  }
  li img, li video { width: 100%; height: 100%; object-fit: cover; display: block; }
  li .state {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.72rem;
    text-align: center;
    padding: 4px;
    background: rgba(0, 0, 0, 0.45);
  }
  li.ok .state { display: none; }
  li.err .state { background: rgba(120, 20, 20, 0.7); }
  .done { color: rgba(244, 239, 229, 0.6); font-size: 0.9rem; text-align: center; }
</style>
</head>
<body>
  <h1>Add photos to the display</h1>
  <p class="sub">They appear in the photo frame within a few seconds.</p>

  <label class="pick" id="pick">
    Choose photos
    <input type="file" multiple
      accept="image/jpeg,image/png,image/webp,video/quicktime,video/mp4" />
  </label>

  <ul id="grid"></ul>
  <p class="done" id="done" hidden></p>

<script>
  var input = document.querySelector('input');
  var pick = document.getElementById('pick');
  var grid = document.getElementById('grid');
  var done = document.getElementById('done');
  var added = 0;

  input.addEventListener('change', async function () {
    var files = Array.prototype.slice.call(input.files || []);
    if (!files.length) return;
    pick.classList.add('busy');
    pick.firstChild.textContent = 'Uploading…';

    for (var i = 0; i < files.length; i++) {
      await send(files[i]);
    }

    pick.classList.remove('busy');
    pick.firstChild.textContent = 'Choose more';
    input.value = '';
    done.hidden = false;
    done.textContent = added + (added === 1 ? ' photo added.' : ' photos added.');
  });

  function send(file) {
    var li = document.createElement('li');
    // A Live Photo saved as a video: show its first frame.
    var video = file.type.indexOf('video/') === 0;
    var img = document.createElement(video ? 'video' : 'img');
    img.src = URL.createObjectURL(file) + (video ? '#t=0.1' : '');
    if (video) { img.muted = true; img.playsInline = true; }
    var state = document.createElement('div');
    state.className = 'state';
    state.textContent = '…';
    li.appendChild(img);
    li.appendChild(state);
    grid.appendChild(li);

    var form = new FormData();
    form.append('file', file);
    return fetch('/api/photos', { method: 'POST', body: form })
      .then(function (r) {
        if (r.ok) { li.className = 'ok'; added++; return; }
        li.className = 'err';
        state.textContent = r.status === 409 ? 'already added'
          : r.status === 413 ? 'over 10 s'
          : r.status === 415 ? 'not an image'
          : 'failed (' + r.status + ')';
      })
      .catch(function () { li.className = 'err'; state.textContent = 'no connection'; });
  }
</script>
</body>
</html>
"""
