#!/usr/bin/env python3
"""多线程并行检索知识库"""
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
QUICK_RETRIEVE = SCRIPT_DIR / "quick_retrieve.py"
RETRIEVE = SCRIPT_DIR / "retrieve.py"

queries = [
    ("许山", 5),
    ("许山 主角 战力", 5),
    ("许山 战斗 群英会", 5),
    ("许山 镇海宗 院长", 5),
    ("许山 化神 修为", 5),
    ("许山 法宝 规则", 5),
    ("许山 王庭 昊日", 5),
    ("许山 北地 无敌", 5),
]

def retrieve_single(query, top_k):
    try:
        result = subprocess.run(
            ["python3", str(QUICK_RETRIEVE), query, str(top_k)],
            capture_output=True, text=True, timeout=30
        )
        # Parse the JSON output from stdout
        for line in result.stdout.strip().split('\n'):
            try:
                data = json.loads(line)
                return (query, data.get("results", []))
            except json.JSONDecodeError:
                continue
        return (query, [])
    except Exception as e:
        return (query, [])

def deduplicate(all_results):
    seen = set()
    unique = []
    for r in all_results:
        chunk_id = r.get("chunkId", "")
        if chunk_id not in seen:
            seen.add(chunk_id)
            unique.append(r)
    return unique

# Multi-thread parallel retrieval
all_results = []
print("🚀 启动多线程并行检索 (8路)...\n")

with ThreadPoolExecutor(max_workers=8) as executor:
    fut_to_q = {executor.submit(retrieve_single, q, k): q for q, k in queries}
    done = 0
    for fut in as_completed(fut_to_q):
        q, results = fut.result()
        done += 1
        print(f"  [{done}/8] 「{q}」→ {len(results)} 条")
        all_results.extend(results)

# Deduplicate & sort by score
unique = deduplicate(all_results)
unique.sort(key=lambda x: x.get("score", 0), reverse=True)

print(f"\n{'='*60}")
print(f"✅ 汇总: 原始 {len(all_results)} 条 → 去重后 {len(unique)} 条")
print(f"{'='*60}\n")

for i, r in enumerate(unique[:20], 1):
    content = r.get("content", "")
    score = r.get("score", 0)
    doc = r.get("docName", "未知")
    # Truncate content for display
    preview = content[:120].replace('\n', ' ') + ("..." if len(content) > 120 else "")
    print(f"{i:2d}. [得分 {score:.4f}] {preview}")
    print(f"    来源: {doc}\n")

# Output full JSON for later use
output = {
    "query": "许山(多线程)",
    "totalRaw": len(all_results),
    "totalUnique": len(unique),
    "results": unique
}
print("---JSON_START---")
print(json.dumps(output, ensure_ascii=False))
print("---JSON_END---")
