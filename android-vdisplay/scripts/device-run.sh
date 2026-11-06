#!/system/bin/sh
# Runs on the device (pushed by start.sh): server <scid> <WxH/dpi> | bridge <scid> <port>
case "$1" in
server)
  exec >/data/local/tmp/sc/server.log 2>&1
  CLASSPATH=/data/local/tmp/sc/server.jar exec app_process / com.genymobile.scrcpy.Server 5.0.1 scid=$2 log_level=debug \
    audio=false control=true tunnel_forward=true send_dummy_byte=true new_display=$3 vd_system_decorations=true \
    display_ime_policy=${IME_POLICY:-local} \
    video_bit_rate=${BITRATE:-4000000} max_fps=${FPS:-30} cleanup=false power_off_on_close=false power_on=false stay_awake=false ;;
bridge)
  exec >/data/local/tmp/sc/bridge.log 2>&1
  CLASSPATH=/data/local/tmp/sc/shell.jar exec app_process / app.openminis.vdisplay.Bridge $2 ${3:-27183} video,control ;;
up)
  # up <scid> <WxH/dpi> <port> <x> <y> <w> : stop old processes, start server + bridge + overlay TOGETHER, then wait on the
  # device (100 ms polling, no adb round trips) until the virtual display exists and the app is connected + decoding.
  # Prints one line: "OK <displayId> <ms>" or "FAIL <stage> <ms>".
  D=/data/local/tmp/sc; PKG=app.openminis.vdisplay; SCID=$2; SIZE=$3; PORT=$4
  now() { date +%s%3N; }; T0=$(now)
  am force-stop $PKG >/dev/null 2>&1
  # Only touch OUR processes: the server started with our scid, and our own Bridge class. A scrcpy server that the user started
  # for other purposes (different scid, e.g. from scrcpy on a PC) must be left alone.
  for p in $(ps -A -o PID,ARGS | grep -E "scrcpy\.Server .*scid=$SCID|vdisplay\.Bridge $SCID" | grep -v grep | awk '{print $1}'); do kill $p 2>/dev/null; done
  rm -f $D/server.log $D/bridge.log
  BITRATE=${BITRATE:-4000000} nohup setsid sh $0 server $SCID $SIZE </dev/null >/dev/null 2>&1 &
  # Keep the dependency order (server listening → bridge listening → overlay). Starting all three at once makes the overlay hit the
  # bridge before it listens (ECONNREFUSED) and the retry can land on a half-open session. Waiting here costs ~50 ms polls, not adb trips.
  i=0; while [ $i -lt 400 ]; do grep -q scrcpy_$SCID /proc/net/unix 2>/dev/null && break; i=$((i+1)); sleep 0.05; done
  grep -q scrcpy_$SCID /proc/net/unix 2>/dev/null || { echo "FAIL server $(( $(now) - T0 ))"; exit 1; }
  nohup setsid sh $0 bridge $SCID $PORT </dev/null >/dev/null 2>&1 &
  i=0; while [ $i -lt 200 ]; do grep -q listening $D/bridge.log 2>/dev/null && break; i=$((i+1)); sleep 0.05; done
  grep -q listening $D/bridge.log 2>/dev/null || { echo "FAIL bridge $(( $(now) - T0 ))"; exit 1; }
  am start-foreground-service -n $PKG/.PipService --ei port $PORT --ei x ${5:-20} --ei y ${6:-300} --ei w ${7:-168} --ei idle ${IDLE_MIN:-10} >/dev/null 2>&1
  ID=""; i=0
  while [ $i -lt 200 ]; do                                   # 200 × 0.1 s = 20 s
    [ -z "$ID" ] && ID=$(grep -o 'New display: .*id=[0-9]*' $D/server.log 2>/dev/null | tail -1 | sed 's/.*id=//')
    if [ -n "$ID" ]; then
      printf 'GET /status HTTP/1.0\r\n\r\n' | nc -w1 127.0.0.1 28080 2>/dev/null | grep -q '"frames":[1-9]' && { echo "OK $ID $(( $(now) - T0 ))"; exit 0; }
    fi
    i=$((i+1)); sleep 0.1
  done
  if [ -z "$ID" ]; then
    grep -q scrcpy_$SCID /proc/net/unix 2>/dev/null && echo "FAIL display $(( $(now) - T0 ))" || echo "FAIL server $(( $(now) - T0 ))"
  else echo "FAIL frames $(( $(now) - T0 ))"; fi
  exit 1 ;;
waitrender)
  # waitrender <max_ms>: poll /status until a picture was really rendered (ready:true == rendered>0). Prints "OK <ms>" or "FAIL <ms>".
  now() { date +%s%3N; }; T0=$(now); MAX=${2:-3000}
  while [ $(( $(now) - T0 )) -lt $MAX ]; do
    printf 'GET /status HTTP/1.0\r\n\r\n' | nc -w1 127.0.0.1 28080 2>/dev/null | grep -q '"ready":true' && { echo "OK $(( $(now) - T0 ))"; exit 0; }
    sleep 0.1
  done
  echo "FAIL $(( $(now) - T0 ))"; exit 1 ;;
health)
  # health <scid>: one-line summary used by start.sh to decide whether the running display can be reused.
  # Prints "app=<0|1> server=<0|1> id=<displayId> status=<one-line /status JSON>"
  D=/data/local/tmp/sc; SCID=$2
  A=0; [ -n "$(ps -A -o PID,ARGS 2>/dev/null | awk '$2=="app.openminis.vdisplay"')" ] && A=1
  S=0; ps -A -o PID,ARGS 2>/dev/null | grep -E "scrcpy\.Server .*scid=$SCID" | grep -vq grep && S=1
  ID=$(grep -o 'New display: .*id=[0-9]*' $D/server.log 2>/dev/null | tail -1 | sed 's/.*id=//')
  ST=$(printf 'GET /status HTTP/1.0\r\n\r\n' | nc -w1 127.0.0.1 28080 2>/dev/null | tr -d '\r\n' | sed 's/.*\({"ok".*}\).*/\1/')
  echo "app=$A server=$S id=$ID status=$ST" ;;
esac
