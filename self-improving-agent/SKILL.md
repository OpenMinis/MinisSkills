---
name: self-improving-agent
description: "自我改进记录与闭环：当命令/操作失败、用户纠错、发现知识过时、外部 API 失败、或出现可复用更优方案时触发。重要任务前可回顾历史 learnings。避免在普通闲聊、无需记录的临时失误或用户已明确不需要记录时触发。"
metadata:
  language: zh-CN
  scope: minis
---

# 自我改进技能（Minis 版）

本技能用于在 Minis 环境内**记录错误、纠正与可复用的最佳实践**，形成可追踪的学习闭环。

## Minis 目录约定

- **工作目录**：`/var/minis/workspace/`
- **技能默认学习日志目录**：`/var/minis/skills/self-improving-agent/data/`
- **技能内公共学习日志目录（提升后）**：`/var/minis/skills/self-improving-agent/data/public/`
- **项目级学习日志目录（可选）**：`<project>/.learnings/`
- **学习日志文件**：
  - `LEARNINGS.md`（纠错、知识缺口、最佳实践）
  - `ERRORS.md`（命令失败、异常输出）
  - `FEATURE_REQUESTS.md`（用户提出的新能力）

> 默认先记到技能自己的 data 目录；当你明确指定项目时，再写到项目级日志；当问题已抽象为跨项目通用规则时，再提升到技能内公共区或 Minis 记忆系统。

## 当前最终规则

- **默认记录位置**：`/var/minis/skills/self-improving-agent/data/`
- **技能内公共区**：`/var/minis/skills/self-improving-agent/data/public/`
- **项目级记录**：仅在显式传入 `--project <path>` 时使用 `<project>/.learnings/`
- **推荐公共参数**：`--public`
- **兼容别名**：`--workspace` 仍可用，但仅作兼容，不再推荐
- **提升行为**：`promote <条目ID>` 会将条目复制到技能内公共区，并自动把源条目标记为 `promoted`，写回 `**已提升到**` 与 `### 解决记录`
- **重复保护**：若条目已存在于技能内公共区，重复执行 `promote` 不会重复追加

## 快速参考（Quick Reference）

| 情景 | 动作 |
|-----------|--------|
| 命令/操作失败 | 默认记录到技能目录 `data/ERRORS.md` |
| 用户纠正你 | 默认记录到技能目录 `data/LEARNINGS.md`，类别 `correction` |
| 用户需要缺失能力 | 默认记录到技能目录 `data/FEATURE_REQUESTS.md` |
| 明确指定项目上下文 | 记录到 `<project>/.learnings/` |
| 外部 API/工具失败 | 记录到当前作用域的 `ERRORS.md`，包含集成细节 |
| 知识过时 | 记录到当前作用域的 `LEARNINGS.md`，类别 `knowledge_gap` |
| 发现更优方案 | 先记录到当前作用域，确认通用后再提升 |
| 同类问题跨多个项目复发 | 提升到技能内公共区 `data/public/` |
| 与已有条目类似 | 用 `**See Also**` 链接，并考虑提升优先级 |
| 广泛适用的经验 | 提升到技能内公共区或 Minis 记忆（见下方“提升到 Minis 记忆”） |

## 触发记录规则（Minis 运行时约定）

> 说明：本技能默认**不会后台自动监听**。当满足触发条件时，由助手（或你）主动调用 `scripts/minis_auto_log.sh` 落盘。

### 建议“必须记录”的触发条件
满足以下任一条，就应该记录（除非你明确说“不用记”）：

1. **命令/操作失败且非显然**：例如权限、路径、依赖、网络、第三方 API 异常，需要排查才能定位。
2. **用户纠正**：你指出我哪里理解错、逻辑不符合本软件实际、路径/规范不对。
3. **知识更新/过时修正**：发现之前假设不适配 Minis，或文档/实现需要纠偏。
4. **可复用的更优方案**：形成稳定做法、约定、模板、或能显著减少返工的流程。
5. **复发模式**：同类问题在同一任务中反复出现，或跨任务/跨项目出现。

### 一般不记录的情况
- 普通闲聊、一次性小改动、没有复用价值的细枝末节。
- 你明确要求“不要记录”。

### 记录位置建议
- **默认**先写入技能区 `data/`。
- 确认具备跨任务复用价值后，用 `promote` 提升到技能内公共区 `data/public/`。

## 与 Minis 记忆（memory）的区别与提升标准

