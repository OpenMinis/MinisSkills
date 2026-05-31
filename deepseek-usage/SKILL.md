---
name: deepseek-usage
description: >
  查询 DeepSeek API 用量（余额、本月消费、各模型 Token 明细、日维度明细、缓存命中率）。
  通过 browser_use 访问 DeepSeek 开放平台，自动登录并导出月度数据。
  需要用户自行配置 DeepSeek 账号到本地环境变量。
  当用户说"查用量"、"看token消耗"、"查消费"、"余额还剩多少"、"今天跑了多少"时触发。
version: 1.1.0
compatibility: Requires python3. DEEPSEEK_EMAIL and DEEPSEEK_PASSWORD env vars.
---

# DeepSeek API 用量查询

> ⚠️ **安全提示**
> 本技能需要 DeepSeek 登录凭据才能工作。
> 凭据仅存储在本地环境变量中，**Minis 不会上传到任何服务器**。
> 如果你不信任此方式，请删除本技能或不要设置凭据。

## 前置配置（首次使用，只需一次）

### 1. 设置环境变量

在 Minis 设置 → 环境变量中添加以下两个变量：

| 变量名 | 说明 | 示例值 |
|--------|------|--------|
| `DEEPSEEK_EMAIL` | 你的 DeepSeek 平台登录邮箱 | `user@example.com` |
| `DEEPSEEK_PASSWORD` | 你的 DeepSeek 平台登录密码 | `your_password_here` |

