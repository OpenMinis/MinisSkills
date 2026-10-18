#!/bin/sh
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
echo "🚀 开始安装 CoreDevice RSD 极客工具链 (coredevice-toolkit / cdtk)..."

# 1. 检查并安装系统级依赖
echo "📦 检查系统依赖 (Node.js, Python3, Cryptography)..."
which node >/dev/null 2>&1 || apk add nodejs
which python3 >/dev/null 2>&1 || apk add python3 py3-pip
which zsign >/dev/null 2>&1 || apk add zsign >/dev/null 2>&1 || true

# 2. 检查 Python 核心依赖 (pymobiledevice3, pmd-pytcp, cryptography)
python3 -c "import pymobiledevice3, cryptography" >/dev/null 2>&1 || {
    echo "⚡ 正在安装 Python 核心依赖 (pymobiledevice3, pmd-pytcp, cryptography)..."
    pip install --no-cache-dir pymobiledevice3 pmd-pytcp cryptography
}

# 3. 安装公共桥接库到 Python site-packages
SP_DIR="$(python3 -c 'import site; print(site.getsitepackages()[0])' 2>/dev/null || echo '/usr/lib/python3.12/site-packages')"
echo "📁 复制 coredevice_session.py 到 Python 库目录: $SP_DIR"
cp -f "$SCRIPT_DIR/coredevice_session.py" "$SP_DIR/"
# 建立向后兼容别名软链
ln -sf "$SP_DIR/coredevice_session.py" "$SP_DIR/minis_device.py"

# 4. 软链接 CLI 工具到 /usr/local/bin
echo "🔧 注册全局 CLI 命令到 /usr/local/bin (cdtk-*)..."
mkdir -p /usr/local/bin
for tool in cdtk-install cdtk-ctrl cdtk-profile cdtk-fs cdtk-diag cdtk-crash cdtk-inspect; do
    if [ -f "$SCRIPT_DIR/$tool" ]; then
        chmod +x "$SCRIPT_DIR/$tool"
        ln -sf "$SCRIPT_DIR/$tool" "/usr/local/bin/$tool"
        echo "  • 已注册 /usr/local/bin/$tool"
    fi
done

# 清理旧版可能冲突的 minis-* 软链接以防混淆
for old_tool in minis-install minis-ctrl minis-profile minis-fs minis-diag minis-crash minis-inspect; do
    if [ -L "/usr/local/bin/$old_tool" ]; then
        rm -f "/usr/local/bin/$old_tool"
    fi
done

echo ""
echo "✨ 安装完成！请确保在 Surge 中已开启本地回环 (10.7.0.1 = reflect)，"
echo "并在工作区放入配对文件 (建议 chmod 600) 即可开始使用！"
