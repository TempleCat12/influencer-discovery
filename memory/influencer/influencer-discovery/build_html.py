#!/usr/bin/env python3
"""
Universal bilingual HTML builder for influencer-discovery reports.
Reads any MD file with `<!-- LANG:ZH -->` marker, outputs a styled
bilingual HTML with:
  - Fixed left TOC sidebar (desktop), collapsible hamburger (mobile)
  - Chinese/English language toggle (persists via localStorage)
  - Auto-generated TOC from h2/h3 headings
  - Active section highlighting via IntersectionObserver
  - Responsive + print-ready

Usage:
    python3 build_html.py <input_md_path> [--output <html_path>]
"""
import markdown, re, os, sys

# ── CSS ─────────────────────────────────────────────────────
CSS = r"""
:root {
  --bg: #ffffff; --text: #1a1a2e; --text-secondary: #555;
  --border: #e0e0e0; --accent: #c2185b; --accent-light: #fce4ec;
  --toggle-bg: #f5f5f5; --toggle-active: #c2185b; --toggle-text: #fff;
  --table-stripe: #fafafa; --code-bg: #f5f5f5;
  --sidebar-w: 250px; --sidebar-bg: #fafafa;
}

* { margin: 0; padding: 0; box-sizing: border-box; }

body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
               "Helvetica Neue", Arial, "PingFang SC", "Microsoft YaHei", sans-serif;
  color: var(--text); background: var(--bg); line-height: 1.7;
}

/* ── Sidebar ── */
.sidebar {
  position: fixed; top: 0; left: 0; width: var(--sidebar-w); height: 100vh;
  background: var(--sidebar-bg); border-right: 1px solid var(--border);
  overflow-y: auto; z-index: 200; padding: 20px 16px;
}
.sidebar h3 {
  font-size: 0.85rem; color: var(--accent); text-transform: uppercase;
  letter-spacing: 0.05em; margin-bottom: 12px; padding-bottom: 8px;
  border-bottom: 2px solid var(--accent);
}
.sidebar nav a {
  display: block; padding: 5px 10px; font-size: 0.82rem; color: var(--text-secondary);
  text-decoration: none; border-radius: 4px; margin-bottom: 2px;
  transition: all 0.15s ease; border-left: 3px solid transparent;
}
.sidebar nav a:hover { background: var(--accent-light); color: var(--accent); }
.sidebar nav a.active {
  background: var(--accent-light); color: var(--accent); font-weight: 600;
  border-left-color: var(--accent);
}
.sidebar nav a.toc-h3 { padding-left: 24px; font-size: 0.78rem; }

/* ── Hamburger (mobile) ── */
.hamburger {
  display: none; position: fixed; top: 12px; left: 12px; z-index: 300;
  width: 40px; height: 40px; background: var(--accent); color: #fff;
  border: none; border-radius: 8px; font-size: 1.3rem; cursor: pointer;
  align-items: center; justify-content: center; box-shadow: 0 2px 8px rgba(0,0,0,0.15);
}
.sidebar-overlay { display: none; }

/* ── Main content ── */
.main-wrap {
  margin-left: var(--sidebar-w); padding: 20px 32px 40px; max-width: 960px;
}

/* ── Toggle bar ── */
.toggle-bar {
  position: sticky; top: 0; z-index: 100; display: flex;
  justify-content: flex-end; gap: 0; padding: 10px 0 16px;
  background: linear-gradient(to bottom, #fff 60%, transparent);
}
.toggle-btn {
  padding: 8px 22px; border: 2px solid var(--accent);
  background: var(--toggle-bg); color: var(--accent); cursor: pointer;
  font-size: 0.92rem; font-weight: 600; transition: all 0.2s ease;
  outline: none; font-family: inherit;
}
.toggle-btn:first-child { border-radius: 8px 0 0 8px; }
.toggle-btn:last-child  { border-radius: 0 8px 8px 0; }
.toggle-btn.active { background: var(--toggle-active); color: var(--toggle-text); }
.toggle-btn:hover:not(.active) { background: var(--accent-light); }

/* ── Typography ── */
h1 { font-size: 1.85rem; color: var(--accent); border-bottom: 3px solid var(--accent); padding-bottom: 12px; margin-bottom: 8px; line-height: 1.3; }
h2 { font-size: 1.4rem; color: var(--accent); margin-top: 36px; margin-bottom: 14px; padding-bottom: 6px; border-bottom: 2px solid var(--border); }
h3 { font-size: 1.15rem; color: #333; margin-top: 28px; margin-bottom: 10px; }
h4 { font-size: 1.02rem; color: var(--accent); margin-top: 20px; margin-bottom: 8px; }
p { margin-bottom: 12px; }
hr { border: none; border-top: 1px solid var(--border); margin: 28px 0; }
strong { color: #222; }

table { width: 100%; border-collapse: collapse; margin: 14px 0 22px; font-size: 0.9rem; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }
thead { background: var(--accent); }
thead th { color: #fff; padding: 9px 12px; text-align: left; font-weight: 600; white-space: nowrap; }
tbody td { padding: 8px 12px; border-bottom: 1px solid var(--border); vertical-align: top; }
tbody tr:nth-child(even) { background: var(--table-stripe); }
tbody tr:hover { background: var(--accent-light); }

ul, ol { margin: 8px 0 14px 24px; }
li { margin-bottom: 4px; }
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
code { background: var(--code-bg); padding: 2px 6px; border-radius: 4px; font-size: 0.9em; font-family: "SF Mono", "Fira Code", "Consolas", monospace; }
blockquote { border-left: 4px solid var(--accent); padding: 10px 16px; margin: 14px 0; background: var(--accent-light); border-radius: 0 6px 6px 0; color: #555; }

.lang-content { display: none; }
.lang-content.active { display: block; }

/* ── Responsive ── */
@media (max-width: 900px) {
  .sidebar { transform: translateX(-100%); transition: transform 0.25s ease; }
  .sidebar.open { transform: translateX(0); box-shadow: 4px 0 20px rgba(0,0,0,0.15); }
  .sidebar-overlay { display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.3); z-index: 199; }
  .sidebar-overlay.open { display: block; }
  .hamburger { display: flex; }
  .main-wrap { margin-left: 0; padding: 16px 12px 40px; }
  body { font-size: 0.9rem; }
  table { font-size: 0.78rem; }
  thead th, tbody td { padding: 6px 8px; }
  .toggle-btn { padding: 6px 14px; font-size: 0.82rem; }
}

@media print {
  .sidebar, .hamburger, .sidebar-overlay, .toggle-bar { display: none; }
  .lang-content { display: block !important; }
  .main-wrap { margin-left: 0; padding: 16px; max-width: 100%; }
  table { box-shadow: none; } thead { background: #333; }
}
"""

