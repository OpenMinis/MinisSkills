#!/bin/sh
# codex on iSH: transparent wrapper
#  - routes codex through local MITM+spoof proxy (rustls broken natively on iSH)
#  - proxy is a singleton, refcounted: starts on demand, tears down when last codex exits
#  - yolo behavior comes from ~/.codex/config.toml (approval_policy/sandbox_mode)
STATE=/tmp/codex-proxy
CLIENTS="$STATE/clients"
PORT=8894
mkdir -p "$CLIENTS"

CPID=$$
echo "$CPID" > "$CLIENTS/$CPID"
cleanup() { rm -f "$CLIENTS/$CPID" 2>/dev/null; }
trap cleanup EXIT INT TERM

# singleton proxy: start only if no live pidfile AND no starting instance
P_PID=$(cat "$STATE/proxy.pid" 2>/dev/null)
if { [ -z "$P_PID" ] || ! kill -0 "$P_PID" 2>/dev/null; } && ! pgrep -f "pyproxy6.py $PORT" >/dev/null 2>&1; then
    rm -f "$STATE/proxy.pid"
    nohup python3 /usr/local/bin/pyproxy6.py "$PORT" > "$STATE/proxy.out" 2>&1 &
fi

# wait for the port (startup on iSH can take a couple seconds)
i=0
while [ "$i" -lt 12 ]; do
    python3 -c "import socket;socket.create_connection(('127.0.0.1',$PORT),0.5)" 2>/dev/null && break
    i=$((i+1)); sleep 1
done

export SSL_CERT_FILE=/etc/pyproxy/ca256.pem
export HTTPS_PROXY="http://127.0.0.1:$PORT"
export HTTP_PROXY="http://127.0.0.1:$PORT"
export NO_PROXY="localhost,127.0.0.1"

/usr/local/bin/codex.bin "$@"
RC=$?
cleanup
trap - EXIT INT TERM
exit $RC
