#!/bin/sh
# github-sync-helper: reusable GitHub sync workflows for Minis
# Requirements: git, python3, env GITHUB_TOKEN
set -e

err() { printf '%s\n' "$*" >&2; }
need_cmd() { command -v "$1" >/dev/null 2>&1 || { err "missing command: $1"; exit 1; }; }
need_env() { name="$1"; eval "val=\${$name-}"; [ -n "$val" ] || { err "missing env: $name"; exit 1; }; }
repo_root() { git rev-parse --show-toplevel 2>/dev/null; }

# Print and require --yes for dangerous commands
need_yes() {
  for a in "$@"; do
    [ "$a" = "--yes" ] && return 0
  done
  err "dangerous operation: re-run with --yes to confirm"
  exit 2
}

# Try infer owner/repo from current git remote (origin)
# Supports https://github.com/owner/repo(.git) and git@github.com:owner/repo(.git)
# Echoes "owner/repo" or empty.
infer_repo() {
  u="$(git remote get-url origin 2>/dev/null || true)"
  [ -n "$u" ] || { echo ""; return 0; }
  case "$u" in
    https://github.com/*)
      s="${u#https://github.com/}";;
    git@github.com:*)
      s="${u#git@github.com:}";;
    *)
      echo ""; return 0;;
  esac
  s="${s%.git}"
  # basic validation
  case "$s" in
    *"/"*) echo "$s";;
    *) echo "";;
  esac
}

# Minimal GitHub API wrapper. Prints JSON response to stdout. Exits non-zero on HTTP error.
gh_api() {
  need_env GITHUB_TOKEN
  method="$1"; url="$2"; body_json="${3-}"
  python3 -c 'import os,sys,json,urllib.request,urllib.error
method=os.environ["M"]; url=os.environ["U"]; tok=os.environ["GITHUB_TOKEN"]; body=os.environ.get("B","")
data=None
if body:
  data=body.encode("utf-8")
req=urllib.request.Request(url,data=data,method=method)
req.add_header("Authorization","Bearer "+tok)
req.add_header("Accept","application/vnd.github+json")
req.add_header("User-Agent","minis")
if data is not None:
  req.add_header("Content-Type","application/json")
try:
  with urllib.request.urlopen(req,timeout=30) as r:
    raw=r.read().decode("utf-8","ignore")
    print(raw)
except urllib.error.HTTPError as e:
  raw=e.read().decode("utf-8","ignore")
  sys.stderr.write(f"HTTP {e.code} {url}\n")
  sys.stderr.write(raw[:800]+"\n")
  sys.exit(1)
' M="$method" U="$url" B="$body_json"
}

ensure_git_identity() {
  [ -n "$(git config user.name || true)" ] || git config user.name "mowenyun"
  [ -n "$(git config user.email || true)" ] || git config user.email "mowenyun@users.noreply.github.com"
}

ensure_askpass() {
  need_env GITHUB_TOKEN
  ASKPASS="/var/minis/workspace/.git_askpass.sh"
  if [ ! -f "$ASKPASS" ]; then
    cat > "$ASKPASS" <<'EOF'
#!/bin/sh
case "$1" in
  *Username*) echo "x-access-token" ;;
  *Password*) echo "$GITHUB_TOKEN" ;;
  *) echo "" ;;
esac
EOF
    chmod +x "$ASKPASS"
  fi
  export GIT_ASKPASS="$ASKPASS"
  export GIT_TERMINAL_PROMPT=0
}

