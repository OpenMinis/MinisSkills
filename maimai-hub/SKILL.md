---
name: maimai-hub
description: 读取脉脉（maimai.cn）同事圈和职言数据。支持：指定公司同事圈帖子、全站职言 Feed（热门/最新/关注）、同事圈人气排行榜、通过公司名查找 webcid。当用户提到"脉脉"、"同事圈"、"职言"、"maimai"、"maimai-hub"，或任何需要读取脉脉内容的场景，必须触发本技能。
---

# maimai-hub

## 认证流程

每次使用前，通过 `browser_use get_cookies` 获取最新 Cookie，**必须在桌面版页面获取**（移动版缺少 csrftoken）：

```
1. browser_use set_user_agent → desktop_safari
2. browser_use navigate → https://maimai.cn/web/search_center
3. browser_use get_cookies → 存入 env 文件
4. 确认 env 文件中有 COOKIE_CSRFTOKEN（否则重试步骤2-3）
```

ENV 文件路径示例：`/var/minis/offloads/env_cookies_maimai_cn_XXXXXXXX.sh`

## 同事圈降级方案（API 不可用时）

当脚本返回空数组或 HTTP 404 时，自动切换为**浏览器直接读取页面内容**：

```
同事圈页面 URL 格式：
https://maimai.cn/company/gossip_discuss?webcid=<WEBCID>

注意：旧路径 /web/gossip_discuss 和 /community/gossip_discuss 均已 404，
必须用 /company/gossip_discuss
```

**降级步骤：**
```
1. browser_use navigate → https://maimai.cn/company/gossip_discuss?webcid=<WEBCID>
2. 滚动多次加载更多内容（scroll down × 4~6，每次 800px）
3. browser_use get_readable 或 execute_js 提取帖子文本：
   document.querySelectorAll('[class*="content"],[class*="text"],[class*="body"]')
   过滤条件：长度 15~800，排除"脉脉"/"违法"/"同事圈人气"等噪音
4. 对提取结果去重后汇总总结
```

## 脚本调用

脚本：`/var/minis/skills/maimai-hub/scripts/maimai.py`

```bash
# 同事圈帖子（需是该公司员工）
python3 /var/minis/skills/maimai-hub/scripts/maimai.py gossip_circle \
  --webcid 9AG14xzt --count 20 --env <ENV_FILE>

# 通过公司名查同事圈（自动查 webcid）
python3 /var/minis/skills/maimai-hub/scripts/maimai.py gossip_circle \
  --company 蚂蚁集团 --count 20 --env <ENV_FILE>

# 全站职言 Feed
python3 /var/minis/skills/maimai-hub/scripts/maimai.py gossip_feed \
  --tab hot --count 20 --env <ENV_FILE>
  # tab: hot(热门) | new(最新) | follow(关注) | recommend(推荐)

# 同事圈人气排行榜（获取热门公司 webcid）
python3 /var/minis/skills/maimai-hub/scripts/maimai.py circle_rank \
  --env <ENV_FILE>

# 通过公司名查 webcid
python3 /var/minis/skills/maimai-hub/scripts/maimai.py search_company \
  --name 字节跳动 --env <ENV_FILE>
```

## webcid 获取方式

优先级：
1. **用户提供 URL** → 正则提取 `webcid=([A-Za-z0-9]+)`
2. **当前用户所在公司** → 访问 `https://maimai.cn/web/search_center` 后执行 JS：
   ```js
   window.share_data.data.mycard.web_cid  // 直接返回 webcid，同时 .company 是公司全称
   ```
3. **公司名匹配** → 脚本内置缓存 + 动态查排行榜（`circle_rank` 命令）

同事圈页面 URL（用于浏览器降级）：`https://maimai.cn/company/gossip_discuss?webcid=<WEBCID>`

内置 webcid 缓存（主要大厂）：

| 公司 | webcid |
|------|--------|
| 字节跳动 | jYZTTwkX |
| 拼多多 | 1cDwhLvjW |
| 腾讯 | 167PEUToR |
| 阿里巴巴 | EnT6guJz |
| 蚂蚁集团 | 9AG14xzt |
| 百度 | mWqfo5EX |
| 美团 | 5DDx3ANi |
| 小米 | KvzN4IGA |
| 京东 | SJdjsQ5S |
| 快手 | RO3MvtaT |

## 权限说明

- **同事圈**：仅限该公司员工访问，返回 `error_code: 21003` 表示无权限
- **全站职言**：所有登录用户均可访问
- **排行榜**：所有登录用户均可访问

## 输出格式

脚本返回 JSON，每条帖子字段：`id, time, text, likes, cmts, spreads, ip_loc`

总结时按热度（likes+cmts）排序，归纳主要话题，不要逐条罗列原文。

## 常见问题

- **返回空数组**：同事圈无权限（非该公司员工），切换到全站职言
- **csrftoken 缺失**：确保用桌面版 UA 访问后再 get_cookies
- **公司名找不到 webcid**：提示用户直接提供同事圈 URL（`https://maimai.cn/company/gossip_discuss?webcid=xxx`）
- **API 返回空 / 404**：自动切换浏览器降级方案，见「同事圈降级方案」章节
