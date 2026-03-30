---
name: haozhu-sms
version: 1.0.0
description: 豪猪平台短信接码工具。当用户需要接收验证码、获取临时手机号、短信接码、SMS verification、注册账号时需要验证码时触发。支持自动获取号码、轮询验证码、释放号码等完整流程。API Token 和 Key 从环境变量 HAOZHU_TOKEN 和 HAOZHU_API_KEY 读取，或使用默认账号（余额¥3.92）。常用项目 ID：59550（移动 - 重庆，已验证可用）。运营商参数：1=移动，5=联通，9=电信，14=广电。
server_preferred: https://api.haozhuyun.com
---

# 豪猪平台短信接码技能

快速接入豪猪平台 API 实现短信验证码接收功能，适用于各类需要手机注册的账号创建任务。

## 🚀 快速开始

### 1. 一键获取号码并等待验证码
```bash
python3 /var/minis/skills/haozhu-sms/scripts/sms_client.py 59550 1
```
参数说明：`59550`=项目 ID，`1`=移动运营商

### 2. 仅获取号码（不等待）
```bash
python3 /var/minis/skills/haozhu-sms/scripts/get_phone_only.py 59550 1
```

### 3. 手动查询指定号码的验证码
```bash
python3 /var/minis/skills/haozhu-sms/scripts/check_sms.py 59550 18290252747
```

## 📋 核心脚本清单

| 脚本 | 功能 | 使用场景 |
|------|------|----------|
| `sms_client.py` | 获取号码 + 轮询验证码 + 自动释放 | 完整的接码流程 |
| `get_phone_only.py` | 仅获取号码 | 需要手动处理短信时 |
| `check_sms.py` | 查询指定号码短信 | 已知号码查验证码 |
| `release_phone.py` | 释放号码 | 主动提前释放节省费用 |

## 🔧 配置认证信息

### 方式一：环境变量（推荐）
```bash
export HAOZHU_TOKEN="你的 token"
export HAOZHU_API_KEY="你的 api_key"
```

### 方式二：使用默认账号
脚本内置了默认账号（余额¥3.92），可直接使用无需配置。

## 📱 运营商参数表

| 参数值 | 运营商 |
|--------|--------|
| `1` | 中国移动 |
| `5` | 中国联通 |
| `9` | 中国电信 |
| `14` | 中国广电 |

## ⚠️ 重要注意事项

### API 限流保护
- 短时间频繁调用会触发 `-101` 错误或 `HTTP 429`
- 解决方案：脚本已内置延迟控制（每次请求间隔 3-5 秒）
- 如遇限流，等待 30 秒后重试

### 服务器选择
- ✅ **推荐**: `https://api.haozhuyun.com`（稳定）
- ⚠️ 备选：`https://api.haozhuma.com`（响应慢）

### 可用项目 ID
- ✅ **59550** - 已验证可用（移动/联通/电信）
- ❌ 参考库中其他 ID（1000/2000/3000 等）大多已失效

## 🔄 工作流程示例

```
1. 获取号码 → getPhone(sid=59550, isp=1)
   ↓ 成功返回：18290252747

2. 目标网站发送验证码到该号码

3. 轮询验证码 → getMessage(sid=59550, phone=18290252747)
   ↓ 成功返回：207135

4. 使用验证码完成注册

5. 释放号码 → cancelRecv(phone=18290252747) [可选]
```

## 🐛 常见问题

### code=-101 "Token 无效或不存在"
实际是 API 限流导致。等待 30 秒后重试即可。

### code=-1 "没有找到项目 ID"
项目 ID 已失效。请使用项目 59550。

### code=-3 "手机号码池没有库存"
当前运营商无可用号码。尝试更换其他运营商（如把 `isp=1` 改为 `isp=5`）。

## 📚 API 接口说明

完整 API 文档见：[`references/api_docs.md`](minis://skills/haozhu-sms/references/api_docs.md)

主要接口：
- `getPhone` - 获取可用号码
- `getMessage` - 查询收到的短信
- `cancelRecv` - 释放号码
- `accountInfo` - 查询账户信息

## 💰 计费说明

- 开发用户享受 **10% 折扣**
- 按成功接收短信计费，未收到不收费
- 及时释放号码可节省费用