usage() {
  cat <<'EOF'
Usage:
  sh gh_sync.sh init
  sh gh_sync.sh clone --url <url> [--dir <path>]
  sh gh_sync.sh remotes
  sh gh_sync.sh add-remote --name <n> --url <url>
  sh gh_sync.sh set-remote-url --name <n> --url <url>
  sh gh_sync.sh remove-remote --name <n>
  sh gh_sync.sh add-upstream --upstream <owner/repo>
  sh gh_sync.sh status
  sh gh_sync.sh diff [--staged]
  sh gh_sync.sh log [--n <k>]
  sh gh_sync.sh branches
  sh gh_sync.sh create-branch --name <b> [--from <ref>]
  sh gh_sync.sh checkout --name <b>
  sh gh_sync.sh add [--path <p>]
  sh gh_sync.sh commit --message <m>
  sh gh_sync.sh fetch [--remote <n>]
  sh gh_sync.sh pull [--remote <n>] [--branch <b>]
  sh gh_sync.sh push [--remote <n>] [--branch <b>]
  sh gh_sync.sh stash [--save <msg> | --pop | --apply | --list]
  sh gh_sync.sh tag --name <tag> [--message <msg>]
  sh gh_sync.sh submodule [--add <url> <path> | --update | --status]
  sh gh_sync.sh delete-branches --keep <branch>
  sh gh_sync.sh empty-dir --dir <path>
  sh gh_sync.sh restore-dir --src <path> --dst <path>
  sh gh_sync.sh push-main
  sh gh_sync.sh pr --upstream <owner/repo> --head <owner:branch> --base <branch> --title <t> --body <b>

  # PR management
  sh gh_sync.sh gh-pr-list --repo <owner/repo> [--state open|closed|all]
  sh gh_sync.sh gh-pr-close --repo <owner/repo> --number <n>
  sh gh_sync.sh gh-pr-merge --repo <owner/repo> --number <n> [--method merge|squash|rebase]

  # GitHub platform APIs
  sh gh_sync.sh gh-issues-list --repo <owner/repo> [--state open|closed|all]
  sh gh_sync.sh gh-issue-create --repo <owner/repo> --title <t> [--body <b>]
  sh gh_sync.sh gh-issue-close --repo <owner/repo> --number <n>
  sh gh_sync.sh gh-labels-list --repo <owner/repo>
  sh gh_sync.sh gh-label-create --repo <owner/repo> --name <n> [--color <rrggbb>] [--description <d>]
  sh gh_sync.sh gh-milestones-list --repo <owner/repo> [--state open|closed|all]
  sh gh_sync.sh gh-milestone-create --repo <owner/repo> --title <t> [--description <d>] [--due <YYYY-MM-DD>]
  sh gh_sync.sh gh-releases-list --repo <owner/repo>
  sh gh_sync.sh gh-release-create --repo <owner/repo> --tag <vX.Y.Z> --name <n> [--body <b>] [--draft true|false] [--prerelease true|false]
  sh gh_sync.sh gh-actions-list --repo <owner/repo>
  sh gh_sync.sh gh-actions-runs --repo <owner/repo> [--status queued|in_progress|completed] [--branch <b>]
  sh gh_sync.sh gh-actions-dispatch --repo <owner/repo> --workflow <id_or_file> [--ref <branch>] [--inputs <json>]
EOF
}

cmd="$1"; shift || true
need_cmd git
need_cmd python3
ROOT="$(repo_root)"; [ -n "$ROOT" ] || { err "not inside a git repo"; exit 1; }
cd "$ROOT"

