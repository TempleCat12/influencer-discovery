# HTML Output Template — Bilingual (Chinese/English)

Every influencer-discovery run produces an `.html` file alongside the `.md` report. The HTML must include a **Chinese/English language toggle button** so the reader can switch between languages.

---

## Structure

The HTML uses a **two-body** approach for clean language switching:

```
┌─────────────────────────────────────────┐
│  [🌐 English] [🌐 中文]   ← fixed toggle │
├─────────────────────────────────────────┤
│                                         │
│  <div id="content-en">  or  <div id="content-zh">  │
│       (visible based on toggle)          │
│                                         │
└─────────────────────────────────────────┘
```

- `#content-en` — full English content
- `#content-zh` — full Chinese content  
- Both divs are present in the DOM; only one is visible at a time
- Toggle state is saved to `localStorage` so the preference persists across page reloads

---

## Python Conversion Script

The script below:

1. Reads the MD report
2. Converts English MD → English HTML
3. Converts Chinese MD → Chinese HTML (the report author must provide both language versions, or the script falls back to auto-translation of key terms)
4. Wraps both in a styled page with the toggle

```python
#!/usr/bin/env python3
"""
Convert an influencer-discovery MD report to a bilingual HTML file
with Chinese/English language toggle.

Usage:
    python3 build_html.py <input_md_path> [--output <html_path>]

If only the English MD is provided, the script still generates a
bilingual shell — but the Chinese side will mirror the English content
with a note that manual translation is pending for nuanced sections.
"""

import markdown
import sys
import os
import re
import json
from pathlib import Path

# ── CSS (shared across all reports) ──────────────────────────

CSS = r"""
:root {
  --bg: #ffffff;
  --text: #1a1a2e;
  --text-secondary: #555;
  --border: #e0e0e0;
  --accent: #c2185b;
  --accent-light: #fce4ec;
  --toggle-bg: #f5f5f5;
  --toggle-active: #c2185b;
  --toggle-text: #fff;
  --table-stripe: #fafafa;
  --code-bg: #f5f5f5;
}

* { margin: 0; padding: 0; box-sizing: border-box; }

body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
               "Helvetica Neue", Arial, "PingFang SC", "Microsoft YaHei", sans-serif;
  color: var(--text);
  background: var(--bg);
  line-height: 1.7;
  padding: 20px 24px 40px;
  max-width: 960px;
  margin: 0 auto;
}

/* ── Language Toggle ── */
.toggle-bar {
  position: sticky;
  top: 0;
  z-index: 100;
  display: flex;
  justify-content: flex-end;
  gap: 0;
  padding: 10px 0 16px;
  background: linear-gradient(to bottom, #fff 60%, transparent);
}

.toggle-btn {
  padding: 7px 20px;
  border: 2px solid var(--accent);
  background: var(--toggle-bg);
  color: var(--accent);
  cursor: pointer;
  font-size: 0.9rem;
  font-weight: 600;
  transition: all 0.2s ease;
  outline: none;
}

.toggle-btn:first-child { border-radius: 6px 0 0 6px; }
.toggle-btn:last-child  { border-radius: 0 6px 6px 0; }

.toggle-btn.active {
  background: var(--toggle-active);
  color: var(--toggle-text);
}

.toggle-btn:hover:not(.active) {
  background: var(--accent-light);
}

/* ── Typography ── */
h1 {
  font-size: 2rem;
  color: var(--accent);
  border-bottom: 3px solid var(--accent);
  padding-bottom: 12px;
  margin-bottom: 8px;
  line-height: 1.3;
}

h2 {
  font-size: 1.5rem;
  color: var(--accent);
  margin-top: 36px;
  margin-bottom: 16px;
  padding-bottom: 6px;
  border-bottom: 2px solid var(--border);
}

h3 {
  font-size: 1.2rem;
  color: #333;
  margin-top: 28px;
  margin-bottom: 10px;
}

h4 {
  font-size: 1.05rem;
  color: var(--accent);
  margin-top: 20px;
  margin-bottom: 8px;
}

p { margin-bottom: 12px; }

hr {
  border: none;
  border-top: 1px solid var(--border);
  margin: 28px 0;
}

strong { color: #222; }

/* ── Tables ── */
table {
  width: 100%;
  border-collapse: collapse;
  margin: 16px 0 24px;
  font-size: 0.92rem;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 1px 4px rgba(0,0,0,0.06);
}

thead { background: var(--accent); }

thead th {
  color: #fff;
  padding: 10px 14px;
  text-align: left;
  font-weight: 600;
  white-space: nowrap;
}

tbody td {
  padding: 9px 14px;
  border-bottom: 1px solid var(--border);
  vertical-align: top;
}

tbody tr:nth-child(even) { background: var(--table-stripe); }
tbody tr:hover { background: var(--accent-light); }

/* ── Lists & Code ── */
ul, ol { margin: 8px 0 16px 24px; }
li { margin-bottom: 4px; }

a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }

code {
  background: var(--code-bg);
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 0.9em;
  font-family: "SF Mono", "Fira Code", "Consolas", monospace;
}

blockquote {
  border-left: 4px solid var(--accent);
  padding: 10px 18px;
  margin: 16px 0;
  background: var(--accent-light);
  border-radius: 0 6px 6px 0;
  color: #555;
}

/* ── Notes / Warning callouts ── */
.callout-warn {
  background: #fff3e0;
  border-left: 4px solid #e65100;
  padding: 10px 16px;
  margin: 12px 0;
  border-radius: 0 6px 6px 0;
}

/* ── Language visibility ── */
.lang-content { display: none; }
.lang-content.active { display: block; }

/* ── Responsive ── */
@media (max-width: 768px) {
  body { padding: 16px 12px; font-size: 0.9rem; }
  table { font-size: 0.78rem; }
  thead th, tbody td { padding: 6px 8px; }
  .toggle-btn { padding: 6px 14px; font-size: 0.82rem; }
}

/* ── Print ── */
@media print {
  .toggle-bar { display: none; }
  .lang-content { display: block !important; }
  body { padding: 20px; max-width: 100%; }
  table { box-shadow: none; }
  thead { background: #333; }
}
"""

# ── JavaScript toggle ───────────────────────────────────────

JS_TOGGLE = r"""
<script>
(function() {
  const STORAGE_KEY = 'influencer-discovery-lang';
  const btnEn = document.getElementById('btn-en');
  const btnZh = document.getElementById('btn-zh');
  const contentEn = document.getElementById('content-en');
  const contentZh = document.getElementById('content-zh');

  function setLang(lang) {
    if (lang === 'zh') {
      btnZh.classList.add('active');
      btnEn.classList.remove('active');
      contentZh.classList.add('active');
      contentEn.classList.remove('active');
    } else {
      btnEn.classList.add('active');
      btnZh.classList.remove('active');
      contentEn.classList.add('active');
      contentZh.classList.remove('active');
    }
    try { localStorage.setItem(STORAGE_KEY, lang); } catch(e) {}
  }

  // Init: respect saved preference, fallback to browser detection, then English
  var saved = null;
  try { saved = localStorage.getItem(STORAGE_KEY); } catch(e) {}
  if (saved === 'zh' || saved === 'en') {
    setLang(saved);
  } else if (navigator.language && navigator.language.startsWith('zh')) {
    setLang('zh');
  } else {
    setLang('en');
  }

  btnEn.addEventListener('click', function() { setLang('en'); });
  btnZh.addEventListener('click', function() { setLang('zh'); });
})();
</script>
"""


def md_to_html(md_text: str) -> str:
    """Convert markdown to clean HTML body."""
    html = markdown.markdown(
        md_text,
        extensions=["tables", "fenced_code", "nl2br"]
    )
    # Collapse excessive <br> tags
    html = re.sub(r'<br\s*/?>\s*<br\s*/?>', '<br>', html)
    return html


def build_bilingual_html(
    html_en: str,
    html_zh: str,
    title_en: str,
    title_zh: str
) -> str:
    """Wrap English and Chinese HTML bodies into a full page with toggle."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title_en} / {title_zh}</title>
  <style>{CSS}</style>
</head>
<body>

<div class="toggle-bar">
  <button class="toggle-btn active" id="btn-en">🇺🇸 English</button>
  <button class="toggle-btn" id="btn-zh">🇨🇳 中文</button>
</div>

<div class="lang-content active" id="content-en">
{html_en}
</div>

<div class="lang-content" id="content-zh">
{html_zh}
</div>

{JS_TOGGLE}

</body>
</html>"""


# ── Main ─────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 build_html.py <input_md_path> [--output <html_path>]")
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] != "--output" \
                   else input_path.replace(".md", ".html")

    # Parse --output flag
    for i, arg in enumerate(sys.argv):
        if arg == "--output" and i + 1 < len(sys.argv):
            output_path = sys.argv[i + 1]

    with open(input_path, "r", encoding="utf-8") as f:
        md_text = f.read()

    # ── IMPORTANT ──────────────────────────────────────────
    # The MD file should contain BOTH languages, separated by:
    # <!-- LANG:ZH --> marker.
    #
    # Everything BEFORE the marker is English.
    # Everything AFTER  the marker is Chinese.
    #
    # If no marker is found, the script processes the entire
    # file as English and duplicates it for Chinese with a
    # warning banner — the report author should provide a
    # proper Chinese version.
    # ────────────────────────────────────────────────────────

    lang_split = re.split(r'<!--\s*LANG:ZH\s*-->', md_text, maxsplit=1)

    if len(lang_split) == 2:
        md_en = lang_split[0].strip()
        md_zh = lang_split[1].strip()
    else:
        md_en = md_text.strip()
        md_zh = f"> ⚠️ 中文版本尚未提供。请参考上方英文版本。\n>\n> Chinese translation pending. Please refer to the English version above.\n\n{md_text.strip()}"

    html_en = md_to_html(md_en)
    html_zh = md_to_html(md_zh)

    # Extract title from first h1
    title_match = re.search(r'^#\s+(.+)$', md_en, re.MULTILINE)
    title_en = title_match.group(1) if title_match else "Influencer Discovery Report"
    title_zh = "红人发现报告"

    full_html = build_bilingual_html(html_en, html_zh, title_en, title_zh)

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(full_html)

    print(f"✅ Bilingual HTML written to: {output_path}")
    print(f"   Size: {len(full_html):,} bytes")
    print(f"   Toggle: Chinese / English (persists via localStorage)")
```

---

## MD Bilingual Convention

To supply both languages, the MD report uses a separator comment:

```markdown
# Influencer Discovery: Parenting · USA · Momcozy-Adjacent

**Search Date**: 2026-07-23
...

(all English content above the marker)

<!-- LANG:ZH -->

# 红人发现：育儿 · 美国 · Momcozy 相关品牌

**搜索日期**：2026-07-23
...

(all Chinese content below the marker)
```

When the `<!-- LANG:ZH -->` marker is present, the script splits the MD into two halves and builds a proper bilingual HTML. When absent, the Chinese side falls back to a placeholder.

---

## Behavior

| Feature | Detail |
|---------|--------|
| **Default language** | Respects `localStorage` → browser `navigator.language` → English |
| **Toggle persistence** | Saves choice to `localStorage`; survives page reloads |
| **Print behavior** | Toggle bar is hidden; both languages print (user can toggle before printing) |
| **Responsive** | Works on mobile; sticky toggle bar |
| **Font stack** | System fonts + PingFang SC / Microsoft YaHei for Chinese rendering |

---

## See Also

- [templates.md](templates.md) — MD report templates
- [platform-vetting.md](platform-vetting.md) — platform playbooks
- [../SKILL.md](../SKILL.md) — main skill contract
