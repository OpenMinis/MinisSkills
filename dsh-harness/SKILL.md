---
name: dsh-harness
description: >
  Install, run, inspect and troubleshoot DeepSeek Harness (dsh web) inside the Minis Linux sandbox,
  and point its workspace at a phone directory so the harness can read and write real files.
  Handles the four musl/aarch64 failures (glibc-prebuilt node-pty, --expose-internals rejected in
  NODE_OPTIONS, DSH_PERMISSION_MODE being bootstrap-only, no usable sandbox backend), the
  /opt/dsh-harness pinning step, and workspace registration in ~/.dsh/storages/workspace.json.
  Trigger when the user says "打开 dsh", "启动 harness", "装 deepseek harness", "dsh 起不来",
  "dsh 白屏", "端口 3080 没反应", "把手机目录挂给 dsh", "让 harness 读写手机文件",
  or when the user wants a second agent harness running on-device next to Minis.
version: 1.0.0
compatibility: Alpine Linux sandbox (musl/aarch64). Needs apk, npm/node >= 20, ~800 MB disk.
---

# DeepSeek Harness on the Minis sandbox

Two layers, one contract:

| | Minis (local layer) | dsh (execution layer) |
|---|---|---|
| Owns | mounting phone storage, the sandbox, device tools, permissions, app lifecycle | agent loop, task decomposition, tool calls, long-task context |
| Guarantees | the file is real, the device is real | the task is actually finished |

**The only contract between them is a mounted directory.** Never point the workspace at `/root` —
writes there hit `Operation not permitted` under PRoot, and the phone can't see the files anyway.

Reference implementation (install script, wrappers, troubleshooting manual):
https://github.com/maple564/dsh-on-android

---

## 1. Check before you install

```bash
node -v; npm -v
ldd --version 2>&1 | head -1            # musl expected on Alpine
dsh --version 2>/dev/null || echo "dsh not installed"
pgrep -f 'dsh/lib/bin.js' >/dev/null && echo "already running" || echo "not running"
curl -s -o /dev/null -w "HTTP %{http_code}\n" http://127.0.0.1:3080/
```

If it is already installed and `dsh-go --status` works, do **not** reinstall — go to step 3.

## 2. Install

```bash
apk add --no-cache build-base linux-headers python3 git curl
cd /tmp && rm -rf dsh-on-android
git clone --depth 1 https://github.com/maple564/dsh-on-android.git
sh dsh-on-android/install.sh            # deps -> install -> rebuild node-pty -> pin /opt/dsh-harness -> wrappers
dsh --version
```

The script pins the install to `/opt/dsh-harness` because the npx cache gets evicted. It compiles
node-pty from source, which takes 3–10 minutes on a phone CPU — do not kill it early.

## 3. Register a phone directory as the workspace

```bash
mkdir -p /var/minis/mounts/Documents/dsh-workspace
cp ~/.dsh/storages/workspace.json ~/.dsh/storages/workspace.json.bak
python3 - <<'PY'
import json, uuid, datetime
p = json.load(open('/root/.dsh/storages/workspace.json'))
new = "/var/minis/mounts/Documents/dsh-workspace"
for ws in p["tables"]["workspaces"].values():
    if ws.get("path") == new:
        raise SystemExit("already registered")
now = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", ".000Z")
wid = "ws-" + uuid.uuid4().hex[:12]
p["tables"]["workspaces"][wid] = {"path": new, "title": "dsh-workspace",
                                  "sessionIds": [], "createdAt": now, "updatedAt": now}
p["global"]["workspaceIds"].append(wid)
json.dump(p, open('/root/.dsh/storages/workspace.json','w'), indent=2, ensure_ascii=False)
print("registered", wid)
PY
pkill -f 'dsh/lib/bin.js'; sleep 2; dsh-go
```

Verify with a real file, not a claim:

```bash
echo ok > /var/minis/mounts/Documents/dsh-workspace/hello.txt
ls -l /var/minis/mounts/Documents/dsh-workspace/hello.txt
```

Then tell the user to open `http://127.0.0.1:3080` in **Chrome** (in-app WebViews may render blank)
and pick `dsh-workspace` in the sidebar.

## 4. Troubleshooting — match the error, not the guess

| Symptom | Real cause | Fix |
|---|---|---|
| `Error loading shared library ld-linux-aarch64.so.1` | node-pty is a glibc prebuild | `cd /opt/dsh-harness/node_modules/node-pty && npx --yes node-gyp rebuild` |
| `Cannot find module '.../node_modules/...'` | dir tree flattened by tar copy | must be `/opt/dsh-harness/node_modules/@deepseek-ai/dsh/lib/bin.js` |
| `--expose-internals is required for HMR` | flag rejected inside `NODE_OPTIONS` | wrapper passes it on the node command line |
| `.env sets DSH_PERMISSION_MODE ... only the launching environment may set` | bootstrap variable | `export` it in the wrapper; keep `.env` for `DEEPSEEK_API_KEY` only |
| `no sandbox backend is usable` | no workspace-write backend in a container | `DSH_PERMISSION_MODE=danger-full-access` |
| Web UI blank | WebView lacks Canvas/WebGL, or server down | check `curl ...:3080`; open in Chrome |
| Writes fail `Operation not permitted` | PRoot view mismatch | move workspace to a mounted path |

## 5. Rules that matter

- **Never expose port 3080 to the public network.** Full-access mode means shell without approval.
- **Process lifetime is tied to Minis.** Killing the app kills the harness; split long tasks.
- **One contract only.** If the user asks for phone files, fix the workspace mount — do not
  invent sync jobs, cloud uploads or copy dance.
- Report absolute paths when you deliver files, so the user can find them in the phone's file manager.
