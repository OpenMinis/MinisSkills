#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""快速检索 - 直接调用，只有出问题时才提示"""

import os
import sys
import json

def quick_retrieve(query, top_k=10, workspace_id=None, index_id=None):
    """直接执行检索，不提前检查环境"""
    # 获取参数：优先级命令行 > 环境变量
    ws_id = workspace_id or os.getenv('DEFAULT_WORKSPACE_ID', '')
    idx_id = index_id or os.getenv('DEFAULT_INDEX_ID', '')
    
    try:
        from alibabacloud_bailian20231229.client import Client as BaiLianClient
        from alibabacloud_tea_openapi.models import Config
        from alibabacloud_tea_util.models import RuntimeOptions
        from alibabacloud_bailian20231229.models import RetrieveRequest

        # 直接从环境获取凭证（不单独检查，缺失时SDK会报错）
        ak = os.getenv('ALIBABA_CLOUD_ACCESS_KEY_ID', '')
        sk = os.getenv('ALIBABA_CLOUD_ACCESS_KEY_SECRET', '')

        config = Config(
            access_key_id=ak,
            access_key_secret=sk,
            endpoint='bailian.cn-beijing.aliyuncs.com',
            read_timeout=15000,
            connect_timeout=15000
        )
        client = BaiLianClient(config)
        runtime = RuntimeOptions()

        request = RetrieveRequest(
            index_id=idx_id,
            query=query,
            dense_similarity_top_k=top_k,
            enable_reranking=True,
            rerank_top_n=top_k,
            sparse_similarity_top_k=0
        )

        resp = client.retrieve_with_options(ws_id, request, {}, runtime)
        
        # 解析响应
        data_obj = getattr(resp.body, 'data', None)
        nodes = []
        if data_obj is not None:
            raw_nodes = getattr(data_obj, 'nodes', []) or []
            for node in raw_nodes:
                if isinstance(node, dict):
                    nodes.append(node)
                elif hasattr(node, 'to_map'):
                    nodes.append(node.to_map())
        
        chunks = []
        for item in nodes:
            meta = item.get('Metadata', {}) if isinstance(item, dict) else {}
            chunk_entry = {
                'chunkId': meta.get('_id', ''),
                'content': item.get('Text', '') if isinstance(item, dict) else '',
                'score': float(meta.get('_score', 0)),
                'docName': meta.get('doc_name', ''),
                'filePath': meta.get('file_path', ''),
                'pipelineId': meta.get('pipeline_id', '')
            }
            chunks.append(chunk_entry)
        
        result = {
            'workspaceId': ws_id,
            'indexId': idx_id,
            'query': query,
            'topK': top_k,
            'totalMatches': len(chunks),
            'results': chunks,
            'requestId': getattr(getattr(resp.body, 'data', None), 'request_id', '')
        }
        
        # 输出 JSON
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print(f"\n✅ 检索完成: 匹配到 {len(chunks)} 条内容", file=sys.stderr)
        
    except Exception as e:
        # 统一出错输出
        print(json.dumps({"error": str(e)}, ensure_ascii=False), file=sys.stderr)
        print(f"❌ 检索失败: {e}", file=sys.stderr)
        print("\n💡 提示:", file=sys.stderr)
        print("- 检查 ALIBABA_CLOUD_ACCESS_KEY_ID / SECRET 是否配置", file=sys.stderr)
        print("- 检查 DEFAULT_WORKSPACE_ID / DEFAULT_INDEX_ID 是否设置正确", file=sys.stderr)
        print("- 检查工作空间是否存在且有知识库权限", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("用法: python3 quick_retrieve.py <query> [top_k] [workspace_id] [index_id]", file=sys.stderr)
        print("示例:", file=sys.stderr)
        print("  python3 quick_retrieve.py '许山' 10", file=sys.stderr)
        print("  python3 quick_retrieve.py '认证' 5 workspaceId indexId", file=sys.stderr)
        print("\n建议设置环境变量: DEFAULT_WORKSPACE_ID, DEFAULT_INDEX_ID", file=sys.stderr)
        sys.exit(1)
    
    query = sys.argv[1]
    top_k = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 10
    ws_id = sys.argv[3] if len(sys.argv) > 3 else None
    idx_id = sys.argv[4] if len(sys.argv) > 4 else None
    
    quick_retrieve(query, top_k, ws_id, idx_id)
