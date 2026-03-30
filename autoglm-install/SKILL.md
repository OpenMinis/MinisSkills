---
name: autoglm-install
version: 4.0.0
description: >
	安装和配置 AutoGLM Android Phone Agent
	当用户说"安装 AutoGLM"、"设置 AutoGLM"、"控制安卓手机"等控制手机类时触发技能，
	自动执行完整部署并创建快捷脚本。
---

# AutoGLM Phone Agent 安装与使用

一键安装 **AutoGLM** —— AI 驱动的手机自动化框架，通过自然语言指令操作手机应用。

## 🚀 快速开始

### 一键安装（交互式）

```sh
/var/minis/skills/autoglm-install/scripts/install.sh
```

**安装流程**：
1. ✅ 自动下载项目到 `/root/AutoGLM`
2. ✅ 创建 Python 虚拟环境
3. ✅ 安装所有依赖
4. 🔑 **交互式配置 API Key**（可稍后在 `.env` 中填写）
5. ✅ 自动检测 ADB 设备并配置
6. ✅ 生成配置文件 `.env` 和快捷脚本 `aglm.sh`

## 💻 使用方式

### 快捷命令（推荐）

安装后直接使用 `aglm.sh`：

```sh
# 检查状态
/root/aglm.sh "操作需求"
```

### 自定义 API 配置

```sh
# 使用智谱 API
python3 quickstart.py \
  --base-url https://open.bigmodel.cn/api/paas/v4 \
  --model autoglm-phone-9b \
  --apikey YOUR_KEY \
  "测试任务"

# 使用自定义模型
python3 quickstart.py \
  --base-url https://api-inference.modelscope.cn/v1 \
  --model ZhipuAI/AutoGLM-Phone-9B \
  --apikey YOUR_KEY \
  "检查当前屏幕"
```

### 多设备支持

```sh
# 指定设备 ID
python3 quickstart.py -d "emulator-5554" "打开抖音"
python3 quickstart.py -d "ip:port" "打开京东"
```

## ⚙️ 配置说明

### 自动生成的配置文件

安装完成后，所有配置保存在 `/root/AutoGLM/.env`：

```env
# AutoGLM Configuration
AUTOGLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4
AUTOGLM_MODEL=autoglm-phone-9b
AUTOGLM_API_KEY=your-api-key-here
DEVICE_ID=ip:port
```

**重要**：首次安装时会提示输入 API Key，如果跳过可在 `.env` 中手动填写。

### 环境变量（可选）

在 `~/.bashrc` 中添加：

```bash
export AUTOGLM_BASE_URL="https://open.bigmodel.cn/api/paas/v4"
export AUTOGLM_MODEL="autoglm-phone"
export AUTOGLM_API_KEY="your-api-key-here"
export DEVICE_ID="ip:port"
```

## 🔑 API 密钥获取

### 方式 1: 智谱 BigModel（推荐中文场景）

1. 访问：https://bigmodel.cn/
2. 注册账号并实名认证
3. 进入控制台 → API Key
4. 复制 Key 填入配置

### 方式 2: 使用自定义模型

1. 准备APIurl+APIkey
2. 模型id(必须使用图片识别能力的)
## 🔍 故障排查

| 问题 | 现象 | 解决方法 |
|------|------|---------|
| 设备未找到 | `No output from dumpsys window` | `adb kill-server && adb connect IP:PORT` |
| 连接超时 | `Operation timed out` | `ping -c 3 IP` 检查设备在线 |
| 模块导入错误 | `ModuleNotFoundError` | `cd /root/AutoGLM && pip install -e .` |
| 文本输入失败 | 输入无响应 | 安装 ADB Keyboard APK |
| API Key 无效 | `401 Unauthorized` | 检查 Key 是否正确或重新生成 |

### 文本输入失败解决

```sh
# 方法 1: 安装 ADB Keyboard（推荐）
curl -L https://github.com/senzhk/ADBKeyBoard/raw/master/ADBKeyboard.apk -o adb_keyboard.apk
adb install adb_keyboard.apk

# 方法 2: 启用其他输入法
adb shell ime enable com.iflytek.inputmethod/.FlyIME
```

## 📱 手机端准备

- **Android**: Android 7.0+，需开启 USB 调试
- **HarmonyOS**: NEXT 版本以上，需启用 HDC 调试
- **iOS**: 需配置 WebDriverAgent（参考 iOS 专用文档）

### 开启调试步骤

1. 开发者模式：设置 → 关于手机 → 版本号（连续点击 7 次）
2. USB 调试：设置 → 开发者选项 → USB 调试 → 启用
3. 无线调试：设置 → 开发者选项 → 无线调试 → 启用
4. 安装 ADB Keyboard：设置 → 输入法 → 启用

## 🧪 测试任务

验证安装是否成功：

```sh
cd /root/AutoGLM && python3 quickstart.py "检查当前屏幕状态"
```

预期输出：
```
✅ 任务完成!
当前运行的是：**系统桌面（Home）**
从截图可以看到...
```

## 📚 参考资源

- [完整使用指南](minis://skills/autoglm-install/references/README.md)
- [GitHub 仓库](https://github.com/zai-org/Open-AutoGLM)
- [模型下载](https://modelscope.cn/models/ZhipuAI/AutoGLM-Phone-9B)
- [智谱 API 文档](https://docs.bigmodel.cn/cn/api/introduction)