🔗 [点此打开环境变量设置](minis://settings/environments)

> 如果你的账号使用 Google/微信等第三方登录，则无法使用本技能。

### 2. 验证配置

```bash
[ -n "$DEEPSEEK_EMAIL" ] && [ -n "$DEEPSEEK_PASSWORD" ] && echo "已配置" || echo "未配置"
```

## 查询流程（仅需 2 个 tool call）

### 第 1 步：导航并确保登录（1 个 tool call）

```yaml
动作:
  - set_user_agent: desktop_chrome
  - navigate: https://platform.deepseek.com/usage
  - 如果未登录，从环境变量填充 DEEPSEEK_EMAIL / DEEPSEEK_PASSWORD 并提交登录
  - wait_for_dom_stable
```

### 第 2 步：一键执行完整 JS 脚本（1 个 execute_js）

以下 JS 脚本完成**取 Token → 下载 zip → 解压 → 解析 CSV → 输出**全部逻辑。

将整个 JS 脚本作为 `execute_js --script` 的参数一次性执行。

```js
(async () => {
  // === 获取汇总文本 ===
  // 用 get_readable 提取（在 execute_js 外部完成）

  // === 获取 Token ===
  const token = JSON.parse(localStorage.getItem('userToken')).value;
  if (!token) return JSON.stringify({ error: 'no_token' });

  // === 下载 zip ===
  const resp = await fetch('https://platform.deepseek.com/api/v0/usage/export?month=5&year=2026', {
    headers: { 'Authorization': 'Bearer ' + token }
  });
  const blob = await resp.blob();

  // === 加载 JSZip ===
  const script = document.createElement('script');
  script.src = 'https://cdnjs.cloudflare.com/ajax/libs/jszip/3.10.1/jszip.min.js';
  await new Promise(r => { script.onload = r; document.head.appendChild(script); });

  // === 解压 ===
  const zip = await JSZip.loadAsync(blob);
  const costText = await zip.file('cost-2026-5.csv').async('text');
  const amountText = await zip.file('amount-2026-5.csv').async('text');

  // === 解析 cost（费用）===
  // ⚠️ 表头: user_id, utc_date, model, wallet_type, cost, currency
  const costLines = costText.trim().split('\n').slice(1);
  const modelCost = {};
  let totalCost = 0;
  for (const line of costLines) {
    const p = line.split(',');
    const model = p[2], cost = parseFloat(p[4]) || 0;
    modelCost[model] = (modelCost[model] || 0) + cost;
    totalCost += cost;
  }

  // === 解析 amount（用量，按需筛选日期）===
  // ⚠️ 表头: user_id, utc_date, model, api_key_name, api_key(敏感!), type, price, amount
  // ⚠️ 安全警告：第5列是 api_key 明文，禁止打印整行！必须用索引引用。
  const allLines = amountText.trim().split('\n').slice(1);

  // 筛选规则：用户问当日用量 → 筛当天；用户问当月用量 → 全月
  // 默认当日。如需当日，取消下面这行的注释：
  // const targetDate = '当前日期的 YYYY-MM-DD 格式';
  // const filteredLines = targetDate ? allLines.filter(l => l.split(',')[1] === targetDate) : allLines;
  const filteredLines = allLines; // 默认全月

  const models = {};
  for (const line of filteredLines) {
    const p = line.split(',');
    const model = p[2], type = p[5], amount = parseInt(p[7]) || 0;
    if (!models[model]) models[model] = { requests: 0, cache_hit: 0, cache_miss: 0, output: 0 };
    if (type === 'request_count') models[model].requests += amount;
    else if (type === 'input_cache_hit_tokens') models[model].cache_hit += amount;
    else if (type === 'input_cache_miss_tokens') models[model].cache_miss += amount;
    else if (type === 'output_tokens') models[model].output += amount;
  }

  // === 汇总输出 ===
  let result = '';
  let gr = 0, go = 0, gh = 0, gm = 0;

  for (const [m, d] of Object.entries(models)) {
    const ti = d.cache_hit + d.cache_miss;
    const hr = ti > 0 ? (d.cache_hit / ti * 100).toFixed(1) : '0.0';
    const co = modelCost[m] || 0;
    result += `${m}|${d.requests}|${d.output}|${d.cache_hit}|${d.cache_miss}|${ti}|${hr}|${co.toFixed(2)}\n`;
    gr += d.requests; go += d.output; gh += d.cache_hit; gm += d.cache_miss;
  }

  const ti = gh + gm;
  const hr = ti > 0 ? (gh / ti * 100).toFixed(1) : '0.0';
  result += `TOTAL|${gr}|${go}|${gh}|${gm}|${ti}|${hr}|${totalCost.toFixed(2)}`;

  return result;
})();
```

> ⚠️ 注意：`execute_js` 返回的是包裹在 JSON 中的文本，AI 需要解析 `data.text` 获取实际结果。

### 第 3 步：截图（1 个 tool call，可选）

```yaml
screenshot: 当前页面
```

### 第 4 步：汇报（memory_write 由用户决定）

是否需要将结果写入 daily log **由用户决定**。用户明确要求时才写入。

### 输出格式

**余额：** ¥X.XX | **本月已消费：** ¥X.XX

![用量截图](minis://browser/screenshot_xxx.jpg)

| 模型 | 请求次数 | 输出 Tokens | 缓存命中 | 缓存未命中 | 总输入 Tokens | 缓存命中率 | 费用 |
|------|---------|------------|---------|-----------|-------------|-----------|------|
| deepseek-v4-pro | X | X | X | X | X | X% | ¥X.XX |
| deepseek-v4-flash | X | X | X | X | X | X% | ¥X.XX |
| **总计** | **X** | **X** | **X** | **X** | **X** | **X%** | **¥X.XX** |

## ⚠️ 安全注意事项（必须遵守）

### API Key 泄露风险
amount CSV 第 5 列（索引 4）为 `api_key` 字段，包含用户的 DeepSeek API Key **明文**。

**必须遵守：**
- 解析 CSV 时使用列索引引用（如 `p[2]`、`p[5]`、`p[7]`），不要引用整行
- **禁止**在任何回复、日志或截图中间接展示 api_key 内容
- 如果需要在调试时查看 CSV 内容，只打印表头（第 1 行），不要打印数据行

### 凭据安全
- 邮箱密码存储在 Minis 本地环境变量，不会上传
- localStorage Token 仅当前浏览器 session 有效
- 建议定期修改密码

## 踩坑记录

| 问题 | 原因 | 解决方案 |
|------|------|---------|
| 导出按钮点击无效 | 导出按钮是 `<div>` 不是 `<button>` | 用 `querySelector` 匹配文本"导出"后 `.click()` |
| browser_use fetch 返回 Missing Token | fetch 不携带页面 cookie | 改用 `execute_js` 在页面上下文中执行 fetch |
| JSZip 加载失败 | `import()` 方式不支持 | 用 `document.createElement('script')` 动态加载 CDN |
| CSV 解析出 0 条 | 字段索引猜错 | 先确认表头（amount 8 列，cost 6 列），再按索引引用 |
| amount.csv 含 API Key 明文 | 第 5 列是 api_key | 解析时使用列名引用，不打印整行 |
| minis-browser-use CLI 跨调用状态丢失 | 每次调用是独立进程 | 全 JS 逻辑放在一个 execute_js 中执行，不要跨 navigate/execute_js 传递状态 |
