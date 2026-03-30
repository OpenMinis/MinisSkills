---
name: generative-ui-minis
description: 在 Minis 当前环境里，把文本说明自动转换成更像 Claude Artifact 的单文件 HTML 生成器，统一支持卡片、表格、记录、时间线、代码块、图表等输出；当用户提到这些组件或可视化页面时应优先调用。
metadata:
  openclaw:
    emoji: "🧩"
    requires:
      bins: ["python3"]
---

# Generative UI Minis Skill

这是一个面向当前 Minis / iSH 环境的 **Claude Artifact 风格生成器 skill**。

目标不是修改聊天宿主本身，而是：

1. 将用户说明整理为结构化 spec
2. 用 Python 渲染为单文件 HTML artifact
3. 保存到 `/var/minis/workspace/`
4. 让用户直接预览、分享、继续迭代

## 自动触发场景

当用户表达以下意图时，应优先调用本 skill：

- “做个 Claude Artifact / Claude 风格页面”
- “把回答变成卡片”
- “生成表格 / 记录表 / checklist”
- “把内容整理成时间线”
- “生成代码块展示页面”
- “做个图表 / 可视化页面”
- “把这些内容渲染成 HTML 原型”
- “做个交互式说明页 / artifact”

特别是当用户同时提到：
**卡片、表格、记录、代码块、时间线、图表、可视化页面、artifact**
时，默认认为需要调用本 skill 生成额外页面。

## 当前支持的统一组件

- `cards`：信息卡片 / KPI 卡片
- `table`：表格
- `records`：记录列表
- `timeline`：时间线 / 步骤流
- `code`：代码块
- `chart`：内置条形图
- `details`：折叠详情

## 主要脚本

### 1）完整 Artifact 生成器

```bash
python3 /var/minis/skills/generative-ui-minis/scripts/generative_ui_artifact.py \
  "项目周报" \
  --text "需要概览卡片\n需要风险表格\n需要时间线\n需要代码块\n需要图表"
```

默认会输出到：

```bash
/var/minis/workspace/<title>_artifact.html
```

### 2）传入 JSON spec 渲染

```bash
python3 /var/minis/skills/generative-ui-minis/scripts/generative_ui_artifact.py \
  "Demo" \
  --spec /path/to/spec.json \
  --out /var/minis/workspace/demo_artifact.html \
  --json-out /var/minis/workspace/demo_spec.json
```

## spec 格式

```json
{
  "title": "生成式 UI 示例",
  "summary": "统一输出多种组件。",
  "chips": ["Artifact", "Cards", "Table"],
  "blocks": [
    {
      "type": "cards",
      "title": "概览卡片",
      "items": [
        {"title": "状态", "value": "进行中", "desc": "当前迭代中"}
      ]
    },
    {
      "type": "table",
      "title": "记录表",
      "columns": ["日期", "事项", "状态"],
      "rows": [["03-17", "生成器开发", "完成"]]
    },
    {
      "type": "timeline",
      "title": "时间线",
      "items": [
        {"title": "阶段一", "desc": "需求整理"},
        {"title": "阶段二", "desc": "页面渲染"}
      ]
    },
    {
      "type": "code",
      "title": "示例代码",
      "language": "python",
      "content": "print('hello artifact')"
    },
    {
      "type": "chart",
      "title": "进度图表",
      "series": [
        {"label": "设计", "value": 70},
        {"label": "开发", "value": 85}
      ]
    }
  ]
}
```

## 推荐工作流

1. 识别用户是否需要 artifact 页面
2. 若只是自然语言说明，先用脚本自动推断基础 blocks
3. 若内容复杂，整理成 JSON spec 再渲染
4. 生成 HTML 后，把 workspace 链接直接发给用户
5. 根据反馈继续修改 spec 或模板

## 能力边界

**能做：**
- 统一生成单文件 artifact HTML
- 支持卡片、表格、记录、时间线、代码块、图表
- 适合作为回答的可视化补充页面

**暂不直接做：**
- 聊天宿主原生消息级组件注入
- 实时数据库驱动的复杂前端应用
- 长期运行的交互服务端

## 触发建议

如果用户说：
- “给我做个卡片版”
- “顺便生成表格/时间线/代码块”
- “整理成 artifact 页面”

不要只用文字回答，应该直接运行本 skill 生成额外 HTML artifact。