### 区别（建议理解方式）
- 本技能日志（`data/` 与 `data/public/`）是**可编辑的工作复盘库**：记录上下文、排错过程、方案演进，允许长文本与细节。
- Minis 记忆（`memory_write` 写入 `/var/minis/memory/`）是**跨会话长期规则/偏好**：应短、稳定、可复用；写得不好会长期“污染”后续决策。

### 写入选择（先记日志，再提炼成记忆）
- **先写本技能日志**：当内容需要上下文（错误输出、排查路径、对比方案）、暂不确定是否通用、或仍在迭代。
- **再提升到记忆**：当结论已稳定、跨任务/跨技能都适用，且能用一句话表达。

### 何时提升到记忆（硬标准）
满足以下任一条，才考虑 `memory_write`：
1. 可以浓缩成一句“**以后遇到 X 就做 Y**”的规则，并且不依赖特定项目细节。
2. **30 天内复发 ≥ 3 次**，或至少出现在 **2 个不同任务/领域**。
3. 明确属于你的长期偏好/约定（例如工具使用约束、路径规范、输出格式规则），且你明确说“记住/以后都这样”。

### 提升动作建议
- 先用 `promote` 提升到技能内公共区 `data/public/`（可见性更高、便于复盘）。
- 再从公共区条目中提炼 1~3 条短规则，用 `memory_write` 写入当日日记忆。


用法示例：
```bash
# 默认写到技能自己的 data 目录
sh /var/minis/skills/self-improving-agent/scripts/minis_auto_log.sh init

# 记录技能级学习
sh /var/minis/skills/self-improving-agent/scripts/minis_auto_log.sh learning "修复了下载超时" "使用分片与重试"

# 如需明确落到项目级，再显式传 --project
sh /var/minis/skills/self-improving-agent/scripts/minis_auto_log.sh --project /var/minis/workspace/my-project error "curl 请求失败" "HTTP 429"

# 如需直接写到技能内公共区，显式传 --public
sh /var/minis/skills/self-improving-agent/scripts/minis_auto_log.sh --public feature "支持批量导出" "运营需要日报"

# 搜索技能区 + 项目区 + 技能内公共区
sh /var/minis/skills/self-improving-agent/scripts/minis_auto_log.sh search 超时

# 将条目提升到技能内公共区
sh /var/minis/skills/self-improving-agent/scripts/minis_auto_log.sh promote LRN-20260317-ABC

# 查看当前作用域
sh /var/minis/skills/self-improving-agent/scripts/minis_auto_log.sh status
```

## 记录格式（Logging Format）

### Learning 记录

追加到 `.learnings/LEARNINGS.md`：

```markdown
## [LRN-YYYYMMDD-XXX] category

**记录时间**: ISO-8601 时间戳
**优先级**: low | medium | high | critical
**状态**: pending
**领域**: frontend | backend | infra | tests | docs | config

### 摘要
一行描述所学内容

### 详情
完整上下文：发生了什么、哪里错了、正确做法

### 建议动作
具体可执行的改进或修复

### 元数据
- 来源: conversation | error | user_feedback
- 关联文件: path/to/file.ext
- 标签: tag1, tag2
- 相关条目: LRN-20250110-001（如有关联）
- 模式键: simplify.dead_code | harden.input_validation（可选，复发模式追踪）
- 复发次数: 1（可选）
- 首次出现: 2025-01-15（可选）
- 最近出现: 2025-01-15（可选）

---
```

### Error 记录

追加到 `.learnings/ERRORS.md`：

```markdown
## [ERR-YYYYMMDD-XXX] skill_or_command_name

**记录时间**: ISO-8601 时间戳
**优先级**: high
**状态**: pending
**领域**: frontend | backend | infra | tests | docs | config

### 摘要
简要描述失败内容

### Error
```
实际错误信息或输出
```

### Context
- 尝试的命令/操作
- 输入或参数
- 环境细节（如相关）

### 建议修复
如可识别，给出可能的解决方案

### 元数据
- 可复现: yes | no | unknown
- 关联文件: path/to/file.ext
- 相关条目: ERR-20250110-001（如复发）

---
```

### Feature Request 记录

追加到 `.learnings/FEATURE_REQUESTS.md`：

```markdown
## [FEAT-YYYYMMDD-XXX] capability_name

**记录时间**: ISO-8601 时间戳
**优先级**: medium
**状态**: pending
**领域**: frontend | backend | infra | tests | docs | config

### 需求能力
用户想实现的能力

### 用户背景
为什么需要、在解决什么问题

### 复杂度评估
simple | medium | complex

### 建议实现
可能的实现方式与扩展点

### 元数据
- 频次: first_time | recurring
- 关联功能: existing_feature_name

---
```

