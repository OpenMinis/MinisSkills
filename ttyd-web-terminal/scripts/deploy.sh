#!/bin/sh

# ttyd网页终端部署脚本

# 检查ttyd是否已安装
if command -v ttyd >/dev/null 2>&1; then
    echo "检测到ttyd已安装版本: $(ttyd --version 2>/dev/null || echo 'version unknown')"
else
    echo "未检测到ttyd，正在安装..."
    if apk add ttyd; then
        echo "ttyd安装成功"
    else
        echo "ttyd安装失败"
        exit 1
    fi
fi

# 启动脚本现在位于skill目录中，确保有执行权限
chmod +x /var/minis/skills/ttyd-web-terminal/scripts/start
chmod +x /var/minis/skills/ttyd-web-terminal/scripts/stop

# 检查服务状态并启动
echo ""
echo "检查当前服务状态..."
EXISTING_PID=$(pgrep -f "ttyd.*5222" | head -n 1)
if [ ! -z "$EXISTING_PID" ]; then
    echo "✅ 检测到ttyd服务已在运行 (PID: $EXISTING_PID)"
    echo $EXISTING_PID > /root/ttyd.pid
else
    /var/minis/skills/ttyd-web-terminal/start
fi

echo "  ttyd网页终端启动完成！"
echo "  访问地址: http://localhost:5222"
echo "  启动服务: sh /var/minis/skills/ttyd-web-terminal/start"
echo "  停止服务: sh /var/minis/skills/ttyd-web-terminal/stop"
echo "  查看状态: sh /var/minis/skills/ttyd-web-terminal/status"