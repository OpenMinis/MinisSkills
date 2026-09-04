#!/bin/sh
# setup.sh — install Codex CLI on iSH (Minis iOS sandbox)
# Requires: apk add curl openssl python3
set -e
CODEX_VER="rust-v0.130.0"
BIN="/usr/local/bin"

[ "$(uname -m)" = "aarch64" ] || { echo "this skill targets aarch64 iSH"; exit 1; }

# 1. certificates (ECDSA P-256 — codex's ring provider rejects RSA/P-521)
mkdir -p /etc/pyproxy && cd /etc/pyproxy
[ -f ca256.pem ] || {
  openssl ecparam -name prime256v1 -genkey -noout -out ca256.key 2>/dev/null
  openssl req -x509 -new -key ca256.key -out ca256.pem -days 3650 -subj "/CN=Minis Local CA" 2>/dev/null
  openssl ecparam -name prime256v1 -genkey -noout -out srv256.key 2>/dev/null
  openssl req -new -key srv256.key -out srv256.csr -subj "/CN=auth.openai.com" 2>/dev/null
  printf 'subjectAltName=DNS:auth.openai.com,DNS:*.openai.com,DNS:chatgpt.com,DNS:*.chatgpt.com\nextendedKeyUsage=serverAuth\n' > ext.cnf
  openssl x509 -req -in srv256.csr -CA ca256.pem -CAkey ca256.key -CAcreateserial -out srv256.pem -days 3650 -extfile ext.cnf 2>/dev/null
  chmod 600 ca256.key srv256.key
}

# 2. codex binary (v0.130 = last release whose rustls works on iSH)
cd /tmp
curl -sL -o codex.tgz "https://github.com/openai/codex/releases/download/$CODEX_VER/codex-aarch64-unknown-linux-musl.tar.gz"
tar xzf codex.tgz
install -m 755 codex-aarch64-unknown-linux-musl "$BIN/codex.bin"
rm -f codex.tgz codex-aarch64-unknown-linux-musl

# 3. proxy + wrapper (from this skill's scripts/)
SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
install -m 755 "$SKILL_DIR/scripts/pyproxy6.py" "$BIN/pyproxy6.py"
install -m 755 "$SKILL_DIR/scripts/codex-wrapper.sh" "$BIN/codex-wrapper.sh"
ln -sf "$BIN/codex-wrapper.sh" "$BIN/codex"

# 4. config defaults (idempotent)
mkdir -p ~/.codex
python3 - <<'EOF'
import os
p = os.path.expanduser("~/.codex/config.toml")
c = open(p).read() if os.path.exists(p) else ""
def top(k, v):
    global c
    if k + " =" not in c:
        c = k + " = " + v + "\n" + c
top("model", '"gpt-5.5"')
top("approval_policy", '"never"')
top("sandbox_mode", '"danger-full-access"')
open(p, "w").write(c)
EOF

codex --version && echo "OK — run scripts/token_poller3.sh to log in"
