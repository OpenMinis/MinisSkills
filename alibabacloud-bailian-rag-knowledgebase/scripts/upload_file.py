#!/usr/bin/env python3
"""
上传文件到阿里云百炼知识库
完整流程: ApplyFileUploadLease → PUT到OSS → AddFile → SubmitIndexAddDocumentsJob

用法:
  python3 upload_file.py <文件路径> [index_id]

  如果不指定 index_id，默认使用 DEFAULT_INDEX_ID 环境变量
  所有其他参数从环境变量自动读取

返回 JSON 格式结果

安全限制:
  - 文件必须存在且可读
  - 支持的格式: pdf, doc, docx, txt, md, pptx, ppt, html, png, jpg, jpeg, bmp, gif, xls, xlsx, mp3, mp4, mov, avi
  - 最大文件大小: 100 MB
  - 文件路径必须在允许的目录内 (/var/minis/, /tmp/, 用户主目录)
"""
import os
import sys
import json
import hashlib
from pathlib import Path

# 允许的文件扩展名
ALLOWED_EXTENSIONS = {
    'pdf', 'doc', 'docx', 'txt', 'md', 'pptx', 'ppt', 'html',
    'png', 'jpg', 'jpeg', 'bmp', 'gif', 'xls', 'xlsx',
    'mp3', 'mp4', 'mov', 'avi'
}

# 最大文件大小: 100 MB
MAX_FILE_SIZE = 100 * 1024 * 1024

# 允许的基础目录
ALLOWED_BASE_DIRS = [
    '/var/minis/',
    '/tmp/',
    os.path.expanduser('~'),
]


def validate_file_path(file_path):
    """验证文件路径和安全性"""
    try:
        # 转换为绝对路径
        abs_path = os.path.abspath(file_path)
        
        # 检查路径是否在允许的目录内
        allowed = False
        for base_dir in ALLOWED_BASE_DIRS:
            if abs_path.startswith(os.path.abspath(base_dir)):
                allowed = True
                break
        
        if not allowed:
            return None, f"文件路径必须在以下目录内: {', '.join(ALLOWED_BASE_DIRS)}"
        
        # 检查文件是否存在
        if not os.path.exists(abs_path):
            return None, f"文件不存在: {abs_path}"
        
        # 检查是否是文件（不是目录）
        if not os.path.isfile(abs_path):
            return None, f"路径不是文件: {abs_path}"
        
        # 检查文件扩展名
        ext = os.path.splitext(abs_path)[1].lstrip('.').lower()
        if ext not in ALLOWED_EXTENSIONS:
            return None, f"不支持的文件格式: .{ext}。支持的格式: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        
        # 检查文件大小
        file_size = os.path.getsize(abs_path)
        if file_size == 0:
            return None, "文件为空"
        if file_size > MAX_FILE_SIZE:
            return None, f"文件过大: {file_size / 1024 / 1024:.1f} MB，最大限制: {MAX_FILE_SIZE / 1024 / 1024:.0f} MB"
        
        return abs_path, None
    except Exception as e:
        return None, f"路径验证失败: {str(e)}"


