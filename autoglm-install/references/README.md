# AutoGLM Phone Agent 完整使用指南

## 📚 目录

1. [环境准备](#环境准备)
2. [完整安装流程](#完整安装流程)
3. [配置说明](#配置说明)
4. [使用示例](#使用示例)
5. [故障排查](#故障排查)
6. [API 密钥获取](#api-密钥获取)

---

## 环境准备

### 系统要求

| 组件 | 版本 | 状态 |
|------|------|------|
| Python | ≥ 3.10 | ✅ 自动检测 |
| ADB | 最新版 | ✅ 已安装 |
| pip | 最新版 | ✅ 已安装 |

### 手机端要求

- **Android**: Android 7.0+，需开启 USB 调试
- **HarmonyOS**: NEXT 版本以上，需启用 HDC 调试
- **iOS**: 需配置 WebDriverAgent（参考 iOS 专用文档）

---

## 完整安装流程

### 步骤 1：下载项目

```bash
cd /root/AutoGLM
curl -sL https://github.com/zai-org/Open-AutoGLM/archive/refs/heads/main.zip -o project.zip
unzip -q project.zip
mv Open-AutoGLM-main/* .
rm -rf project.zip Open-AutoGLM-main
```

### 步骤 2：安装依赖

```sh
pip install Pillow>=12.0.0 openai>=2.9.0 requests>=2.31.0
pip install -e .
```

### 步骤 3：验证安装

```sh
python3 quickstart.py --help
```

---

## 配置说明

### 环境变量

在 `~/.bashrc` 中添加（可选）：

```bash
export AUTOGLM_BASE_URL="https://open.bigmodel.cn/api/paas/v4"
export AUTOGLM_MODEL="autoglm-phone"
export AUTOGLM_API_KEY="your-api-key-here"
export DEVICE_ID="your-ip:port"
source ~/.bashrc
```

### 配置文件

```sh
# /root/AutoGLM/.env
AUTOGLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4
AUTOGLM_MODEL=autoglm-phone
AUTOGLM_API_KEY=sk-xxx
DEVICE_ID=ip:port
```

---

## 使用示例

### 基础用法

```sh

# 执行操作
python3 quickstart.py "打开小红书搜索美食"
python3 quickstart.py "打开高德地图导航回家"

```

### 自定义 API 端点

```sh
# 使用智谱 API
python3 quickstart.py \
  --base-url https://open.bigmodel.cn/api/paas/v4 \
  --model autoglm-phone-9b \
  --apikey YOUR_KEY \
  "测试"

# 使用自定义模型
python3 quickstart.py \
  --base-url ‘your-api-key-here’ \
  --model ‘自定义模型,默认autoglm-phone-9b‘ \
  "检查当前屏幕"
```

### 多设备支持

```sh
# 指定设备 ID
python3 quickstart.py -d "emulator-5554" "打开抖音"
python3 quickstart.py -d "ip:5555" "打开京东"
```

---

## 故障排查

### 问题 1: 设备未找到

**现象**: `No output from dumpsys window`

**解决**:
```sh
adb kill-server
adb start-server
adb connect "ip:port"
```

### 问题 2: 连接超时

**现象**: `Operation timed out`

**解决**:
```sh
# 检查设备是否在线
ping -c 3 "ip"

# 重启 ADB TCP 服务（需要 USB 先连一次）
adb tcpip port
adb connect ip:port
```

### 问题 3: 模块导入错误

**现象**: `ModuleNotFoundError: No module named 'phone_agent'`

**解决**:
```sh
cd /root/AutoGLM
pip uninstall -y phone-agent
pip install -e .
```

### 问题 4: 文本输入失败

**原因**: 缺少 ADB Keyboard

**解决**:
```sh
# 方法 1: 安装 ADB Keyboard（推荐）
curl -L https://github.com/senzhk/ADBKeyBoard/raw/master/ADBKeyboard.apk -o adb_keyboard.apk
adb install adb_keyboard.apk

# 方法 2: 在设备上手动设置输入法
adb shell ime enable com.iflytek.inputmethod/.FlyIME
```

### 问题 5: API Key 无效

**现象**: `401 Unauthorized` 或类似错误

**解决**: 
1. 检查 API Key 是否正确
2. 访问智谱平台验证 Key 有效性
3. 重新生成新的 API Key

---

## API 密钥获取

### 方式 1: 智谱 BigModel（推荐中文场景）

1. 访问：https://bigmodel.cn/
2. 注册账号并实名认证
3. 进入控制台 → API Key
4. 复制 Key 填入环境变量或使用 `--apikey` 参数

### 方式 2: ModelScope 魔搭社区

1. 访问：https://modelscope.cn/
2. 注册并登录
3. 申请 AutoGLM-Phone-9B 模型权限
4. 获取 API Key

### 方式 3: 本地部署（高级用户）

如需本地部署模型，需要：
- NVIDIA GPU (建议 24GB+ 显存)
- 安装 vLLM 或 SGLang
- 下载约 20GB 的模型文件

详细请参考：https://github.com/zai-org/Open-AutoGLM

---

## 测试任务

运行以下命令验证安装是否成功：

```sh
cd /root/AutoGLM && \
python3 quickstart.py "检查当前屏幕状态"
```

预期结果：AI 会分析并返回当前手机屏幕的内容描述。

如果看到类似这样的输出，说明安装成功：

```
✅ 任务完成!
当前运行的是：**系统桌面（Home）**
从截图可以看到...
```

---

## 相关链接

- 官方仓库：https://github.com/zai-org/Open-AutoGLM
- 模型下载：https://modelscope.cn/models/ZhipuAI/AutoGLM-Phone-9B
- 智谱 API 文档：https://docs.bigmodel.cn/cn/api/introduction
- 常见问题：见项目根目录 README.md

---

## 下一步

安装完成后，您可以：

1. **尝试基本命令**:
   ```bash
   python3 quickstart.py "打开微信"
   python3 quickstart.py "打开小红书搜索美食"
   ```

2. **探索高级功能**:
   - 批量任务执行
   - 自定义回调函数
   - 工作流自动化

3. **参与社区**:
   - 加入微信社区讨论
   - 贡献代码或报告问题
   - 分享您的使用案例

祝您使用愉快！🎉
