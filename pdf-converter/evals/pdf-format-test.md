# Markdown 格式综合测试文档

> **用途**：pdf-converter 功能测试 | **日期**：2026-08-08
> **覆盖**：标题、表格、代码、引用、列表、emoji、混合文本
> **说明**：本文件不含任何个人信息，仅用于格式兼容性验证

---

## 一、标题层级测试

### 三级标题
#### 四级标题
##### 五级标题（应降级为普通样式）

---

## 二、复杂表格

### 2.1 数据统计表（多列 + 数字 + 货币）

| 指标 | Q1 | Q2 | Q3 | Q4 | 全年 |
|------|-----|-----|-----|-----|------|
| 营收（万元） | 128.5 | 156.3 | 172.8 | 198.2 | 655.8 |
| 同比增长 | +12.3% | +15.7% | +9.2% | +18.6% | +14.2% |
| 成本（万元） | 89.2 | 95.6 | 98.4 | 105.9 | 389.1 |
| 利润率 | 30.5% | 38.8% | 43.1% | 46.6% | 40.7% |
| 订单数（万单） | 45.2 | 52.8 | 61.5 | 70.3 | 229.8 |

### 2.2 功能对比表（含 emoji 和符号）

| 功能 | 基础版 | 专业版 🚀 | 旗舰版 👑 | 备注 |
|------|:------:|:---------:|:---------:|------|
| 用户数 | 1,000 | 10,000 | 100,000 | 按年计费 |
| 存储空间 | 10 GB | 100 GB | 1 TB | 可扩展 |
| API 调用 | 1,000/天 | 100,000/天 | 无限制 🔥 | 含限流保护 |
| 技术支持 | ❌ 无 | ✅ 工作日 | ✅ 7×24 | 旗舰专属 |
| 数据导出 | CSV | CSV/JSON/XML | 全格式 ⚡ | 含增量同步 |
| 安全审计 | — | 季度报告 | 实时监控 🛡️ | 等保三级 |

### 2.3 混合内容表（中文 + 英文 + 特殊符号）

| 项目 | 描述 | 优先级 | 状态 |
|------|------|--------|------|
| API Gateway 网关升级 | 支持 WebSocket & gRPC 协议，QPS 从 5,000 → 50,000 | P0 | 进行中 60% |
| 缓存层改造 | Redis Cluster → Redis 7.x + 持久化 AOF/RDB | P1 | 已完成 ✅ |
| 数据库迁移 | PostgreSQL 16 + 分库分表（16 个分片） | P1 | 待开始 ⏳ |
| 监控告警 | Prometheus + Grafana，告警延迟 <30s | P2 | 进行中 45% |
| CI/CD 流水线 | GitHub Actions → 自建 Jenkins，构建 <10min | P2 | 设计中 |

---

## 三、代码块

### 3.1 Python

```python
import asyncio
from dataclasses import dataclass
from typing import Optional

@dataclass
class Config:
    """Configuration object with validation."""
    host: str = "127.0.0.1"
    port: int = 8080
    debug: bool = False
    retries: int = 3

    def validate(self) -> bool:
        if not 0 < self.port < 65536:
            raise ValueError(f"Invalid port: {self.port}")
        if self.retries < 0:
            raise ValueError("Retries cannot be negative")
        return True


async def fetch(url: str, config: Config) -> Optional[bytes]:
    """Fetch a URL with retry logic."""
    for attempt in range(config.retries + 1):
        try:
            print(f"Attempt {attempt + 1} fetching {url}...")
            return await _http_get(url, timeout=10)
        except TimeoutError:
            if attempt == config.retries:
                raise
            await asyncio.sleep(2 ** attempt)  # exponential backoff
    return None
```

### 3.2 JavaScript

```javascript
// Rate limiter with token bucket algorithm
class TokenBucket {
  constructor(capacity, refillRate) {
    this.capacity = capacity;    // max tokens
    this.tokens = capacity;
    this.refillRate = refillRate; // tokens per second
    this.lastRefill = Date.now();
  }

  take(count = 1) {
    this._refill();
    if (this.tokens >= count) {
      this.tokens -= count;
      return true;
    }
    return false;
  }

  _refill() {
    const now = Date.now();
    const elapsed = (now - this.lastRefill) / 1000;
    this.tokens = Math.min(
      this.capacity,
      this.tokens + elapsed * this.refillRate
    );
    this.lastRefill = now;
  }
}

export { TokenBucket };
```

### 3.3 Bash

