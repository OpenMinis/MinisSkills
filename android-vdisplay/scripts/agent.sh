#!/bin/sh
# Call the agent API: agent.sh tap 100 200 | swipe x1 y1 x2 y2 [ms] | key 4 | text hello | start pkg | status | takeover 1|0
#                  title "what I'm doing" | version | resume | window x=.. y=.. w=.. | hide | show | shot [out.png]
#                  ui [find <text>] [clickable] [editable] [scrollable] [json] [all-displays] | ui-tap <text>   (widget tree of the 2nd screen; coords in the 540-wide space)
. "$(dirname "$0")/common.sh"
# No eager ensure_adb here: agent()/agent_to() try the forwarded HTTP port first and only fall back to adb health checks on failure.
# (`version` is the one command that needs adb, for the installed-APK check.)
[ "$1" = version ] && { ensure_adb || exit $?; }
REF=${REF_W:-540}
# GET /ui with one automatic recovery: if the accessibility service is off (503 "not enabled") re-enable it and retry once.
ui_get() {
  _r=$(agent "$1")
  case "$_r" in *'"serviceEnabled":false'*|*'"serviceConnected":false'*)
    ui_heal && _r=$(agent "$1") ;;
  esac
  printf '%s' "$_r"
}
c=$1; shift
case "$c" in
  tap) agent "/tap?x=$1&y=$2&ref=$REF" ;;
  swipe) agent "/swipe?x1=$1&y1=$2&x2=$3&y2=$4&ms=${5:-300}&ref=$REF" ;;
  key) agent "/key?code=$1" ;;
  text) agent "/text?s=$(python3 -c 'import sys,urllib.parse;print(urllib.parse.quote(sys.argv[1]))' "$1" 2>/dev/null || printf %s "$1")" ;;
  start) agent "/start?pkg=$1" ;;
  status) agent "/status" ;;
  title) agent "/title?s=$(python3 -c 'import sys,urllib.parse;print(urllib.parse.quote(sys.argv[1]))' "$1" 2>/dev/null)" ;;
  version) echo "$(version_info)"; agent "/version" ;;
  resume) agent "/resume" ;;
  takeover) agent "/takeover?on=$1" ;;
  window) q=""; for kv in "$@"; do q="$q&$kv"; done; agent "/window?${q#&}" ;;
  hide) agent "/window?hide=1" ;;
  show) agent "/window?hide=0" ;;
  shot) # agent.sh shot [out-file] [png|jpg|webp] [quality 30-100]   — jpg is ~2x faster and ~4x smaller than png (slightly lossy); default png
        FMT=${2:-png}; Q=${3:-80}; case "$FMT" in png) EXT=png;; jpg|jpeg) FMT=jpg; EXT=jpg;; webp) EXT=webp;; *) echo "ERR: format must be png|jpg|webp"; exit 2;; esac
        OUT=${1:-$STATE/shot.$EXT}; agent_to "/screenshot?w=$REF&fmt=$FMT&q=$Q" "$OUT"
        MAGIC=$(head -c 4 "$OUT" 2>/dev/null | od -An -tx1 | tr -d ' \n')
        case "$FMT:$MAGIC" in
          png:89504e47|jpg:ffd8ff*|webp:52494646) echo "$OUT" ;;
          *) echo "ERR: screenshot failed: $(head -c 200 "$OUT" 2>/dev/null)"; echo "hint: check ready/frames via agent.sh status; if ready=false run start.sh; unlock the phone if locked"; upgrade_hint; rm -f "$OUT"; exit 1 ;;
        esac ;;
  ui) q="ref=$REF"; FMT=lines
      while [ $# -gt 0 ]; do case "$1" in
        find) shift; q="$q&find=$(python3 -c 'import sys,urllib.parse;print(urllib.parse.quote(sys.argv[1]))' "$1")" ;;
        clickable|editable|scrollable) q="$q&$1=1" ;;
        json) q="$q&format=json" ;;
        limit) shift; q="$q&limit=$1" ;;
        display) shift; q="$q&display=$1" ;;
        all-displays) q="$q&display=all" ;;
        *) echo "ERR: unknown ui option $1 (find <text> | clickable | editable | scrollable | json | limit N | display N)"; exit 2 ;;
      esac; shift; done
      R=$(ui_get "/ui?$q"); echo "$R"
      case "$R" in '{"ok":false'*) exit 1 ;; "") exit 1 ;; esac
      exit 0 ;;
  ui-tap) # ui-tap <text>: tap the centre of the single best match (exact text/desc/id first, then substring); several candidates -> list them, tap nothing
      [ -z "$1" ] && { echo "ERR: usage: ui-tap <text>"; exit 2; }
      Q=$(python3 -c 'import sys,urllib.parse;print(urllib.parse.quote(sys.argv[1]))' "$1")
      R=$(ui_get "/ui?ref=$REF&format=json&find=$Q&limit=50")
      case "$R" in '{"ok":true'*) ;; *) echo "$R"; exit 1 ;; esac
      OUT=$(printf '%s' "$R" | python3 -c '
import sys,json
t=sys.argv[1].lower(); d=json.load(sys.stdin); it=d["items"]
def lab(n): return [n.get("text","").lower(), n.get("desc","").lower(), n.get("id","").lower()]
ex=[n for n in it if t in lab(n)]
pool=ex or it
# several nodes can share one centre (a label inside a clickable key): they are one target
pts={}
for n in pool: pts.setdefault(tuple(n["center"]),n)
if len(pts)==1:
    n=list(pts.values())[0]; print("TAP %d %d %s"%(n["center"][0],n["center"][1],n.get("text") or n.get("desc") or n.get("id")))
elif not pts: print("NONE")
else:
    print("AMBIGUOUS")
    for n in pool[:15]: print("[%d] %s %r id=%s c=(%d,%d)%s"%(n["i"],n["class"],n.get("text") or n.get("desc",""),n.get("id",""),n["center"][0],n["center"][1]," click" if n.get("clickable") else ""))
' "$1") || exit 1
      case "$OUT" in
        TAP*) set -- $OUT; X=$2; Y=$3; shift 3; agent "/tap?x=$X&y=$Y&ref=$REF"; echo "tapped \"$*\" at ($X,$Y)"; exit 0 ;;
        NONE) echo "ERR: no node matches \"$1\" (try: agent.sh ui, or shot if the app draws its own UI)"; exit 1 ;;
        *) echo "$OUT"; echo "ERR: several different matches; pick one and use: agent.sh tap <cx> <cy>"; exit 1 ;;
      esac ;;
  *) echo "Unknown command: $c"; exit 2 ;;
esac
echo
