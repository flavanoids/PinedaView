# SPDX-License-Identifier: Apache-2.0
"""Standalone pages for the "scan to connect a calendar" flow, Google and
Apple alike.

Same idea as :mod:`pinedaview.upload_page`: tiny, self-contained HTML, no SPA
dependency, so it loads instantly on whatever phone scanned the QR. Rendered
server-side because their content is dynamic:

- :func:`render_not_configured` — the operator hasn't set a Google OAuth
  client / bounce URL yet (``GET /connect-calendar`` before that's done).
- :func:`render_picker` — after Google's consent screen (or a successful
  Apple sign-in), choose which of the account's calendars — own, shared,
  subscribed — to show. ``source_type`` tags what gets saved so one backend's
  save never clobbers the other's.
- :func:`render_apple_form` — Apple ID + app-specific password. No OAuth
  exists for iCloud, so this is the whole "connect" step; a wrong password
  re-renders the same form with an inline error rather than a full failure
  page, since retrying is one field-edit away.
- :func:`render_error` — the pairing attempt failed or expired.
"""

from __future__ import annotations

import html
import json

_STYLE = """
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  html, body { margin: 0; }
  body {
    min-height: 100dvh;
    background: #000;
    color: #f4efe5;
    font: 16px/1.5 "Helvetica Neue", system-ui, sans-serif;
    padding: max(24px, env(safe-area-inset-top)) 20px max(24px, env(safe-area-inset-bottom));
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 20px;
  }
  h1 { font-size: 1.4rem; font-weight: 300; text-align: center; margin: 0; }
  p.sub { color: rgba(244, 239, 229, 0.6); text-align: center; font-size: 0.92rem; margin: 0; }
  .card {
    width: 100%;
    max-width: 440px;
    background: #171310;
    border-radius: 16px;
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  label.row {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 4px;
    border-bottom: 1px solid rgba(244, 239, 229, 0.08);
  }
  label.row:last-child { border-bottom: none; }
  label.row input[type=checkbox] { width: 20px; height: 20px; accent-color: #e7a34a; }
  .swatch { width: 12px; height: 12px; border-radius: 50%; flex: none; }
  .name { flex: 1; font-size: 0.95rem; }
  .role { font-size: 0.72rem; color: rgba(244, 239, 229, 0.45); text-transform: uppercase; }
  button.primary {
    width: 100%;
    max-width: 440px;
    padding: 16px;
    border: none;
    border-radius: 999px;
    background: #e7a34a;
    color: #1a1300;
    font: inherit;
    font-weight: 600;
    font-size: 1rem;
    cursor: pointer;
  }
  button.primary:disabled { opacity: 0.5; }
  p.status {
    font-size: 0.85rem;
    color: rgba(244, 239, 229, 0.6);
    text-align: center;
    min-height: 1.2em;
  }
  .done {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
    text-align: center;
    padding: 20px 0;
  }
  .done .checkmark {
    width: 56px;
    height: 56px;
    border-radius: 50%;
    background: #4caf7d;
    color: #fff;
    font-size: 1.6rem;
    display: flex;
    align-items: center;
    justify-content: center;
    margin-bottom: 6px;
  }
  .done p { margin: 0; font-size: 1.1rem; }
  .done p.sub { font-size: 0.9rem; }
  form.card { align-items: stretch; }
  form.card label {
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: rgba(244, 239, 229, 0.45);
  }
  form.card input {
    width: 100%;
    padding: 13px 14px;
    border-radius: 12px;
    border: 1px solid rgba(244, 239, 229, 0.14);
    background: rgba(244, 239, 229, 0.04);
    color: #f4efe5;
    font: inherit;
    margin-bottom: 4px;
  }
  p.status.error { color: #e58a8a; }
  a.link { color: #e7a34a; }
"""


def _page(title: str, body: str, *, extra_style: str = "") -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
<meta name="theme-color" content="#000000" />
<title>{html.escape(title)}</title>
<style>{_STYLE}{extra_style}</style>
</head>
<body>
{body}
</body>
</html>
"""


def render_not_configured() -> str:
    body = """
  <h1>Calendar setup isn't finished yet</h1>
  <p class="sub">
    This display needs a Google OAuth client id/secret (in Settings → Secrets)
    and a bounce-page URL (in the calendar config) before it can connect an
    account. See docs/INSTALL.md for the five-minute setup.
  </p>