# ── JavaScript (TOC builder + toggle + mobile sidebar) ────
JS = r"""<script>
(function(){
  // ── Language toggle ──
  var K='inf-discovery-lang',
      be=document.getElementById('btn-en'),bz=document.getElementById('btn-zh'),
      ce=document.getElementById('content-en'),cz=document.getElementById('content-zh');
  function setLang(l){
    if(l==='zh'){bz.classList.add('active');be.classList.remove('active');cz.classList.add('active');ce.classList.remove('active');buildTOC('zh');}
    else{be.classList.add('active');bz.classList.remove('active');ce.classList.add('active');cz.classList.remove('active');buildTOC('en');}
    try{localStorage.setItem(K,l);}catch(e){}
  }
  var s=null;try{s=localStorage.getItem(K);}catch(e){}
  var initial = (s==='zh'||s==='en')?s:(navigator.language&&navigator.language.startsWith('zh')?'zh':'en');
  setLang(initial);
  be.addEventListener('click',function(){setLang('en');});
  bz.addEventListener('click',function(){setLang('zh');});

  // ── Build TOC from headings ──
  var tocLabels = {
    zh: {toc:'目 录', step:'第{0}步'},
    en: {toc:'Contents', step:'Step {0}'}
  };

  function buildTOC(lang){
    var activeContent = document.getElementById(lang==='zh'?'content-zh':'content-en');
    var nav = document.getElementById('toc-nav');
    if(!activeContent||!nav)return;
    var hs = activeContent.querySelectorAll('h2,h3');
    var html='';
    var stepNum=0, inProfiles=false;
    for(var i=0;i<hs.length;i++){
      var h=hs[i], tag=h.tagName.toLowerCase();
      var id='sec-'+i;
      h.id=id;

      // Detect step headers
      var txt=h.textContent.trim();
      var mStep=txt.match(/第[一二三四五六七八九十]+步|Step\s+(\d+)/i);
      if(mStep&&tag==='h2'){stepNum++;}

      // Generate TOC label
      var label=txt;
      // Truncate long influencer titles
      if(txt.indexOf('达人 #')>-1||txt.indexOf('Influencer #')>-1||txt.indexOf('WL-')>-1){
        label=txt.substring(0,50)+(txt.length>50?'…':'');
      }
      if(txt.indexOf('观察名单')>-1||txt.indexOf('Watch List')>-1){stepNum=0;}

      html+='<a href="#'+id+'" class="toc-'+(tag==='h3'?'h3':'h2')+'" title="'+txt.replace(/"/g,'&quot;')+'">'+label+'</a>';
    }
    // Update toc title
    var labels=tocLabels[lang]||tocLabels['en'];
    document.getElementById('toc-title').textContent=labels.toc;
    nav.innerHTML=html;

    // Re-bind click handlers
    nav.querySelectorAll('a').forEach(function(a){
      a.addEventListener('click',function(e){
        e.preventDefault();
        var target=document.getElementById(this.getAttribute('href').substring(1));
        if(target){target.scrollIntoView({behavior:'smooth',block:'start'});}
        // Close sidebar on mobile
        document.getElementById('sidebar').classList.remove('open');
        document.getElementById('sidebar-overlay').classList.remove('open');
      });
    });

    // Highlight active section
    var observer=new IntersectionObserver(function(entries){
      entries.forEach(function(entry){
        if(entry.isIntersecting){
          nav.querySelectorAll('a').forEach(function(a){a.classList.remove('active');});
          var link=nav.querySelector('a[href="#'+entry.target.id+'"]');
          if(link)link.classList.add('active');
        }
      });
    },{rootMargin:'-80px 0px -70% 0px'});
    hs.forEach(function(h){observer.observe(h);});
  }

  // ── Mobile sidebar toggle ──
  document.getElementById('hamburger').addEventListener('click',function(){
    document.getElementById('sidebar').classList.add('open');
    document.getElementById('sidebar-overlay').classList.add('open');
  });
  document.getElementById('sidebar-overlay').addEventListener('click',function(){
    document.getElementById('sidebar').classList.remove('open');
    document.getElementById('sidebar-overlay').classList.remove('open');
  });
})();
</script>"""