```bash
#!/bin/bash
# Deployment script v2.3

set -euo pipefail

APP_DIR="/opt/myapp"
BACKUP_DIR="/backups/$(date +%Y%m%d_%H%M%S)"

echo "🚀 Deploying version ${VERSION:-latest}..."
mkdir -p "$BACKUP_DIR"

# Backup current version
if [ -d "$APP_DIR" ]; then
  cp -r "$APP_DIR" "$BACKUP_DIR/app"
  echo "✅ Backup saved to $BACKUP_DIR"
fi

# Health check
curl -sf http://localhost:8080/health || {
  echo "❌ Health check failed, rolling back..."
  exit 1
}

echo "✨ Deployment complete"
```

### 3.4 SQL

```sql
-- Monthly revenue report
SELECT
    DATE_TRUNC('month', order_date) AS month,
    COUNT(DISTINCT user_id)         AS active_users,
    SUM(total_amount)               AS revenue,
    AVG(order_amount)               AS avg_order,
    ROUND(SUM(total_amount) * 0.15, 2) AS tax_estimate
FROM orders
WHERE order_date >= NOW() - INTERVAL '12 months'
GROUP BY 1
ORDER BY 1 DESC
LIMIT 12;
```

### 3.5 行内代码

使用 `pip install -r requirements.txt` 安装依赖，通过 `python manage.py runserver` 启动开发服务器，
用 `curl -X POST http://localhost:8080/api/v1/items` 测试接口，最后用 `docker compose up -d` 部署。

---

## 四、引用块

> 这是一条普通的引用文字，用于测试引用块的基本渲染效果。

> **多行引用**：第一行内容
> 第二行继续的内容
> 第三行：**加粗** 和 *斜体* 混合的 `行内代码` 示例

> 💡 **最佳实践**：代码评审应当在 PR 合并前完成
> ⚠️ **注意**：生产环境变更必须经过审批流程
> ✅ **已完成**：自动化测试覆盖率提升至 85%

---

## 五、列表测试

### 5.1 无序列表（嵌套）

- 基础设施
  - 计算资源
    - 应用服务器 × 12
    - 数据库服务器 × 4
    - 缓存节点 × 6
  - 网络
    - 负载均衡器（双活）
    - CDN 边缘节点（全球 28 个）
  - 存储
    - 对象存储（冷热分层）
    - 块存储（SSD 高性能）
- 应用服务
  - 用户服务（Java 17 / Spring Boot）
  - 订单服务（Go / gRPC）
  - 支付服务（Python / FastAPI）
- 运维保障
  - 监控告警（Prometheus + Grafana）
  - 日志收集（ELK 集群）
  - 备份恢复（每日全量 + 实时增量）

### 5.2 有序列表

1. 需求分析（2 周）
   - 用户调研
   - 竞品分析
   - 需求文档评审
2. 架构设计（1 周）
   - 技术选型
   - 接口定义
   - 数据库设计
3. 开发实施（8 周）
   - 后端开发（4 周）
   - 前端开发（3 周）
   - 联调测试（1 周）
4. 上线发布（1 周）
   - 灰度发布（10% → 50% → 100%）
   - 性能压测
   - 回滚预案演练

### 5.3 任务清单

- [x] 完成需求文档
- [x] 通过架构评审
- [x] 数据库迁移脚本
- [ ] 接口联调（进行中）
- [ ] 性能优化（QPS ≥ 30,000）
- [ ] 上线前安全检查

---

## 六、Emoji 与符号测试

### 6.1 表情 emoji

🔴 红色圆  🟠 橙色圆  🟡 黄色圆  🟢 绿色圆  🔵 蓝色圆  🟣 紫色圆  ⚫ 黑色圆  ⚪ 白色圆

😀 微笑  😂 大笑  🤔 思考  😎 酷  🥳 庆祝  😴 睡觉  🤖 机器人  👻 幽灵

❤️ 红心  💙 蓝心  💚 绿心  🧡 橙心  💜 紫心  💛 黄心  🖤 黑心

🚗 汽车  ✈️ 飞机  🚀 火箭  🚢 轮船  🚲 自行车  🚄 高铁

🍎 苹果  🍊 橙子  🍋 柠檬  🍉 西瓜  🍇 葡萄  🍓 草莓  🍔 汉堡  🍕 披萨

🏔️ 雪山  🌊 海浪  🌋 火山  🌴 棕榈树  🌸 樱花  🌙 月亮  ⭐ 星星

### 6.2 符号与箭头

→ 右箭头  ← 左箭头  ↑ 上箭头  ↓ 下箭头  ↔ 双向箭头

➡️ 加粗右箭头  ⬅️ 加粗左箭头  ⬆️ 加粗上箭头  ⬇️ 加粗下箭头