"""
    return _page("Calendar not set up", body)


def render_apple_form(*, error: str | None = None) -> str:
    error_html = f'<p class="status error">{html.escape(error)}</p>' if error else ""
    body = f"""
  <h1>Connect Apple Calendar</h1>
  <p class="sub">
    Use your Apple ID and an <strong>app-specific password</strong> — not your
    real one. Generate one at
    <a class="link" href="https://appleid.apple.com/account/manage">appleid.apple.com</a>
    under Sign-In and Security &rarr; App-Specific Passwords.
  </p>
  <form class="card" method="POST" action="/api/calendar/apple/connect">
    <label for="apple_id">Apple ID</label>
    <input id="apple_id" name="apple_id" type="email" required autocomplete="username" />
    <label for="password">App-specific password</label>
    <input
      id="password" name="password" type="password" required
      autocomplete="current-password" placeholder="xxxx-xxxx-xxxx-xxxx"
    />
    <button class="primary" type="submit">Connect</button>
  </form>
  {error_html}
"""
    return _page("Connect Apple Calendar", body)


def render_error(message: str) -> str:
    body = f"""
  <h1>Couldn't connect your calendar</h1>
  <p class="sub">{html.escape(message)}</p>
  <p class="sub">Go back to the display and scan the QR code again.</p>
"""
    return _page("Connection failed", body)


def render_picker(
    *,
    email: str,
    calendars: list[dict[str, object]],
    existing_selection: dict[str, bool] | None = None,
    source_type: str = "google",
) -> str:
    """``existing_selection`` (calendarId → selected) comes from a prior save —
    when set, it wins over the "owns/can-edit" default so refreshing the list
    (to pick up a newly-shared calendar) doesn't silently un-pick anything."""
    rows = []
    slim = [
        {
            "id": str(c.get("id", "")),
            "summary": str(c.get("summary", c.get("id", ""))),
            "backgroundColor": c.get("backgroundColor"),
        }
        for c in calendars
    ]
    calendars_json = json.dumps(slim).replace("</", "<\\/")
    for cal in calendars:
        cal_id = str(cal.get("id", ""))
        summary = str(cal.get("summary", cal_id))
        color = str(cal.get("backgroundColor") or "#e7a34a")
        role = str(cal.get("accessRole", ""))
        primary = bool(cal.get("primary"))
        if existing_selection is not None and cal_id in existing_selection:
            is_checked = existing_selection[cal_id]
        else:
            is_checked = primary or role in ("owner", "writer")
        checked = "checked" if is_checked else ""
        rows.append(
            f"""<label class="row">
      <input type="checkbox" value="{html.escape(cal_id, quote=True)}" {checked} />
      <span class="swatch" style="background:{html.escape(color, quote=True)}"></span>
      <span class="name">{html.escape(summary)}</span>
      <span class="role">{html.escape(role)}</span>
    </label>"""
        )
    body = f"""
  <h1 id="heading">Choose your calendars</h1>
  <p class="sub" id="subheading">
    Connected as {html.escape(email)}. Pick which ones show on the display.
  </p>
  <div class="card" id="list">
    {"".join(rows)}
  </div>
  <button class="primary" id="save">Save</button>
  <p class="status" id="status"></p>
  <div class="done" id="done" hidden>
    <div class="checkmark">&#10003;</div>
    <p>Connected</p>
    <p class="sub">You can close this tab and go back to the display.</p>
  </div>

<script>
  var list = document.getElementById('list');
  var save = document.getElementById('save');
  var status = document.getElementById('status');
  var heading = document.getElementById('heading');
  var subheading = document.getElementById('subheading');
  var done = document.getElementById('done');
  var calendars = {calendars_json};

  save.addEventListener('click', function () {{
    save.disabled = true;
    status.textContent = 'Saving…';
    var checked = Array.prototype.slice.call(list.querySelectorAll('input:checked'))
      .map(function (el) {{ return el.value; }});
    var sources = calendars.map(function (c) {{
      return {{
        calendarId: c.id,
        label: c.summary || c.id,
        color: c.backgroundColor || null,
        selected: checked.indexOf(c.id) !== -1,
        type: {json.dumps(source_type)}
      }};
    }});
    fetch('/api/calendar/sources', {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify({{ sources: sources }})
    }}).then(function (r) {{
      if (r.ok) {{
        heading.hidden = true;
        subheading.hidden = true;
        list.hidden = true;
        save.hidden = true;
        status.hidden = true;
        done.hidden = false;
        done.scrollIntoView({{ block: 'center' }});
      }} else {{
        status.textContent = 'Something went wrong — try again.';
        save.disabled = false;
      }}
    }}).catch(function () {{
      status.textContent = 'No connection — try again.';
      save.disabled = false;
    }});
  }});
</script>
"""
    return _page("Choose your calendars", body)
