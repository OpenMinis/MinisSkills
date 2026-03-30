# 豪猪 SMS 接码工具 - 快速使用指南

## 📦 技能结构

```
haozhu-sms/
├── SKILL.md                    # 主文档（触发后加载）
├── references/
│   └── api_docs.md            # 完整 API 接口文档
└── scripts/
    ├── sms_client.py          # 全功能客户端（获取 + 等待 + 释放）
    ├── get_phone_only.py      # 快速获取号码
    ├── check_sms.py           # 查询短信内容
    └── release_phone.py       # 释放号码
```

---

## 🚀 常用场景示例

### 场景一：自动获取并等待验证码（最常用）

```bash
python3 /var/minis/skills/haozhu-sms/scripts/sms_client.py 59550 1
```

**说明**：
- `59550`: 项目 ID（已验证可用）
- `1`: 中国移动（可改 5=联通，9=电信，14=广电）
- 脚本会自动获取号码 → 轮询验证码 → 输出结果

---

### 场景二：仅获取号码（用于手动操作）

```bash
phone=$(python3 /var/minis/skills/haozhu-sms/scripts/get_phone_only.py 59550 1)
echo "获取到号码：$phone"
# 然后在目标网站输入 $phone 接收验证码
```

**说明**：
- 纯输出手机号，方便管道处理
- 适合在浏览器操作时获取临时号码

---

### 场景三：查询指定号码的短信

```bash
python3 /var/minis/skills/haozhu-sms/scripts/check_sms.py 59550 18290252747
```

**输出示例**：
```
📱 原始短信内容:
【智谱 AI】您的验证码为 207135，请于 3 分钟内使用...

🎯 6 位验证码：207135
```

---

### 场景四：释放号码（节省费用）

```bash
python3 /var/minis/skills/haozhu-sms/scripts/release_phone.py 18290252747
```

---

## 🔧 环境变量配置（可选）

如果需要使用自己的账号，设置环境变量：

```bash
export HAOZHU_TOKEN="你的 token"
export HAOZHU_API_KEY="你的 api_key"
```

**内置默认账号**（已验证可用）：
- Token: `12979f4eba...` (32 位字符串)
- 余额：¥3.92
- 类型：开发用户（10% 折扣）

---

## ⚠️ 常见问题

### Q: code=-101 "No Input" 错误？

**原因**：API 限流保护  
**解决**：等待 30 秒后重试

```bash
sleep 30 && python3 scripts/get_phone_only.py 59550 1
```

### Q: code=-3 "没有库存" 错误？

**原因**：当前运营商号码用完了  
**解决**：更换其他运营商

```bash
python3 scripts/get_phone_only.py 59550 5  # 改成联通
```

### Q: code=-1 "没有找到项目 ID"？

**原因**：项目已失效  
**解决**：使用项目 59550（已验证可用）

---

## 📊 运营商参数对照表

| 参数值 | 运营商 | 备注 |
|--------|--------|------|
| 1 | 中国移动 | ✅ 最常用 |
| 5 | 中国联通 | ✅ 备选 |
| 9 | 中国电信 | ✅ 备选 |
| 14 | 中国广电 | ⚠️ 新运营商 |

---

## 💡 最佳实践

1. **优先使用项目 59550** - 已验证稳定可用
2. **避免频繁调用** - 每次请求间隔至少 3 秒
3. **及时释放号码** - 未收到验证码时主动释放节省费用
4. **遇到限流不慌张** - 等 30 秒即可恢复
5. **建议配合 curl 测试** - curl 比 Python requests 更不容易触发限流

---

## 🔍 调试技巧

### 方法一：直接使用 curl 测试（推荐）

```bash
TOKEN="12979f4ebab7cfffd5239df6b569d57b6ba4174db474de268754d095fffb40660da9a277a6ad6636f21a80dac7e32f811c921eed962625876572a81c2e15f0b4a7b497091f5fb39ce9dad5e8c5c808a783fe68068a574dcc"

# 获取号码
curl -s "https://api.haozhuyun.com/sms/?action=getPhone&_id=59550&sid=59550&isp=1&token=${TOKEN}"

# 查询短信
curl -s "https://api.haozhuyun.com/sms/?action=getMessage&_id=59550&sid=59550&phone=18290252747&token=${TOKEN}"
```

### 方法二：开启调试模式

修改脚本中的 `HEADERS` 添加更多日志：
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

---

## 📝 API 服务器选择

- ✅ **推荐**: `https://api.haozhuyun.com/sms/` (稳定快速)
- ⚠️ **备选**: `https://api.haozhuma.com/sms/` (响应慢)

如需切换服务器，修改脚本开头的 `BASE_URL` 变量即可。
