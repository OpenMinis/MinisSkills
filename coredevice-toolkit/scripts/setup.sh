#!/bin/sh
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
echo "🚀 开始安装 CoreDevice RSD 极客工具链 (coredevice-toolkit)..."

# 1. 检查并安装系统级依赖
echo "📦 检查系统依赖 (Node.js, Python3, Cryptography)..."
which node >/dev/null 2>&1 || apk add nodejs
which python3 >/dev/null 2>&1 || apk add python3 py3-pip
which zsign >/dev/null 2>&1 || apk add zsign >/dev/null 2>&1 || true

# 2. 检查 Python 依赖
python3 -c "import pymobiledevice3, cryptography" >/dev/null 2>&1 || {
    echo "⚡ 正在安装 Python 核心依赖 (pymobiledevice3, pmd-pytcp, cryptography)..."
    pip install --no-cache-dir pymobiledevice3 pmd-pytcp cryptography
}

# 3. 安装公共桥接库到 Python site-packages
SP_DIR="$(python3 -c 'import site; print(site.getsitepackages()[0])' 2>/dev/null || echo '/usr/lib/python3.12/site-packages')"
echo "📁 复制 minis_device.py 到 Python 库目录: $SP_DIR"
cp -f "$SCRIPT_DIR/minis_device.py" "$SP_DIR/"

# 4. 软链接/安装 CLI 工具到 /usr/local/bin
echo "🔧 注册全局 CLI 命令到 /usr/local/bin..."
mkdir -p /usr/local/bin
for tool in minis-install minis-ctrl minis-profile minis-fs minis-diag minis-crash minis-inspect; do
    if [ -f "$SCRIPT_DIR/$tool" ]; then
        chmod +x "$SCRIPT_DIR/$tool"
        ln -sf "$SCRIPT_DIR/$tool" "/usr/local/bin/$tool"
        echo "  • 已注册 /usr/local/bin/$tool"
    fi
done

echo "\n✨ 安装完成！请确保在 Surge 中已开启本地回环 (10.7.0.1 = reflect)，"
echo "并在工作区放入配对文件即可开始使用！"
