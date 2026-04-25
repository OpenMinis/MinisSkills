#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""知识库 RAG 检索 - Python版"""

import os
import sys
import json


def retrieve(workspace_id, index_id, query, top_k=5):
    """执行知识库检索
    
    Args:
        workspace_id: 工作空间ID
        index_id: 索引(知识库)ID
        query: 查询文本
        top_k: 返回的匹配段落数量 (1-20)
    """
    ak = os.getenv('ALIBABA_CLOUD_ACCESS_KEY_ID', '')
    sk = os.getenv('ALIBABA_CLOUD_ACCESS_KEY_SECRET', '')
    
    if not ak or not sk:
        print(json.dumps({"error": "未配置阿里云访问凭证"}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
    
    from alibabacloud_bailian20231229.client import Client as BaiLianClient
    from alibabacloud_tea_openapi.models import Config
    from alibabacloud_tea_util.models import RuntimeOptions
    from alibabacloud_bailian20231229.models import RetrieveRequest, RetrieveRequestQueryHistory
    
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
        index_id=index_id,
        query=query,
        dense_similarity_top_k=top_k,
        enable_reranking=True,
        rerank_top_n=top_k,
        sparse_similarity_top_k=0
    )
    
    try:
        resp = client.retrieve_with_options(workspace_id, request, {}, runtime)
        
        # 解析响应 - Python SDK 返回的结构不同
        # resp.body.data.nodes 是一个列表，每个节点是 {'Metadata': {...}, 'Score': float, 'Text': str}
        data_obj = getattr(resp.body, 'data', None)
        nodes = []
        if data_obj is not None:
            raw_nodes = getattr(data_obj, 'nodes', []) or []
            for node in raw_nodes:
                if isinstance(node, dict):
                    nodes.append(node)
                elif hasattr(node, 'to_map'):
                    nodes.append(node.to_map())
        
        # 构建结果列表
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
            'workspaceId': workspace_id,
            'indexId': index_id,
            'query': query,
            'topK': top_k,
            'totalMatches': len(chunks),
            'results': chunks,
            'requestId': getattr(getattr(resp.body, 'data', None), 'request_id', '')
        }
        
        # 输出 JSON
        print(json.dumps(result, ensure_ascii=False, indent=2))
        
        # 同时打印摘要到 stderr（方便阅读）
        total = len(chunks)
        match_count = result['totalMatches']
        print(f"\n[检索摘要] 匹配到 {match_count} 条内容 | 共 {total} 个结果块", file=sys.stderr)
        
    except Exception as e:
        error_msg = f"错误: {e}"
        print(json.dumps({"error": str(e)}, ensure_ascii=False), file=sys.stderr)
        print(error_msg, file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    if len(sys.argv) < 4:
        print("用法: python3 retrieve.py <workspaceId> <indexId> <query> [top_k]", file=sys.stderr)
        print(f"\n示例:")
        print(f"  python3 {sys.argv[0]} llm-vh23s0c0buyg942k 35ozlwb6sa '许爷是谁'", file=sys.stderr)
        print(f"  python3 {sys.argv[0]} llm-vh23s0c0buyg942k 35ozlwb6sa '规则系道具' 20", file=sys.stderr)
        sys.exit(1)
    
    ws_id = sys.argv[1]
    idx_id = sys.argv[2]
    query_text = sys.argv[3]
    top_k = int(sys.argv[4]) if len(sys.argv) > 4 and sys.argv[4].isdigit() else 5
    
    retrieve(ws_id, idx_id, query_text, top_k)
