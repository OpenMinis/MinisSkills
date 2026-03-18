# Learnings
## [LRN-20260317-EUC] category

**记录时间**: 2026-03-17T14:05:12Z
**优先级**: medium
**状态**: pending
**领域**: docs

### 摘要
初始化 self-improving-agent 时脚本无执行权限

### 详情
在 Minis 中此脚本应通过 sh 显式调用，避免 Permission denied；优先用 sh /var/minis/skills/self-improving-agent/scripts/minis_auto_log.sh init

### 建议动作
（待补充）

### 元数据
- 来源: conversation
- 关联文件: (可选)
- 标签: (可选)

---
## [LRN-20260317-EXY] category

**记录时间**: 2026-03-17T14:16:26Z
**优先级**: medium
**状态**: pending
**领域**: docs

### 摘要
学习日志默认位置改为 workspace/learnings

### 详情
隐藏目录 .learnings 在跨项目检索与文件选择场景下可见性较差。默认改为 /var/minis/workspace/learnings；同时保留 --project 项目级隔离与 --base 自定义路径，形成共享沉淀 + 项目隔离双线并行。

### 建议动作
（待补充）

### 元数据
- 来源: conversation
- 作用域: workspace
- 基础路径: /var/minis/workspace/learnings
- 关联文件: (可选)
- 标签: (可选)

---
## [LRN-20260317-KNL] category

**记录时间**: 2026-03-17T14:26:04Z
**优先级**: medium
**状态**: pending
**领域**: docs

### 摘要
demo-b 重复问题

### 详情
用于后续公共区提升测试

### 建议动作
（待补充）

### 元数据
- 来源: conversation
- 作用域: project
- 基础路径: /var/minis/workspace/demo-b/.learnings
- 项目路径: /var/minis/workspace/demo-b
- 关联文件: (可选)
- 标签: (可选)

---

## [LRN-20260317-JJ4] category

**记录时间**: 2026-03-17T15:10:28Z
**优先级**: medium
**状态**: pending
**领域**: docs

### 摘要
promote回写测试

### 详情
测试提升后是否自动写回 promoted

### 建议动作
（待补充）

### 元数据
- 来源: conversation
- 作用域: skill
- 基础路径: /var/minis/skills/self-improving-agent/data
- 关联文件: (可选)
- 标签: (可选)

---

## [LRN-20260317-QQG] category

**记录时间**: 2026-03-17T15:12:21Z
**优先级**: medium
**状态**: pending
**领域**: docs

### 摘要
promote版式二次测试

### 详情
检查回写位置是否在分隔线前

### 建议动作
（待补充）

### 元数据
- 来源: conversation
- 作用域: skill
- 基础路径: /var/minis/skills/self-improving-agent/data
- 关联文件: (可选)
- 标签: (可选)

---

## [LRN-20260317-2LU] category

**记录时间**: 2026-03-17T15:16:42Z
**优先级**: medium
**状态**: pending
**领域**: docs

### 摘要
重复提升保护测试

### 详情
测试第二次 promote 是否被阻止

### 建议动作
（待补充）

### 元数据
- 来源: conversation
- 作用域: skill
- 基础路径: /var/minis/skills/self-improving-agent/data
- 关联文件: (可选)
- 标签: (可选)

---

