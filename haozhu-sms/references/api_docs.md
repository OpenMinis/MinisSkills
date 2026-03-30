# 豪猪平台 SMS API 接口文档

## 📍 服务器地址

- **推荐**：`https://api.haozhuyun.com/sms/`（稳定）
- **备选**：`https://api.haozhuma.com/sms/`（响应慢）

## 🔐 认证方式

所有接口需携带 `token` 参数（登录获取）或 `apkey` 参数。

### 示例 Token（已验证可用）
```
Token: 12979f4ebab7cfffd5239df6b569d57b6ba4174db474de268754d095fffb40660da9a277a6ad6636f21a80dac7e32f811c921eed962625876572a81c2e15f0b4a7b497091f5fb39ce9dad5e8c5c808a783fe68068a574dcc
API Key: 3a216c7fff1b1894fd7ff19f904813ca1f1f56006cf5e9f5af83e5d46ebd17bf
```

---

## 1. 登录接口 `/login/`

**请求**：
```
GET /login/?username=<账号>&password=<密码>
```

**响应成功**：
```json
{
  "code": 0,
  "msg": "success",
  "data": {
    "uid": 1234,
    "user": "example_user",
    "balance": 3.92,
    "type": 2
  }
}
```

---

## 2. 获取 Token `/get_token/`

**请求**：
```
GET /get_token/?username=<账号>&password=<密码>&time=60
```

**说明**：
- `time`: 过期时间（秒），最大 3600
- 开发用户默认折扣 10%

**响应成功**：
```json
{
  "code": 0,
  "msg": "success",
  "data": {
    "token": "<32 位 token 字符串>",
    "overdue": 3600
  }
}
```

---

## 3. 查询账户信息 `/query_account/`

**请求**：
```
GET /query_account/?action=queryAccount&token=<token>
```

**响应成功**：
```json
{
  "code": 0,
  "msg": "success",
  "data": {
    "uid": 1234,
    "user": "example_user",
    "balance": "¥3.92",
    "type": 2,
    "max_isp": 100,
    "remark": "开发用户"
  }
}
```

---

## 4. 查询项目列表 `/list_project/`

**请求**：
```
GET /list_project/?action=listProject&token=<token>&_id=-2
```

**响应成功**：
```json
{
  "code": 0,
  "msg": "success",
  "data": [
    {"id": "59550", "name": "测试项目", "isp": "1,5,9", "price": "0.3"},
    ...
  ]
}
```

---

## 5. 获取手机 `/get_phone/` ⭐核心接口

**请求**：
```
GET /get_phone/?action=getPhone&_id=<项目 ID>&sid=<项目 ID>&isp=<运营商>&token=<token>
```

**参数**：
| 参数 | 说明 | 示例 |
|------|------|------|
| `_id` | 项目 ID | 59550 |
| `sid` | 项目 ID（同上） | 59550 |
| `isp` | 运营商 | 1=移动，5=联通，9=电信，14=广电 |
| `country_qu` | 国家区号 | +86（中国） |
| `token` | 认证 Token | （必填） |

**响应成功**：
```json
{
  "code": 0,
  "msg": "成功",
  "sid": "59550",
  "shop_name": "59550",
  "country_name": "中国大陆",
  "country_code": "cn",
  "country_qu": "+86",
  "phone": "18290252747",
  "sp": "移动",
  "phone_gsd": "重庆"
}
```

**错误码**：
- `-1`: 没有找到项目 ID
- `-2`: 手机号码不存在于号码池
- `-3`: 手机号码池没有库存
- `-5`: ISP 不在允许范围内
- `-8`: 账户余额不足
- `-101`: Token 无效或不存在（实际是限流）

---

## 6. 接收短信 `/get_message/` ⭐核心接口

**请求**：
```
GET /get_message/?action=getMessage&_id=<项目 ID>&sid=<项目 ID>&phone=<手机号>&token=<token>
```

**参数**：
| 参数 | 说明 | 示例 |
|------|------|------|
| `_id` | 项目 ID | 59550 |
| `sid` | 项目 ID（同上） | 59550 |
| `phone` | 目标手机号 | 18290252747 |
| `token` | 认证 Token | （必填） |

**响应成功（有短信）**：
```json
{
  "code": 0,
  "msg": "success",
  "sms": "【智谱 AI】您的验证码为 207135，请于 3 分钟内使用，若非本人操作，请忽略本短信。",
  "yzm": "207135"
}
```

**响应成功（无短信）**：
```json
{
  "code": 0,
  "msg": "success",
  "sms": ""
}
```

**轮询建议**：
- 每 5 秒查询一次
- 最多等待 60 秒
- 超过超时未收到可释放号码重试

---

## 7. 释放号码 `/cancel_recv/`

**请求**：
```
GET /cancel_recv/?action=cancelRecv&phone=<手机号>&token=<token>
```

**响应成功**：
```json
{
  "code": 0,
  "msg": "success"
}
```

**注意事项**：
- 主动释放可节省费用
- 如果已收到验证码仍会收费
- 不主动释放也会自动到期释放

---

## 8. 查询号码状态 `/status_phone/`

**请求**：
```
GET /status_phone/?action=statusPhone&phone=<手机号>&token=<token>
```

**用途**：
- 查询号码是否还在租期内
- 检查号码是否已收到短信

---

## 9. 删除消息 `/del_sms/`

**请求**：
```
GET /del_sms/?action=delSms&phone=<手机号>&token=<token>
```

**用途**：
- 清空指定号码的消息记录
- 用于测试时重置状态

---

## 常见错误码汇总

| 错误码 | 含义 | 解决方案 |
|--------|------|----------|
| 0 | 成功 | - |
| -1 | 没有找到项目 ID | 更换有效的项目 ID |
| -2 | 手机号不存在 | 重新获取新号码 |
| -3 | 号码池无库存 | 换其他运营商重试 |
| -5 | ISP 不允许 | 检查项目支持的运营商 |
| -8 | 余额不足 | 充值或释放号码 |
| -101 | Token 无效 | 等待 30 秒重试（实为限流） |
| 429 | Too Many Requests | HTTP 级别限流，等待 30 秒 |

---

## 使用建议

### ✅ 最佳实践

1. **优先使用 `api.haozhuyun.com`** —— 更稳定
2. **避免高频调用** —— 每次间隔 3-5 秒
3. **及时释放号码** —— 节省费用
4. **设置 User-Agent 头** —— 避免被识别为脚本
5. **重试机制** —— 限流时指数退避（30 秒、60 秒、120 秒）

### ⚠️ 注意事项

1. **开发用户有 10% 折扣**
2. **未收到短信不收费**
3. **Token 有效期 3600 秒**
4. **每个项目有不同价格和运营商限制**
