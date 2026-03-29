#!/bin/sh
# ==============================================================================
# AutoGLM Phone Agent 一键安装脚本
# AI 驱动的手机自动化框架 - 通过自然语言指令操作手机应用
# ==============================================================================
# 安装位置：/root/AutoGLM
# 适用系统：Linux (推荐 Ubuntu/Debian/Alpine)
# ==============================================================================

set -e

INSTALL_DIR="/root/AutoGLM"
VENV_DIR="${INSTALL_DIR}/venv"
GITHUB_URL="https://github.com/zai-org/Open-AutoGLM.git"

# 颜色输出
if [ -t 1 ]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    BLUE='\033[0;34m'
    NC='\033[0m'
else
    RED=''
    GREEN=''
    YELLOW=''
    BLUE=''
    NC=''
fi

log_info()    { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $1"; }
log_step()    { echo -e "${BLUE}[STEP]${NC} $1"; }

# ==============================================================================
# 检查是否已安装
# ==============================================================================
if [ -d "${INSTALL_DIR}" ] && [ -f "${INSTALL_DIR}/quickstart.py" ]; then
    log_warn "检测到已安装：${INSTALL_DIR}"
    read -p "是否重新安装？(y/N): " confirm
    if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
        log_info "开始重新安装..."
        rm -rf "${INSTALL_DIR}"
    else
        log_info "跳过安装，使用现有环境"
        echo ""
        echo "=============================================="
        echo "  使用方式"
        echo "=============================================="
        echo "快捷命令：cd ${INSTALL_DIR} && python3 quickstart.py \"任务描述\""
        echo "示例：python3 quickstart.py \"打开小红书搜索美食\""
        echo ""
        exit 0
    fi
fi

# ==============================================================================
# 步骤 1: 创建目录
# ==============================================================================
log_step "1/5: 创建安装目录 ${INSTALL_DIR}"
mkdir -p "${INSTALL_DIR}"
cd "${INSTALL_DIR}"

# ==============================================================================
# 步骤 2: 下载项目
# ==============================================================================
log_step "2/5: 下载 AutoGLM 项目"

# 优先使用 git，失败则使用 curl+unzip
if command -v git &> /dev/null; then
    log_info "使用 git 克隆..."
    git clone "${GITHUB_URL}" /tmp/Open-AutoGLM
    mv /tmp/Open-AutoGLM/* .
    mv /tmp/Open-AutoGLM/.* . 2>/dev/null || true
    rm -rf /tmp/Open-AutoGLM
else
    log_info "使用 curl 下载..."
    curl -sL "${GITHUB_URL/archive/refs/heads/main}.zip" -o /tmp/project.zip
    unzip -q /tmp/project.zip -d /tmp/
    mv /tmp/Open-AutoGLM-main/* .
    mv /tmp/Open-AutoGLM-main/.* . 2>/dev/null || true
    rm -rf /tmp/project.zip /tmp/Open-AutoGLM-main
fi

log_info "项目下载完成：${INSTALL_DIR}"

# ==============================================================================
# 步骤 3: 创建虚拟环境
# ==============================================================================
log_step "3/5: 创建 Python 虚拟环境"
python3 -m venv "${VENV_DIR}"
log_info "虚拟环境创建完成"

# ==============================================================================
# 步骤 4: 安装依赖
# ==============================================================================
log_step "4/5: 安装 Python 依赖"
. "${VENV_DIR}/bin/activate"

log_info "升级 pip..."
pip install --upgrade pip -q

log_info "安装核心依赖..."
pip install Pillow>=12.0.0 openai>=2.9.0 requests>=2.31.0 -q

log_info "安装 phone-agent 包..."
pip install -e . -q

log_info "依赖安装完成"

# ==============================================================================
# 步骤 5: 验证安装
# ==============================================================================
log_step "5/5: 验证安装"
if python3 quickstart.py --help > /dev/null 2>&1; then
    log_info "✅ 验证成功！"
else
    log_error "❌ 验证失败，请检查错误信息"
    exit 1
fi

# ==============================================================================
# 创建快捷脚本
# ==============================================================================
cat > /root/aglm.sh << 'EOF'
#!/bin/sh
# AutoGLM Phone Agent 快捷脚本
VENV="/root/AutoGLM/venv"
if [ ! -d "${VENV}" ]; then
    echo "错误：虚拟环境未找到"
    exit 1
fi
. ${VENV}/bin/activate
cd /root/AutoGLM
exec python3 quickstart.py "$@"
EOF
chmod +x /root/aglm.sh

# ==============================================================================
# 输出完成信息
# ==============================================================================
echo ""
echo "=============================================="
echo -e "${GREEN}  AutoGLM 安装完成！${NC}"
echo "=============================================="
echo ""
echo "📁 安装位置：${INSTALL_DIR}"
echo "🔧 虚拟环境：${VENV_DIR}"
echo "⚡ 快捷脚本：/root/aglm.sh"
echo ""
echo "=============================================="
echo "  快速开始"
echo "=============================================="
echo ""
echo "1️⃣ 基础用法:"
echo "   cd ${INSTALL_DIR}"
echo "   source ${VENV_DIR}/bin/activate"
echo "   python3 quickstart.py \"打开小红书搜索美食\""
echo ""
echo "2️⃣ 使用快捷脚本:"
echo "   /root/aglm.sh \"打开微信\""
echo ""
echo "3️⃣ 自定义 API 配置:"
echo "   python3 quickstart.py \\"
echo "     --base-url https://open.bigmodel.cn/api/paas/v4 \\"
echo "     --model autoglm-phone-9b \\"
echo "     --apikey YOUR_KEY \\"
echo "     \"测试任务\""
echo ""
echo "=============================================="
echo "  API Key 获取"
echo "=============================================="
echo ""
echo "智谱 BigModel（推荐中文场景）:"
echo "  https://bigmodel.cn/"
echo ""
echo "ModelScope 魔搭社区:"
echo "  https://modelscope.cn/models/ZhipuAI/AutoGLM-Phone-9B"
echo ""
echo "=============================================="
echo "  故障排查"
echo "=============================================="
echo ""
echo "• 设备未找到：adb kill-server && adb connect 设备 IP:5555"
echo "• 模块错误：cd ${INSTALL_DIR} && pip install -e ."
echo "• 输入失败：安装 ADB Keyboard APK"
echo ""
echo "=============================================="
echo ""
log_info "祝您使用愉快！🎉"
