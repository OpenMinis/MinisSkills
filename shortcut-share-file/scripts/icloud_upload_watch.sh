#!/bin/bash
# icloud_upload_watch.sh — 等待 iCloud 文件上传完成（ctime 同步信号检测）
# 用法: icloud_upload_watch.sh <文件路径|文件名> [超时秒数，默认600]
#       支持三种写法:
#         1) 绝对路径: /var/minis/mounts/iCloud/极速分享/xxx.bin
#         2) 以 iCloud 根为基准的相对路径: 极速分享/xxx.bin
#         3) 纯文件名: xxx.bin（默认在 极速分享/ 目录下）
#
# 原理: 文件写入 iCloud 挂载点后，系统同步管线完成处理时文件 ctime 会跳变一次
#       （实测：小文件 ~8-10 秒；大文件按约 4MB/s 线性增长，128MB 约 33 秒）
# 退出码: 0=检测到上传完成 / 2=超时 / 1=参数或文件错误

ARG="${1:?用法: icloud_upload_watch.sh <文件路径|文件名> [超时秒数]}"
TIMEOUT="${2:-600}"
ICLOUD_ROOT="/var/minis/mounts/iCloud"

case "$ARG" in
  /*)  F="$ARG" ;;
  */*) F="$ICLOUD_ROOT/$ARG" ;;
  *)   F="$ICLOUD_ROOT/极速分享/$ARG" ;;
esac

[ -f "$F" ] || { echo "ERROR: 文件不存在: $F"; exit 1; }

y=$(stat -c %Y "$F"); z=$(stat -c %Z "$F")
if [ "$z" -gt "$y" ]; then
  echo "UPLOAD_OK (already synced) $F"
  exit 0
fi

start=$(date +%s)
echo "WATCHING $F (size=$(stat -c %s "$F")B) timeout=${TIMEOUT}s"
i=0
while :; do
  sleep 2
  i=$((i + 1))
  z2=$(stat -c %Z "$F" 2>/dev/null) || { echo "ERROR: 文件消失: $F"; exit 1; }
  el=$(( $(date +%s) - start ))
  if [ "$z2" != "$z" ]; then
    echo "UPLOAD_OK after ${el}s"
    exit 0
  fi
  if [ "$el" -ge "$TIMEOUT" ]; then
    echo "TIMEOUT after ${el}s (无 ctime 跳变)"
    exit 2
  fi
  [ $((i % 15)) -eq 0 ] && echo "still waiting: ${el}s"
done