SUMMARY=""
add_row() { SUMMARY="$SUMMARY
| $1 | $2 | $3 | $4 |"; }
print_summary() {
  printf '%s\n' "| 序号 | 动作 | 结果 | 备注 |"
  printf '%s\n' "|---:|---|---|---|"
  printf '%s\n' "$SUMMARY" | sed '1{/^$/d;}'
}

case "$cmd" in
  init)
    git init >/dev/null 2>&1 || true
    add_row 1 init OK initialized
    ;;

  clone)
    url=""; dir=""
    while [ $# -gt 0 ]; do
      case "$1" in
        --url) url="$2"; shift 2;;
        --dir) dir="$2"; shift 2;;
        *) break;;
      esac
    done
    [ -n "$url" ] || { err "--url required"; usage; exit 1; }
    if [ -n "$dir" ]; then
      git clone "$url" "$dir" >/dev/null
      add_row 1 clone OK "$url -> $dir"
    else
      git clone "$url" >/dev/null
      add_row 1 clone OK "$url"
    fi
    ;;

  remotes)
    out="$(git remote -v 2>/dev/null || true)"
    add_row 1 remotes OK "$(printf '%s' "$out" | tr '\n' '; ' | sed 's/; $//')"
    ;;

  add-remote)
    name=""; url=""
    while [ $# -gt 0 ]; do
      case "$1" in
        --name) name="$2"; shift 2;;
        --url) url="$2"; shift 2;;
        *) break;;
      esac
    done
    [ -n "$name" ] && [ -n "$url" ] || { err "--name and --url required"; usage; exit 1; }
    git remote add "$name" "$url"
    add_row 1 add-remote OK "$name=$url"
    ;;

  set-remote-url)
    name=""; url=""
    while [ $# -gt 0 ]; do
      case "$1" in
        --name) name="$2"; shift 2;;
        --url) url="$2"; shift 2;;
        *) break;;
      esac
    done
    [ -n "$name" ] && [ -n "$url" ] || { err "--name and --url required"; usage; exit 1; }
    git remote set-url "$name" "$url"
    add_row 1 set-remote-url OK "$name=$url"
    ;;

  remove-remote)
    name=""
    while [ $# -gt 0 ]; do
      case "$1" in
        --name) name="$2"; shift 2;;
        *) break;;
      esac
    done
    [ -n "$name" ] || { err "--name required"; usage; exit 1; }
    git remote remove "$name"
    add_row 1 remove-remote OK "$name"
    ;;

  add-upstream)
    upstream=""
    while [ $# -gt 0 ]; do
      case "$1" in
        --upstream) upstream="$2"; shift 2;;
        *) break;;
      esac
    done
    [ -n "$upstream" ] || { err "--upstream required"; usage; exit 1; }
    if git remote get-url upstream >/dev/null 2>&1; then
      add_row 1 add-upstream SKIP "upstream exists"
    else
      git remote add upstream "https://github.com/$upstream.git"
      add_row 1 add-upstream OK "$upstream"
    fi
    ;;

  status)
    s="$(git status --porcelain 2>/dev/null || true)"
    if [ -n "$s" ]; then add_row 1 status DIRTY "$(printf '%s' "$s" | tr '\n' '; ' | sed 's/; $//')";
    else add_row 1 status CLEAN "no changes"; fi
    ;;

  diff)
    staged=0
    [ "${1-}" = "--staged" ] && staged=1
    if [ "$staged" -eq 1 ]; then d="$(git diff --staged --name-status)"; else d="$(git diff --name-status)"; fi
    add_row 1 diff OK "$(printf '%s' "$d" | tr '\n' '; ' | sed 's/; $//')"
    ;;

  log)
    n=10
    [ "${1-}" = "--n" ] && { n="$2"; }
    l="$(git log -n "$n" --oneline 2>/dev/null || true)"
    add_row 1 log OK "$(printf '%s' "$l" | tr '\n' '; ' | sed 's/; $//')"
    ;;

  branches)
    l="$(git branch --format='%(refname:short)' | tr '\n' ', ' | sed 's/, $//')"
    r="$(git branch -r --format='%(refname:short)' | tr '\n' ', ' | sed 's/, $//')"
    add_row 1 local OK "$l"; add_row 2 remote OK "$r"
    ;;

  create-branch)
    name=""; from=""
    while [ $# -gt 0 ]; do case "$1" in --name) name="$2"; shift 2;; --from) from="$2"; shift 2;; *) break;; esac; done
    [ -n "$name" ] || { err "--name required"; usage; exit 1; }
    [ -n "$from" ] && git checkout -b "$name" "$from" >/dev/null || git checkout -b "$name" >/dev/null
    add_row 1 create-branch OK "$name"
    ;;

  checkout)
    [ "${1-}" = "--name" ] && name="$2" || name="${1-}"
    [ -n "$name" ] || { err "--name required"; usage; exit 1; }
    git checkout "$name" >/dev/null
    add_row 1 checkout OK "$name"
    ;;

  add)
    path="-A"; [ "${1-}" = "--path" ] && path="$2"
    git add "$path"; add_row 1 add OK "$path"
    ;;

  commit)
    msg=""; [ "${1-}" = "--message" ] && msg="$2"
    [ -n "$msg" ] || { err "--message required"; usage; exit 1; }
    ensure_git_identity
    git commit -m "$msg" >/dev/null
    add_row 1 commit OK "$msg"
    ;;

  fetch)
    remote="origin"; [ "${1-}" = "--remote" ] && remote="$2"
    git fetch "$remote" >/dev/null; add_row 1 fetch OK "$remote"
    ;;

  pull)
    remote="origin"; br=""
    while [ $# -gt 0 ]; do case "$1" in --remote) remote="$2"; shift 2;; --branch) br="$2"; shift 2;; *) break;; esac; done
    [ -n "$br" ] && git pull "$remote" "$br" >/dev/null || git pull >/dev/null
    add_row 1 pull OK "${remote}${br:+/$br}"
    ;;

  push)
    remote="origin"; br=""
    while [ $# -gt 0 ]; do case "$1" in --remote) remote="$2"; shift 2;; --branch) br="$2"; shift 2;; *) break;; esac; done
    ensure_askpass
    [ -n "$br" ] && git push "$remote" "$br" >/dev/null || git push >/dev/null
    add_row 1 push OK "${remote}${br:+/$br}"
    ;;

  stash)
    case "${1-}" in
      --save) git stash push -m "${2:-wip}" >/dev/null; add_row 1 stash OK saved;;
      --pop) git stash pop >/dev/null || true; add_row 1 stash OK popped;;
      --apply) git stash apply >/dev/null || true; add_row 1 stash OK applied;;
      *) l="$(git stash list || true)"; add_row 1 stash OK "$(printf '%s' "$l" | tr '\n' '; ' | sed 's/; $//')";;
    esac
    ;;

  tag)
    name=""; msg=""
    while [ $# -gt 0 ]; do case "$1" in --name) name="$2"; shift 2;; --message) msg="$2"; shift 2;; *) break;; esac; done
    [ -n "$name" ] || { err "--name required"; usage; exit 1; }
    [ -n "$msg" ] && git tag -a "$name" -m "$msg" || git tag "$name"
    add_row 1 tag OK "$name"
    ;;

  submodule)
    case "${1-}" in
      --add) git submodule add "$2" "$3" >/dev/null; add_row 1 submodule OK "add $3";;
      --update) git submodule update --init --recursive >/dev/null; add_row 1 submodule OK update;;
      *) s="$(git submodule status 2>/dev/null || true)"; add_row 1 submodule OK "$(printf '%s' "$s" | tr '\n' '; ' | sed 's/; $//')";;
    esac
    ;;

  delete-branches)
    keep="main"; yes=""
    while [ $# -gt 0 ]; do
      case "$1" in
        --keep) keep="$2"; shift 2;;
        --yes) yes="--yes"; shift 1;;
        *) break;;
      esac
    done
    need_yes "$yes"
    ensure_askpass
    i=1
    for b in $(git branch --format='%(refname:short)'); do [ "$b" = "$keep" ] && continue; git branch -D "$b" >/dev/null 2>&1 || true; add_row "$i" "delete local branch" OK "$b"; i=$((i+1)); done
    for rb in $(git branch -r --format='%(refname:short)' | grep '^origin/' | sed 's#^origin/##'); do [ "$rb" = "$keep" ] && continue; git push origin --delete "$rb" >/dev/null 2>&1 || true; add_row "$i" "delete remote branch" OK "origin/$rb"; i=$((i+1)); done
    ;;

  empty-dir)
    dir=""; yes=""
    while [ $# -gt 0 ]; do
      case "$1" in
        --dir) dir="$2"; shift 2;;
        --yes) yes="--yes"; shift 1;;
        *) break;;
      esac
    done
    [ -n "$dir" ] || { err "--dir required"; usage; exit 1; }
    need_yes "$yes"
    ensure_git_identity
    mkdir -p "$dir"
    git rm -r --ignore-unmatch "$dir"/* "$dir"/.[!.]* "$dir"/..?* >/dev/null 2>&1 || true
    mkdir -p "$dir"; : > "$dir/.gitkeep"; git add "$dir/.gitkeep"
    add_row 1 empty-dir OK "$dir (kept via .gitkeep)"
    ;;

  restore-dir)
    src=""; dst=""; yes=""
    while [ $# -gt 0 ]; do
      case "$1" in
        --src) src="$2"; shift 2;;
        --dst) dst="$2"; shift 2;;
        --yes) yes="--yes"; shift 1;;
        *) break;;
      esac
    done
    [ -n "$src" ] && [ -n "$dst" ] || { err "--src and --dst required"; usage; exit 1; }
    need_yes "$yes"
    [ -d "$src" ] || { err "src not found: $src"; exit 1; }
    ensure_git_identity
    rm -f "$dst/.gitkeep" 2>/dev/null || true
    git rm -r --ignore-unmatch "$dst"/* "$dst"/.[!.]* "$dst"/..?* >/dev/null 2>&1 || true
    mkdir -p "$dst"; cp -a "$src"/. "$dst"/
    find "$dst"/scripts -type f -name '*.sh' -exec chmod +x {} \; 2>/dev/null || true
    git add -A "$dst"
    add_row 1 restore-dir OK "$src -> $dst"
    ;;

  push-main)
    yes=""
    while [ $# -gt 0 ]; do
      case "$1" in
        --yes) yes="--yes"; shift 1;;
        *) break;;
      esac
    done
    need_yes "$yes"
    ensure_askpass
    ensure_git_identity
    git checkout main >/dev/null 2>&1 || true
    git pull --ff-only origin main >/dev/null 2>&1 || true
    git push origin main >/dev/null
    add_row 1 push-main OK pushed
    ;;

  pr)
    upstream=""; head=""; base="main"; title=""; body=""
    while [ $# -gt 0 ]; do case "$1" in --upstream) upstream="$2"; shift 2;; --head) head="$2"; shift 2;; --base) base="$2"; shift 2;; --title) title="$2"; shift 2;; --body) body="$2"; shift 2;; *) break;; esac; done
    [ -n "$upstream" ] && [ -n "$head" ] && [ -n "$title" ] || { err "--upstream --head --title required"; usage; exit 1; }
    need_env GITHUB_TOKEN
    export UP="$upstream" HEAD="$head" BASE="$base" TITLE="$title" BODY="$body"
    out="$(python3 -c 'import os,json,urllib.request,urllib.error; tok=os.environ["GITHUB_TOKEN"]; owner,repo=os.environ["UP"].split("/",1); payload={"title":os.environ["TITLE"],"head":os.environ["HEAD"],"base":os.environ.get("BASE","main"),"body":os.environ.get("BODY","")}; data=json.dumps(payload).encode("utf-8"); req=urllib.request.Request(f"https://api.github.com/repos/{owner}/{repo}/pulls",data=data,method="POST"); req.add_header("Authorization","Bearer "+tok); req.add_header("Accept","application/vnd.github+json"); req.add_header("User-Agent","minis"); req.add_header("Content-Type","application/json");
try:
  resp=json.load(urllib.request.urlopen(req,timeout=30)); print(resp.get("html_url",""))
except urllib.error.HTTPError as e:
  err=e.read().decode("utf-8","ignore"); print("HTTP %s"%e.code+" "+err[:200])' 2>/dev/null)" || true
    if printf '%s' "$out" | grep -q '^https://'; then
      add_row 1 pr OK "$out"
    else
      add_row 1 pr FAIL "$out"
      print_summary
      exit 1
    fi
    ;;

  gh-issues-list)
    repo=""; state="open"
    while [ $# -gt 0 ]; do case "$1" in --repo) repo="$2"; shift 2;; --state) state="$2"; shift 2;; *) break;; esac; done
    [ -n "$repo" ] || repo="$(infer_repo)"
    [ -n "$repo" ] || { err "--repo required (or set origin remote)"; exit 1; }
    need_env GITHUB_TOKEN
    export REPO="$repo" STATE="$state"
    out="$(python3 -c 'import os,json,urllib.request; tok=os.environ["GITHUB_TOKEN"]; owner,repo=os.environ["REPO"].split("/",1); state=os.environ.get("STATE","open"); url=f"https://api.github.com/repos/{owner}/{repo}/issues?state={state}&per_page=20"; req=urllib.request.Request(url,headers={"Authorization":"Bearer "+tok,"Accept":"application/vnd.github+json","User-Agent":"minis"}); data=json.load(urllib.request.urlopen(req,timeout=30)); lines=[]
for it in data:
  if "pull_request" in it: continue
  lines.append(f"#{it['number']} {it['title']}")
print("; ".join(lines))' 2>/dev/null)" || true
    add_row 1 gh-issues-list OK "$out"
    ;;

  gh-issue-create)
    repo=""; title=""; body=""
    while [ $# -gt 0 ]; do case "$1" in --repo) repo="$2"; shift 2;; --title) title="$2"; shift 2;; --body) body="$2"; shift 2;; *) break;; esac; done
    [ -n "$repo" ] || repo="$(infer_repo)"
    [ -n "$repo" ] && [ -n "$title" ] || { err "--repo (or origin remote) and --title required"; exit 1; }
    need_env GITHUB_TOKEN
    export REPO="$repo" TITLE="$title" BODY="$body"
    out="$(python3 -c 'import os,json,urllib.request,urllib.error; tok=os.environ["GITHUB_TOKEN"]; owner,repo=os.environ["REPO"].split("/",1); payload={"title":os.environ["TITLE"],"body":os.environ.get("BODY","")}; data=json.dumps(payload).encode("utf-8"); req=urllib.request.Request(f"https://api.github.com/repos/{owner}/{repo}/issues",data=data,method="POST"); req.add_header("Authorization","Bearer "+tok); req.add_header("Accept","application/vnd.github+json"); req.add_header("User-Agent","minis"); req.add_header("Content-Type","application/json");
try:
  resp=json.load(urllib.request.urlopen(req,timeout=30)); print(resp.get("html_url",""))
except urllib.error.HTTPError as e:
  err=e.read().decode("utf-8","ignore"); print("HTTP %s"%e.code+" "+err[:120])' 2>/dev/null)" || true
    add_row 1 gh-issue-create OK "$out"
    ;;

  gh-issue-close)
    repo=""; num=""
    while [ $# -gt 0 ]; do case "$1" in --repo) repo="$2"; shift 2;; --number) num="$2"; shift 2;; *) break;; esac; done
    [ -n "$repo" ] || repo="$(infer_repo)"
    [ -n "$repo" ] && [ -n "$num" ] || { err "--repo (or origin remote) and --number required"; exit 1; }
    need_env GITHUB_TOKEN
    export REPO="$repo" NUM="$num"
    out="$(python3 -c 'import os,json,urllib.request; tok=os.environ["GITHUB_TOKEN"]; owner,repo=os.environ["REPO"].split("/",1); num=os.environ["NUM"]; payload={"state":"closed"}; data=json.dumps(payload).encode("utf-8"); req=urllib.request.Request(f"https://api.github.com/repos/{owner}/{repo}/issues/{num}",data=data,method="PATCH"); req.add_header("Authorization","Bearer "+tok); req.add_header("Accept","application/vnd.github+json"); req.add_header("User-Agent","minis"); req.add_header("Content-Type","application/json"); resp=json.load(urllib.request.urlopen(req,timeout=30)); print(resp.get("state",""))' 2>/dev/null)" || true
    add_row 1 gh-issue-close OK "$out"
    ;;

  gh-labels-list)
    repo=""; [ "${1-}" = "--repo" ] && repo="$2"
    [ -n "$repo" ] || repo="$(infer_repo)"
    [ -n "$repo" ] || { err "--repo required (or set origin remote)"; exit 1; }
    need_env GITHUB_TOKEN
    export REPO="$repo"
    out="$(python3 -c 'import os,json,urllib.request; tok=os.environ["GITHUB_TOKEN"]; owner,repo=os.environ["REPO"].split("/",1); url=f"https://api.github.com/repos/{owner}/{repo}/labels?per_page=50"; req=urllib.request.Request(url,headers={"Authorization":"Bearer "+tok,"Accept":"application/vnd.github+json","User-Agent":"minis"}); data=json.load(urllib.request.urlopen(req,timeout=30)); print("; ".join([it.get("name","") for it in data]))' 2>/dev/null)" || true
    add_row 1 gh-labels-list OK "$out"
    ;;

  gh-label-create)
    repo=""; name=""; color=""; desc=""
    while [ $# -gt 0 ]; do case "$1" in --repo) repo="$2"; shift 2;; --name) name="$2"; shift 2;; --color) color="$2"; shift 2;; --description) desc="$2"; shift 2;; *) break;; esac; done
    [ -n "$repo" ] || repo="$(infer_repo)"
    [ -n "$repo" ] && [ -n "$name" ] || { err "--repo (or origin remote) and --name required"; exit 1; }
    need_env GITHUB_TOKEN
    export REPO="$repo" NAME="$name" COLOR="$color" DESC="$desc"
    out="$(python3 -c 'import os,json,urllib.request; tok=os.environ["GITHUB_TOKEN"]; owner,repo=os.environ["REPO"].split("/",1); payload={"name":os.environ["NAME"],"color":(os.environ.get("COLOR") or "ededed"),"description":os.environ.get("DESC","")}; data=json.dumps(payload).encode("utf-8"); req=urllib.request.Request(f"https://api.github.com/repos/{owner}/{repo}/labels",data=data,method="POST"); req.add_header("Authorization","Bearer "+tok); req.add_header("Accept","application/vnd.github+json"); req.add_header("User-Agent","minis"); req.add_header("Content-Type","application/json"); resp=json.load(urllib.request.urlopen(req,timeout=30)); print(resp.get("name",""))' 2>/dev/null)" || true
    add_row 1 gh-label-create OK "$out"
    ;;

  gh-milestones-list)
    repo=""; state="open"
    while [ $# -gt 0 ]; do case "$1" in --repo) repo="$2"; shift 2;; --state) state="$2"; shift 2;; *) break;; esac; done
    [ -n "$repo" ] || repo="$(infer_repo)"
    [ -n "$repo" ] || { err "--repo required (or set origin remote)"; exit 1; }
    need_env GITHUB_TOKEN
    export REPO="$repo" STATE="$state"
    out="$(python3 -c 'import os,json,urllib.request; tok=os.environ["GITHUB_TOKEN"]; owner,repo=os.environ["REPO"].split("/",1); state=os.environ.get("STATE","open"); url=f"https://api.github.com/repos/{owner}/{repo}/milestones?state={state}&per_page=30"; req=urllib.request.Request(url,headers={"Authorization":"Bearer "+tok,"Accept":"application/vnd.github+json","User-Agent":"minis"}); data=json.load(urllib.request.urlopen(req,timeout=30)); print("; ".join([f"#{it['number']} {it['title']}" for it in data]))' 2>/dev/null)" || true
    add_row 1 gh-milestones-list OK "$out"
    ;;

  gh-milestone-create)
    repo=""; title=""; desc=""; due=""
    while [ $# -gt 0 ]; do case "$1" in --repo) repo="$2"; shift 2;; --title) title="$2"; shift 2;; --description) desc="$2"; shift 2;; --due) due="$2"; shift 2;; *) break;; esac; done
    [ -n "$repo" ] || repo="$(infer_repo)"
    [ -n "$repo" ] && [ -n "$title" ] || { err "--repo (or origin remote) and --title required"; exit 1; }
    need_env GITHUB_TOKEN
    export REPO="$repo" TITLE="$title" DESC="$desc" DUE="$due"
    out="$(python3 -c 'import os,json,urllib.request; tok=os.environ["GITHUB_TOKEN"]; owner,repo=os.environ["REPO"].split("/",1); payload={"title":os.environ["TITLE"],"description":os.environ.get("DESC","")}; due=os.environ.get("DUE","");
if due: payload["due_on"]=due+"T00:00:00Z";
data=json.dumps(payload).encode("utf-8"); req=urllib.request.Request(f"https://api.github.com/repos/{owner}/{repo}/milestones",data=data,method="POST"); req.add_header("Authorization","Bearer "+tok); req.add_header("Accept","application/vnd.github+json"); req.add_header("User-Agent","minis"); req.add_header("Content-Type","application/json"); resp=json.load(urllib.request.urlopen(req,timeout=30)); print(resp.get("title",""))' 2>/dev/null)" || true
    add_row 1 gh-milestone-create OK "$out"
    ;;

  gh-releases-list)
    repo=""; [ "${1-}" = "--repo" ] && repo="$2"
    [ -n "$repo" ] || repo="$(infer_repo)"
    [ -n "$repo" ] || { err "--repo required (or set origin remote)"; exit 1; }
    need_env GITHUB_TOKEN
    export REPO="$repo"
    out="$(python3 -c 'import os,json,urllib.request; tok=os.environ["GITHUB_TOKEN"]; owner,repo=os.environ["REPO"].split("/",1); url=f"https://api.github.com/repos/{owner}/{repo}/releases?per_page=10"; req=urllib.request.Request(url,headers={"Authorization":"Bearer "+tok,"Accept":"application/vnd.github+json","User-Agent":"minis"}); data=json.load(urllib.request.urlopen(req,timeout=30)); print("; ".join([it.get("tag_name","") for it in data]))' 2>/dev/null)" || true
    add_row 1 gh-releases-list OK "$out"
    ;;

  gh-release-create)
    repo=""; tag=""; name=""; body=""; draft="false"; pre="false"
    while [ $# -gt 0 ]; do case "$1" in --repo) repo="$2"; shift 2;; --tag) tag="$2"; shift 2;; --name) name="$2"; shift 2;; --body) body="$2"; shift 2;; --draft) draft="$2"; shift 2;; --prerelease) pre="$2"; shift 2;; *) break;; esac; done
    [ -n "$repo" ] || repo="$(infer_repo)"
    [ -n "$repo" ] && [ -n "$tag" ] && [ -n "$name" ] || { err "--repo (or origin remote), --tag, --name required"; exit 1; }
    need_env GITHUB_TOKEN
    export REPO="$repo" TAG="$tag" NAME="$name" BODY="$body" DRAFT="$draft" PRE="$pre"
    out="$(python3 -c 'import os,json,urllib.request; tok=os.environ["GITHUB_TOKEN"]; owner,repo=os.environ["REPO"].split("/",1); payload={"tag_name":os.environ["TAG"],"name":os.environ["NAME"],"body":os.environ.get("BODY","")}; payload["draft"]= (os.environ.get("DRAFT","false").lower()=="true"); payload["prerelease"]= (os.environ.get("PRE","false").lower()=="true"); data=json.dumps(payload).encode("utf-8"); req=urllib.request.Request(f"https://api.github.com/repos/{owner}/{repo}/releases",data=data,method="POST"); req.add_header("Authorization","Bearer "+tok); req.add_header("Accept","application/vnd.github+json"); req.add_header("User-Agent","minis"); req.add_header("Content-Type","application/json"); resp=json.load(urllib.request.urlopen(req,timeout=30)); print(resp.get("html_url",""))' 2>/dev/null)" || true
    add_row 1 gh-release-create OK "$out"
    ;;

  gh-actions-list)
    repo=""; [ "${1-}" = "--repo" ] && repo="$2"
    [ -n "$repo" ] || repo="$(infer_repo)"
    [ -n "$repo" ] || { err "--repo required (or set origin remote)"; exit 1; }
    need_env GITHUB_TOKEN
    export REPO="$repo"
    out="$(python3 -c 'import os,json,urllib.request; tok=os.environ["GITHUB_TOKEN"]; owner,repo=os.environ["REPO"].split("/",1); url=f"https://api.github.com/repos/{owner}/{repo}/actions/workflows?per_page=50"; req=urllib.request.Request(url,headers={"Authorization":"Bearer "+tok,"Accept":"application/vnd.github+json","User-Agent":"minis"}); data=json.load(urllib.request.urlopen(req,timeout=30)); w=data.get("workflows",[]); print("; ".join([f"{it['id']} {it['name']}" for it in w[:20]]))' 2>/dev/null)" || true
    add_row 1 gh-actions-list OK "$out"
    ;;

  gh-actions-runs)
    repo=""; status=""; branch=""
    while [ $# -gt 0 ]; do case "$1" in --repo) repo="$2"; shift 2;; --status) status="$2"; shift 2;; --branch) branch="$2"; shift 2;; *) break;; esac; done
    [ -n "$repo" ] || repo="$(infer_repo)"
    [ -n "$repo" ] || { err "--repo required (or set origin remote)"; exit 1; }
    need_env GITHUB_TOKEN
    export REPO="$repo" STATUS="$status" BRANCH="$branch"
    out="$(python3 -c 'import os,json,urllib.request; tok=os.environ["GITHUB_TOKEN"]; owner,repo=os.environ["REPO"].split("/",1); status=os.environ.get("STATUS",""); branch=os.environ.get("BRANCH",""); qs=["per_page=10"]; 
if status: qs.append("status="+status)
if branch: qs.append("branch="+branch)
url=f"https://api.github.com/repos/{owner}/{repo}/actions/runs?"+"&".join(qs); req=urllib.request.Request(url,headers={"Authorization":"Bearer "+tok,"Accept":"application/vnd.github+json","User-Agent":"minis"}); d=json.load(urllib.request.urlopen(req,timeout=30)); runs=d.get("workflow_runs",[]); lines=[]
for r in runs[:10]:
  lines.append(f"#{r.get('run_number')} {r.get('name')} {r.get('status')} {r.get('conclusion')}")
print("; ".join(lines))' 2>/dev/null)" || true
    add_row 1 gh-actions-runs OK "$out"
    ;;

  gh-actions-dispatch)
    repo=""; wf=""; ref="main"; inputs="{}"
    while [ $# -gt 0 ]; do case "$1" in --repo) repo="$2"; shift 2;; --workflow) wf="$2"; shift 2;; --ref) ref="$2"; shift 2;; --inputs) inputs="$2"; shift 2;; *) break;; esac; done
    [ -n "$repo" ] || repo="$(infer_repo)"
    [ -n "$repo" ] && [ -n "$wf" ] || { err "--repo (or origin remote) and --workflow required"; exit 1; }
    need_env GITHUB_TOKEN
    export REPO="$repo" WF="$wf" REF="$ref" INPUTS="$inputs"
    out="$(python3 -c 'import os,json,urllib.request,urllib.error; tok=os.environ["GITHUB_TOKEN"]; owner,repo=os.environ["REPO"].split("/",1); wf=os.environ["WF"]; ref=os.environ.get("REF","main");
try:
  inputs=json.loads(os.environ.get("INPUTS","{}") or "{}")
except Exception:
  inputs={}
payload={"ref":ref,"inputs":inputs}; data=json.dumps(payload).encode("utf-8"); req=urllib.request.Request(f"https://api.github.com/repos/{owner}/{repo}/actions/workflows/{wf}/dispatches",data=data,method="POST"); req.add_header("Authorization","Bearer "+tok); req.add_header("Accept","application/vnd.github+json"); req.add_header("User-Agent","minis"); req.add_header("Content-Type","application/json");
try:
  r=urllib.request.urlopen(req,timeout=30); print(getattr(r,"status",204))
except urllib.error.HTTPError as e:
  print(e.code)' 2>/dev/null)" || true
    add_row 1 gh-actions-dispatch OK "$out"
    ;;

  gh-pr-list)
    repo=""; state="open"
    while [ $# -gt 0 ]; do case "$1" in --repo) repo="$2"; shift 2;; --state) state="$2"; shift 2;; *) break;; esac; done
    [ -n "$repo" ] || repo="$(infer_repo)"
    [ -n "$repo" ] || { err "--repo required (or set origin remote)"; exit 1; }
    need_env GITHUB_TOKEN
    export REPO="$repo" STATE="$state"
    out="$(python3 -c 'import os,json,urllib.request; tok=os.environ["GITHUB_TOKEN"]; owner,repo=os.environ["REPO"].split("/",1); state=os.environ.get("STATE","open"); url=f"https://api.github.com/repos/{owner}/{repo}/pulls?state={state}&per_page=20"; req=urllib.request.Request(url,headers={"Authorization":"Bearer "+tok,"Accept":"application/vnd.github+json","User-Agent":"minis"}); arr=json.load(urllib.request.urlopen(req,timeout=30)); lines=[f"#{p.get('number')} {p.get('title')} ({p.get('state')})" for p in arr[:20]]; print("; ".join(lines))' 2>/dev/null)" || true
    add_row 1 gh-pr-list OK "$out"
    ;;

  gh-pr-close)
    repo=""; num=""
    while [ $# -gt 0 ]; do case "$1" in --repo) repo="$2"; shift 2;; --number) num="$2"; shift 2;; *) break;; esac; done
    [ -n "$repo" ] || repo="$(infer_repo)"
    [ -n "$repo" ] && [ -n "$num" ] || { err "--repo (or origin remote) and --number required"; exit 1; }
    need_env GITHUB_TOKEN
    export REPO="$repo" NUM="$num"
    out="$(python3 -c 'import os,json,urllib.request; tok=os.environ["GITHUB_TOKEN"]; owner,repo=os.environ["REPO"].split("/",1); num=os.environ["NUM"]; payload={"state":"closed"}; data=json.dumps(payload).encode("utf-8"); req=urllib.request.Request(f"https://api.github.com/repos/{owner}/{repo}/pulls/{num}",data=data,method="PATCH"); req.add_header("Authorization","Bearer "+tok); req.add_header("Accept","application/vnd.github+json"); req.add_header("User-Agent","minis"); req.add_header("Content-Type","application/json"); d=json.load(urllib.request.urlopen(req,timeout=30)); print(d.get("state",""))' 2>/dev/null)" || true
    add_row 1 gh-pr-close OK "$out"
    ;;

  gh-pr-merge)
    repo=""; num=""; method="merge"
    while [ $# -gt 0 ]; do case "$1" in --repo) repo="$2"; shift 2;; --number) num="$2"; shift 2;; --method) method="$2"; shift 2;; *) break;; esac; done
    [ -n "$repo" ] || repo="$(infer_repo)"
    [ -n "$repo" ] && [ -n "$num" ] || { err "--repo (or origin remote) and --number required"; exit 1; }
    need_env GITHUB_TOKEN
    export REPO="$repo" NUM="$num" METHOD="$method"
    out="$(python3 -c 'import os,json,urllib.request; tok=os.environ["GITHUB_TOKEN"]; owner,repo=os.environ["REPO"].split("/",1); num=os.environ["NUM"]; method=os.environ.get("METHOD","merge"); payload={"merge_method":method}; data=json.dumps(payload).encode("utf-8"); req=urllib.request.Request(f"https://api.github.com/repos/{owner}/{repo}/pulls/{num}/merge",data=data,method="PUT"); req.add_header("Authorization","Bearer "+tok); req.add_header("Accept","application/vnd.github+json"); req.add_header("User-Agent","minis"); req.add_header("Content-Type","application/json"); d=json.load(urllib.request.urlopen(req,timeout=30)); print("merged" if d.get("merged") else "not merged")' 2>/dev/null)" || true
    add_row 1 gh-pr-merge OK "$out"
    ;;

  *)
    usage
    exit 1
    ;;
esac

print_summary
