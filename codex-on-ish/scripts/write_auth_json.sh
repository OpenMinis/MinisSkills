#!/bin/sh
# write_auth_json.sh — install tokens from /tmp/token_result.json into ~/.codex/auth.json
python3 - <<'EOF'
import json, os, datetime
d = json.load(open("/tmp/token_result.json"))
auth = {
    "OPENAI_API_KEY": None,
    "tokens": {
        "id_token": d["id_token"],
        "access_token": d["access_token"],
        "refresh_token": d["refresh_token"],
    },
    "last_refresh": datetime.datetime.now(datetime.timezone.utc)
        .strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
}
p = os.path.expanduser("~/.codex/auth.json")
os.makedirs(os.path.dirname(p), exist_ok=True)
open(p, "w").write(json.dumps(auth))
os.chmod(p, 0o600)
print("auth.json written")
EOF
codex login status 2>&1 | tail -1
