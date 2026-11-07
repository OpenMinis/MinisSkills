#!/bin/sh
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
echo "🚀 开始安装 CoreDevice RSD 极客工具链 (coredevice-toolkit / cdtk)..."

# 1. 检查并安装系统级包 (Node.js, Python3, zsign)
echo "📦 检查系统依赖 (Node.js, Python3)..."
which node >/dev/null 2>&1 || apk add nodejs
which python3 >/dev/null 2>&1 || apk add python3 py3-pip
if ! which zsign >/dev/null 2>&1; then
    echo "ℹ️  未检测到 zsign 签名工具，尝试通过 apk 安装..."
    apk add zsign >/dev/null 2>&1 || echo "⚠️ 提示: zsign 未预置，若需本地签名功能可后续安装"
fi

# 2. 检查并安装 Python 核心依赖 (锁定 pymobiledevice3>=11.34.0, pmd-pytcp, cryptography)
echo "⚡ 检查 Python 核心依赖..."
python3 -c "import pymobiledevice3, pmd_pytcp, cryptography" >/dev/null 2>&1 || {
    # sslpsk-pmd3 在 musl/arm64 上没有预编译包，需要本地编译
    echo "🔨 安装编译依赖 (build-base, python3-dev, openssl-dev, libffi-dev)..."
    apk add build-base python3-dev openssl-dev libffi-dev
    echo "📦 正在安装依赖: pymobiledevice3>=11.34.0, pmd-pytcp, cryptography..."
    # Alpine 的系统 Python 受 PEP 668 保护；用环境变量而不是 --break-system-packages，旧版 pip 不认识该参数也不会报错
    PIP_BREAK_SYSTEM_PACKAGES=1 pip install --no-cache-dir "pymobiledevice3>=11.34.0" pmd-pytcp cryptography
}

# 3. 核心协议栈可用性自检
echo "🔍 验证 UserspaceTun / DialPlane 协议栈..."
python3 -c "
try:
    from pymobiledevice3.remote.userspace_tunnel import UserspaceTun, UserspaceDialPlane
    print('  ✅ 用户态纯 Python 网络栈就绪')
except ImportError as e:
    import sys
    print(f'  ❌ 协议栈依赖不完整: {e}', file=sys.stderr)
    print('  请确认 pymobiledevice3 版本 >= 11.34.0 且 pmd-pytcp 已正确安装。', file=sys.stderr)
    sys.exit(1)
"

# 4. 安装公共库到 Python site-packages
SP_DIR="$(python3 -c 'import site; print(site.getsitepackages()[0])')"
echo "📁 安装 coredevice_session.py 与 tls_psk_proxy.js 到 $SP_DIR"
cp -f "$SCRIPT_DIR/coredevice_session.py" "$SP_DIR/"
# coredevice_session 按自身所在目录查找桥接脚本，必须一起拷贝，否则在 scripts/ 以外 import 会报找不到 tls_psk_proxy.js
cp -f "$SCRIPT_DIR/tls_psk_proxy.js" "$SP_DIR/"

# 5. 注册 cdtk-* CLI 命令到 /usr/local/bin
echo "🔧 注册全局 CLI 命令 (cdtk-*)..."
mkdir -p /usr/local/bin
for tool in cdtk-install cdtk-ctrl cdtk-profile cdtk-fs cdtk-diag cdtk-crash cdtk-inspect cdtk-springboard; do
    if [ -f "$SCRIPT_DIR/$tool" ]; then
        chmod +x "$SCRIPT_DIR/$tool"
        ln -sf "$SCRIPT_DIR/$tool" "/usr/local/bin/$tool"
        echo "  • 已注册 /usr/local/bin/$tool"
    fi
done

echo ""
echo "✨ 安装完成！请确保在 Surge 中已开启本地回环 (10.7.0.1 = reflect)，"
echo "并将配对记录放入 /var/minis/workspace/cdtk/*.plist (权限严格锁定 chmod 600)。"