def upload_file(file_path, index_id=None):
    # 验证文件路径
    abs_path, error = validate_file_path(file_path)
    if error:
        return {"error": error}
    
    ws_id = os.getenv("DEFAULT_WORKSPACE_ID", "")
    idx_id = index_id or os.getenv("DEFAULT_INDEX_ID", "")

    if not ws_id:
        return {"error": "请设置 DEFAULT_WORKSPACE_ID 环境变量"}

    file_name = os.path.basename(abs_path)
    file_size = os.path.getsize(abs_path)
    
    # 计算 MD5（流式读取以节省内存）
    md5_hash = hashlib.md5()
    with open(abs_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b''):
            md5_hash.update(chunk)
    md5_val = md5_hash.hexdigest()

    import requests as http_req

    try:
        from alibabacloud_bailian20231229.client import Client
        from alibabacloud_bailian20231229 import models as m
        from alibabacloud_tea_openapi.models import Config

        config = Config(
            access_key_id=os.getenv("ALIBABA_CLOUD_ACCESS_KEY_ID", ""),
            access_key_secret=os.getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET", ""),
            endpoint="bailian.cn-beijing.aliyuncs.com",
        )
        client = Client(config)

        # === Step 1: 列出分类，获取真实 category_id ===
        cat_req = m.ListCategoryRequest(category_type="UNSTRUCTURED")
        cat_resp = client.list_category(ws_id, cat_req)
        if not cat_resp.body.success or not cat_resp.body.data:
            return {"error": f"获取分类失败: {cat_resp.body.code} - {cat_resp.body.message}"}

        categories = cat_resp.body.data.category_list or []
        default_cat = None
        for cat in categories:
            mp = cat.to_map() if hasattr(cat, "to_map") else cat
            if mp.get("IsDefault"):
                default_cat = mp
                break
        if not default_cat and categories:
            default_cat = categories[0].to_map() if hasattr(categories[0], "to_map") else categories[0]

        if not default_cat:
            return {"error": "未找到 UNSTRUCTURED 分类，请先在百炼控制台创建"}

        category_id = default_cat["CategoryId"]

        # === Step 2: ApplyFileUploadLease ===
        lease_req = m.ApplyFileUploadLeaseRequest(
            file_name=file_name,
            md_5=md5_val,
            size_in_bytes=str(file_size),
            category_type="UNSTRUCTURED",
        )
        lease_resp = client.apply_file_upload_lease(category_id, ws_id, lease_req)
        if not lease_resp.body.success:
            return {"error": f"申请上传租约失败: {lease_resp.body.code} - {lease_resp.body.message}"}

        lease_data = lease_resp.body.data
        lease_id = lease_data.file_upload_lease_id
        upload_url = lease_data.param.url
        upload_method = lease_data.param.method
        upload_headers = lease_data.param.headers

        # === Step 3: 上传文件到 OSS ===
        with open(abs_path, "rb") as f:
            content = f.read()
        r = http_req.put(upload_url, data=content, headers=upload_headers)
        if r.status_code not in (200, 201):
            return {"error": f"上传文件到OSS失败: HTTP {r.status_code}"}

        # === Step 4: AddFile 添加到数据中心 ===
        add_req = m.AddFileRequest(
            category_id=category_id,
            category_type="UNSTRUCTURED",
            lease_id=lease_id,
            parser="DASHSCOPE_DOCMIND",
        )
        add_resp = client.add_file(ws_id, add_req)
        if not add_resp.body.success:
            return {"error": f"AddFile失败: {add_resp.body.code} - {add_resp.body.message}"}

        # === Step 5: 列出文件获取 FileId ===
        list_req = m.ListFileRequest(category_id=category_id, max_results=50)
        list_resp = client.list_file(ws_id, list_req)
        if not list_resp.body.success:
            return {"error": f"列出文件失败, 但文件已上传: {list_resp.body.code}"}

        file_list = list_resp.body.data.file_list or []
        file_id = None
        target = None
        for f in file_list:
            mp = f.to_map() if hasattr(f, "to_map") else f
            if mp.get("FileName") == file_name:
                file_id = mp["FileId"]
                target = mp
                break

        if not file_id:
            return {"error": "文件上传成功但未能找到文件ID", "file_name": file_name}

        # === Step 6: 提交到知识库索引 ===
        if idx_id:
            idx_req = m.SubmitIndexAddDocumentsJobRequest(
                index_id=idx_id,
                source_type="DATA_CENTER_FILE",
                document_ids=[file_id],
            )
            idx_resp = client.submit_index_add_documents_job(ws_id, idx_req)
            job_ok = idx_resp.body.success
            job_id = idx_resp.body.data.id if idx_resp.body.data else ""
        else:
            job_ok = None
            job_id = ""

        return {
            "success": True,
            "file_name": file_name,
            "file_size": file_size,
            "file_md5": md5_val,
            "file_id": file_id,
            "category_id": category_id,
            "lease_id": lease_id,
            "index_submitted": job_ok,
            "index_job_id": job_id,
            "index_id": idx_id,
            "workspace_id": ws_id,
        }
    except Exception as e:
        return {"error": f"上传失败: {str(e)}"}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python3 upload_file.py <文件路径> [index_id]", file=sys.stderr)
        print("示例:", file=sys.stderr)
        print("  python3 upload_file.py /var/minis/workspace/doc.pdf", file=sys.stderr)
        print("  python3 upload_file.py /tmp/doc.pdf 35ozlwb6sa", file=sys.stderr)
        print("\n支持的文件格式:", file=sys.stderr)
        print(f"  {', '.join(sorted(ALLOWED_EXTENSIONS))}", file=sys.stderr)
        print(f"\n最大文件大小: {MAX_FILE_SIZE / 1024 / 1024:.0f} MB", file=sys.stderr)
        sys.exit(1)

    file_path = sys.argv[1]
    index_id = sys.argv[2] if len(sys.argv) > 2 else None

    result = upload_file(file_path, index_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if result.get("success"):
        print(f"\n✅ 上传完成!", file=sys.stderr)
        print(f"   FileId: {result['file_id']}", file=sys.stderr)
        if result.get("index_submitted"):
            print(f"   已提交到知识库索引 (JobId: {result['index_job_id']})", file=sys.stderr)
        else:
            print(f"   ⚠️ 未提交到索引（未指定 index_id）", file=sys.stderr)
    else:
        print(f"\n❌ 上传失败: {result.get('error')}", file=sys.stderr)
        sys.exit(1)
