#!/usr/bin/env python3
"""
Local server for Influencer Discovery — bridges browser search to Claude Code.
Start: python3 server.py  →  open http://localhost:8765

POST /api/search  → spawns claude -p with --dangerously-skip-permissions
GET  /api/status  → polls for task completion (new report detected via reports.json)
"""

import http.server, json, os, re, subprocess, sys, threading, time, uuid
from pathlib import Path

PORT = 8765
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
MEMORY_DIR = os.path.join(PROJECT_ROOT, "memory", "influencer", "influencer-discovery")
MANIFEST_PATH = os.path.join(MEMORY_DIR, "reports.json")
CLAUDE_BIN = os.path.expanduser("~/.local/bin/claude")

active_tasks = {}
task_lock = threading.Lock()


def build_prompt(data):
    niche = data.get("niche", "").strip()
    platform = data.get("platform", "").strip()
    followers = data.get("followers", "").strip()
    engagement = data.get("engagement", "").strip()
    location = data.get("location", "").strip()
    content = data.get("content", "").strip()
    extra = data.get("extra", "").strip()

    parts = []
    if followers: parts.append(f"粉丝量在{followers}之间")
    if engagement: parts.append(f"互动率大于{engagement}")
    if location: parts.append(f"地区在{location}")
    if content: parts.append(f"拍摄过{content}内容视频")

    cn = f"在{platform}平台，找{'，'.join(parts)}的红人"
    if extra: cn += f"，{extra}"
    cn += "。"

    en_parts = []
    if followers: en_parts.append(f"{followers} followers")
    if engagement: en_parts.append(f"engagement above {engagement}")
    if location: en_parts.append(f"based in {location}")
    if content: en_parts.append(f"who have posted {content} content")

    en = f"Find influencers in {niche} on {platform}"
    if en_parts: en += f" with {', '.join(en_parts)}"
    if extra: en += f", {extra}"
    en += "."

    today = time.strftime("%Y-%m-%d")
    slug = niche.replace(" ", "-").replace("/", "-")[:40]
    md_path = f"memory/influencer/influencer-discovery/{today}-{slug}.md"

    full = f"{cn}\n\n{en}"
    full += f"\n\nAfter your analysis, save the complete report as Markdown to {md_path}"
    full += " with <!-- LANG:ZH --> between Chinese and English sections."
    full += f" Then run: python3 memory/influencer/influencer-discovery/build_html.py {md_path}"
    return full


def process_task(task_id, prompt):
    log_path = os.path.join(MEMORY_DIR, f"task-{task_id}.log")
    try:
        with open(log_path, "w", buffering=1) as log:
            log.write(f"=== Task {task_id} ===\nPrompt: {prompt}\n\nStarting Claude Code...\n")
            log.flush()

            proc = subprocess.Popen(
                [CLAUDE_BIN, "-p", prompt, "--dangerously-skip-permissions"],
                cwd=PROJECT_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            with task_lock:
                if task_id in active_tasks:
                    active_tasks[task_id]["process"] = proc

            for line in proc.stdout:
                log.write(line)
                log.flush()

            proc.wait()
            log.write(f"\n=== Exit code: {proc.returncode} ===\n")

            with task_lock:
                if task_id in active_tasks:
                    active_tasks[task_id]["completed"] = True
                    active_tasks[task_id]["exit_code"] = proc.returncode

    except FileNotFoundError:
        with task_lock:
            if task_id in active_tasks:
                active_tasks[task_id]["completed"] = True
                active_tasks[task_id]["error"] = "Claude CLI not found at " + CLAUDE_BIN
    except Exception as e:
        with task_lock:
            if task_id in active_tasks:
                active_tasks[task_id]["completed"] = True
                active_tasks[task_id]["error"] = str(e)


def get_latest_report_after(timestamp):
    if not os.path.exists(MANIFEST_PATH):
        return None
    try:
        with open(MANIFEST_PATH, "r") as f:
            reports = json.load(f)
    except Exception:
        return None

    # timestamp is float (time.time())
    ts_str = time.strftime("%Y-%m-%d", time.localtime(timestamp))
    for r in reports:
        if r.get("date", "") >= ts_str:
            return r
    return None


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=PROJECT_ROOT, **kwargs)

    def _json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/api/status":
            qs = self.path.split("?")[1] if "?" in self.path else ""
            params = dict(p.split("=") for p in qs.split("&") if "=" in p)
            task_id = params.get("task")
            with task_lock:
                task = active_tasks.get(task_id)
            if not task:
                return self._json({"error": "task not found"}, 404)
            if task.get("error"):
                return self._json({"status": "error", "message": task["error"]})
            if task.get("completed"):
                latest = get_latest_report_after(task.get("started", 0))
                if latest:
                    return self._json({"status": "done", "report": latest})
                return self._json({"status": "done", "message": "No new report detected."})
            elapsed = int(time.time() - task.get("started", time.time()))
            return self._json({"status": "processing", "elapsed_seconds": elapsed})
        elif path == "/api/health":
            return self._json({"ok": True, "claude_bin": os.path.exists(CLAUDE_BIN)})
        else:
            super().do_GET()

    def do_POST(self):
        if self.path == "/api/search":
            length = int(self.headers.get("Content-Length", 0))
            try:
                data = json.loads(self.rfile.read(length))
            except Exception:
                return self._json({"error": "Invalid JSON"}, 400)
            if not data.get("niche"):
                return self._json({"error": "请填写搜索领域"}, 400)

            prompt = build_prompt(data)
            task_id = uuid.uuid4().hex[:12]
            with task_lock:
                active_tasks[task_id] = {"started": time.time(), "prompt": prompt, "completed": False}

            threading.Thread(target=process_task, args=(task_id, prompt), daemon=True).start()
            return self._json({"task_id": task_id, "status": "processing"})
        else:
            return self._json({"error": "not found"}, 404)


if __name__ == "__main__":
    os.makedirs(MEMORY_DIR, exist_ok=True)
    if not os.path.exists(CLAUDE_BIN):
        print(f"WARN: Claude CLI not found at {CLAUDE_BIN}")
    else:
        r = subprocess.run([CLAUDE_BIN, "--version"], capture_output=True, text=True)
        print(f"Claude CLI: {r.stdout.strip()}")

    server = http.server.HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Server: http://localhost:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        server.shutdown()