## ID 生成规则

格式：`TYPE-YYYYMMDD-XXX`
- TYPE: `LRN` (learning), `ERR` (error), `FEAT` (feature)
- YYYYMMDD: 当前日期
- XXX: 顺序号或随机 3 位（如 `001`, `A7B`）

示例：`LRN-20250115-001`、`ERR-20250115-A3F`、`FEAT-20250115-002`

## 条目解决

当问题修复后，更新条目：

1. 将 `**状态**: pending` → `**状态**: resolved`
2. 在元数据后添加解决块：

```markdown
### 解决记录
- **解决时间**: 2025-01-16T09:00:00Z
- **提交/PR**: abc123 或 #42
- **说明**: 简要描述做了什么
```

其他状态：
- `in_progress` - 正在处理
- `wont_fix` - 决定不修（在解决记录中写原因）
- `promoted` - 已提升到 Minis 记忆

## 提升到 Minis 记忆

当某条学习具有广泛适用性（不是一次性修复），应提升到 Minis 记忆系统。

### 何时提升

- 学习跨多个文件/功能适用
- 任何贡献者（人/AI）都应知道
- 防止重复犯错
- 记录项目约定

### 提升目标（Minis）

- **日记忆**：`/var/minis/memory/YYYY-MM-DD.md`（通过 `memory_write` 写入）
- **全局记忆**：`/var/minis/memory/GLOBAL.md`（只读，需要用户在设置中维护）
- **项目笔记**：建议写入 `/var/minis/workspace/PROJECT_NOTES.md`

### 如何提升

1. **提炼**：把学习浓缩成简洁规则或事实
2. **写入**：使用 `memory_write` 写入日记忆，必要时同步到项目笔记
3. **回写**：更新原条目：
   - `**状态**: pending` → `**状态**: promoted`
   - 添加 `**已提升**: YYYY-MM-DD.md` 或 `PROJECT_NOTES.md`

## 复发模式检测

如果记录内容与已有条目相似：

1. **先搜索**：`grep -r "keyword" /var/minis/workspace/.learnings/`
2. **建立关联**：在元数据中添加 `**See Also**: ERR-20250110-001`
3. **提升优先级**：如果问题反复出现
4. **考虑系统性修复**：反复出现通常意味着：
   - 文档缺失（→ 写入 PROJECT_NOTES.md 或日记忆）
   - 自动化缺失（→ 加入脚本或工具链）
   - 架构问题（→ 建立技术债任务）

## Simplify & Harden Feed

用于 ingest `simplify-and-harden` 技能中的复发模式，并将其转化为持久化的提示规则。

### Ingestion Workflow

1. 从任务摘要读取 `simplify_and_harden.learning_loop.candidates`。
2. 对每个候选项使用 `pattern_key` 作为稳定去重键。
3. 在 `.learnings/LEARNINGS.md` 搜索是否已存在：
   - `grep -n "Pattern-Key: <pattern_key>" /var/minis/workspace/.learnings/LEARNINGS.md`
4. 若已存在：
   - 递增 `Recurrence-Count`
   - 更新 `Last-Seen`
   - 添加 `See Also` 关联
5. 若不存在：
   - 新建 `LRN-...` 条目
   - 设置 `Source: simplify-and-harden`
   - 设置 `Pattern-Key`、`Recurrence-Count: 1` 与 `First-Seen`/`Last-Seen`

### 提升规则（系统提示反馈）

当满足以下条件时，把复发模式提升到 Minis 记忆：

- `Recurrence-Count >= 3`
- 至少出现在 2 个不同任务
- 在 30 天内发生

提升后的规则应是**短而明确的预防规则**（做事前/做事时的动作），而不是冗长的事故复盘。

## 周期性回顾

在自然节点回顾 `.learnings/`：

### 何时回顾
- 开始新的重要任务前
- 完成一个功能后
- 进入曾有 learnings 的领域时
- 活跃开发期间每周一次

### 快速状态检查
```bash
# Count pending items
grep -h "状态\*\*: pending" /var/minis/workspace/.learnings/*.md | wc -l

# List pending high-priority items
grep -B5 "优先级\*\*: high" /var/minis/workspace/.learnings/*.md | grep "^## \["

# Find learnings for a specific area
grep -l "领域\*\*: backend" /var/minis/workspace/.learnings/*.md
```