# ── HTML wrapper ────────────────────────────────────────────
def md2html(text):
    html = markdown.markdown(text, extensions=["tables", "fenced_code", "nl2br"])
    return re.sub(r'<br\s*/?>\s*<br\s*/?>', '<br>', html)

def build(input_md_path, output_html_path=None):
    if output_html_path is None:
        output_html_path = input_md_path.replace(".md", ".html")

    with open(input_md_path, "r", encoding="utf-8") as f:
        md_text = f.read()

    parts = re.split(r'<!--\s*LANG:ZH\s*-->', md_text, maxsplit=1)
    if len(parts) == 2:
        md_zh = parts[0].strip()
        md_en = parts[1].strip()
    else:
        md_zh = md_text.strip()
        md_en = md_text.strip()

    html_zh = md2html(md_zh)
    html_en = md2html(md_en)

    # Extract title
    title_match = re.search(r'^#\s+(.+)$', md_zh, re.MULTILINE)
    title_zh = title_match.group(1) if title_match else ""
    title_en_match = re.search(r'^#\s+(.+)$', md_en, re.MULTILINE)
    title_en = title_en_match.group(1) if title_en_match else title_zh

    full = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title_zh} / {title_en}</title>
<style>{CSS}</style>
</head>
<body>

<button class="hamburger" id="hamburger" aria-label="Menu">&#9776;</button>
<div class="sidebar-overlay" id="sidebar-overlay"></div>

<aside class="sidebar" id="sidebar">
  <h3 id="toc-title">Contents</h3>
  <nav id="toc-nav"></nav>
</aside>

<div class="main-wrap">

<div class="toggle-bar">
  <button class="toggle-btn active" id="btn-zh">中文</button>
  <button class="toggle-btn" id="btn-en">English</button>
</div>

<div class="lang-content active" id="content-zh">
{html_zh}
</div>

<div class="lang-content" id="content-en">
{html_en}
</div>

</div>

{JS}

</body>
</html>"""

    os.makedirs(os.path.dirname(output_html_path) or ".", exist_ok=True)
    with open(output_html_path, "w", encoding="utf-8") as f:
        f.write(full)

    return output_html_path, len(full)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 build_html.py <input_md> [--output <html_path>]")
        sys.exit(1)

    inp = sys.argv[1]
    out = None
    for i, a in enumerate(sys.argv):
        if a == "--output" and i + 1 < len(sys.argv):
            out = sys.argv[i + 1]

    path, size = build(inp, out)
    print(f"OK  {path}  ({size:,} bytes)")