✅ 勾选  ❌ 叉号  ⚠️ 警告  💡 提示  🔥 热门  ⭐ 收藏  🎉 庆祝  🎁 礼物

### 6.3 数学与货币

分数：1/2、3/4、5/8
百分比：12.5%、50%、99.99%
温度：-5°C、25°C、100°C
货币：¥100、$250、€89、£45、HK$1,200

### 6.4 编号与日期

版本号：v1.0.0、v2.3.1-beta、v10.12.4
日期格式：2026-08-08、2026/08/08、2026年8月8日
时间：09:30、14:45:30、23:59:59
范围：10-20 个、100~200 元、3-5 天

---

## 七、长段落测试（中文）

人工智能（AI）是研究、开发用于模拟和扩展人类智能的理论、方法、技术及应用系统的一门技术科学。自 1956 年达特茅斯会议提出"人工智能"概念以来，该领域经历了多次兴衰起伏。近年来，随着深度学习技术的突破和算力成本的下降，人工智能在图像识别、自然语言处理、自动驾驶等领域的应用取得了显著进展，成为推动社会进步的重要力量。

区块链是一种去中心化的分布式账本技术，其核心特点包括不可篡改、公开透明和去中心化。每个区块通过密码学哈希函数与前一区块相连，形成一条链式结构。区块链技术最初应用于加密货币领域，如今已在供应链管理、版权保护、电子政务等多个行业得到广泛探索，为数据信任问题提供了新的解决方案。

可再生能源是指风能、太阳能、水能、生物质能等自然界中可以不断再生、永续利用的能源。与化石燃料相比，可再生能源清洁环保，能够有效减少温室气体排放。近年来，随着光伏发电和风力发电技术的成熟，全球可再生能源装机容量持续增长，能源结构转型已成为各国应对气候变化的重要举措。

---

## 八、链接测试

- 官方网站：https://www.example.com
- 文档中心：https://docs.example.com/api/v2/
- 博客文章：https://blog.example.com/posts/2026/08/architecture
- 邮箱联系：support@example.com
- 内嵌链接：[点击查看帮助文档](https://help.example.com/guide)

---

## 九、水平线测试

分隔线一：

---

分隔线二：

***

分隔线三：

___

---

## 十、综合示例（模拟技术周报）

> **技术周报 · 2026 年第 32 期** | 编辑：系统自动生成

### 本周进展

| 模块 | 负责人 | 状态 | 完成度 | 备注 |
|------|--------|:----:|:------:|------|
| 支付网关 | A 组 | ✅ | 100% | 已上线，T+0 结算 |
| 订单系统 | B 组 | 🔄 | 75% | 灰度中，流量 30% |
| 用户中心 | C 组 | ⏳ | 40% | 等待 SSO 联调 |
| 数据平台 | D 组 | 🔧 | 60% | 迁移至 Spark 4.0 |

### 关键指标

- 在线服务数：**186** 个（新增 12 个）
- 平均响应时间：**86ms**（下降 12%）
- 错误率：**0.18%**（达标 <0.5%）
- 7 日可用性：**99.97%**
- 峰值 QPS：**42,000**（上周五 20:00 峰值）

### 技术亮点

1. 引入 eBPF 观测技术，追踪耗时 <5ms，已覆盖 40% 核心链路
2. 缓存命中率提升至 96.8%，数据库 QPS 下降 55%
3. 完成 Kubernetes 1.31 升级，节点滚动重启零事故

> 💡 下周计划：完成全链路压测、发布 v2.4.0 正式版

---

## 附：格式检查清单

| 特性 | 是否覆盖 | 示例 |
|------|:-------:|------|
| 一级标题 | ✅ | 本文标题 |
| 二级标题 | ✅ | "一、标题层级测试" |
| 三/四级标题 | ✅ | 3.x / 5.x 小节 |
| 复杂表格 | ✅ | 2.1 / 2.2 / 2.3 |
| 代码块 | ✅ | Python / JS / Bash / SQL |
| 行内代码 | ✅ | 3.5 节 |
| 引用块 | ✅ | 第四节 |
| 嵌套列表 | ✅ | 5.1 / 5.2 |
| 任务清单 | ✅ | 5.3 |
| Emoji | ✅ | 第六节（60+ 个） |
| 特殊符号 | ✅ | 箭头/货币/温度 |
| 长段落 | ✅ | 第七节 |
| 链接 | ✅ | 第八节 |
| 水平线 | ✅ | 第九节 |
| 混合文本 | ✅ | 中英混合表格 |
| 数字格式 | ✅ | 百分比/小数/大数/范围 |

---

*测试文档生成完毕 — 请转换为 PDF 验证各格式渲染效果*
