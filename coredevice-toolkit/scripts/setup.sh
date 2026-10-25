#!/bin/sh
# CoreDevice RSD 工具链安装脚本 (cdtk)
# 目标环境: iOS + iSH/Alpine Linux
set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REQ_FILE="$SCRIPT_DIR/requirements.txt"

die() {
  echo "❌ $*" >&2
  exit 1
}

echo "🚀 开始安装 CoreDevice RSD 工具链 (coredevice-toolkit / cdtk)..."

# 1. 系统依赖。command -v 是 POSIX，which 在部分精简环境不存在。
echo "📦 检查系统依赖 (Node.js, Python3)..."
command -v node >/dev/null 2>&1 || apk add nodejs
command -v python3 >/dev/null 2>&1 || apk add python3 py3-pip
if ! command -v zsign >/dev/null 2>&1; then
  echo "ℹ️  未检测到 zsign（仅 cdtk-install 的本地重签名功能需要，可选）"
fi

# 2. Alpine 预编译二进制包：避免在设备上编译 cryptography。
echo "📦 安装 Alpine 预编译支持库..."
apk add py3-cryptography py3-requests py3-pillow py3-psutil py3-tqdm \
  py3-wsproto py3-hyperframe py3-packaging >/dev/null 2>&1 || true

# 3. Python 依赖。pip 统一走 python3 -m pip，避免 pip 指向其它解释器。
SP_DIR="$(python3 -c 'import site; print(site.getsitepackages()[0])')"
[ -w "$SP_DIR" ] || die "Python site-packages 不可写: $SP_DIR"

PIP="python3 -m pip"
PIP_FLAGS="--no-cache-dir"
if $PIP install --help 2>/dev/null | grep -q -- "--break-system-packages"; then
  # Alpine 3.19+ / Python 3.12 起默认 PEP 668 (externally-managed)
  PIP_FLAGS="$PIP_FLAGS --break-system-packages"
fi

echo "⚡ 安装 pymobiledevice3 (--no-deps，跳过 sslpsk-pmd3 编译)..."
$PIP install $PIP_FLAGS --no-deps "pymobiledevice3>=11.34.0,<12"

if [ -f "$REQ_FILE" ]; then
  echo "⚡ 安装协议栈依赖..."
  # 可选包失败不阻塞，最后由导入自检判定核心是否就绪。
  $PIP install $PIP_FLAGS -r "$REQ_FILE" || \
    echo "⚠️  部分可选依赖安装失败，继续执行核心自检"
else
  echo "⚠️  未找到 requirements.txt，跳过依赖清单"
fi

# 4. 协议栈自检。缺核心模块就明确失败，不带着坏环境继续。
echo "🔍 验证 UserspaceTun / DialPlane 协议栈..."
python3 - <<'PY'
import sys
try:
    from pymobiledevice3.remote.userspace_tunnel import UserspaceTun, UserspaceDialPlane
    import pmd_pytcp
    import cryptography
except ImportError as e:
    print(f"  ❌ 协议栈依赖不完整: {e}", file=sys.stderr)
    print("  请确认 pymobiledevice3>=11.34.0、pmd-pytcp、cryptography 已安装。", file=sys.stderr)
    sys.exit(1)
print("  ✅ 用户态纯 Python 网络栈就绪")
PY

# 5. 安装共享库和 Node 桥接脚本。
#    注意：两者必须同目录。coredevice_session.py 通过 __file__ 查找 tls_psk_proxy.js，
#    而通过 /usr/local/bin 符号链接调用时，Python 会从 site-packages 导入复制后的副本。
echo "📁 安装核心库到 $SP_DIR"
cp -f "$SCRIPT_DIR/coredevice_session.py" "$SP_DIR/"
cp -f "$SCRIPT_DIR/tls_psk_proxy.js" "$SP_DIR/"

# 6. 注册 CLI。
echo "🔧 注册全局 CLI 命令 (cdtk-*)..."
mkdir -p /usr/local/bin
for tool in cdtk-install cdtk-ctrl cdtk-profile cdtk-fs cdtk-diag cdtk-crash cdtk-inspect cdtk-springboard cdtk-proc cdtk-doctor; do
  if [ -f "$SCRIPT_DIR/$tool" ]; then
    chmod +x "$SCRIPT_DIR/$tool"
    ln -sf "$SCRIPT_DIR/$tool" "/usr/local/bin/$tool"
    echo "  • /usr/local/bin/$tool"
  fi
done

echo ""
echo "✨ 安装完成。"
echo "   1. 在 Surge 中启用 10.7.0.1 本地回环（见 references/SURGE_LOOPBACK_zh.md）"
echo "   2. 将 pairing record 放入 /root/.cdtk/pairing/ 或 /var/minis/workspace/cdtk/（chmod 600）"
echo "   3. 运行 cdtk-doctor 体检"
