#!/usr/bin/env python3
"""下载抖音视频"""
import os
import sys
import json
import requests
from urllib.parse import urlparse

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) EdgiOS/121.0.2277.107 Version/17.0 Mobile/15E148 Safari/604.1',
    'Referer': 'https://www.douyin.com/',
}

def download_file(url, output_path, timeout=60):
    """下载文件到指定路径"""
    # 确保输出目录存在
    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
    
    print(f'开始下载: {url}', file=sys.stderr)
    print(f'保存到: {output_path}', file=sys.stderr)
    
    response = requests.get(url, headers=HEADERS, stream=True, timeout=timeout)
    
    if response.status_code in (301, 302):
        redirect_url = response.headers.get('location')
        return download_file(redirect_url, output_path, timeout)
    
    if response.status_code != 200:
        raise ValueError(f'下载失败: HTTP {response.status_code}')
    
    total_bytes = int(response.headers.get('content-length', 0))
    downloaded_bytes = 0
    last_progress = -1
    
    with open(output_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
                downloaded_bytes += len(chunk)
                if total_bytes > 0:
                    progress = (downloaded_bytes * 100) // total_bytes
                    if progress != last_progress and progress % 10 == 0:
                        print(f'下载进度: {progress}%', file=sys.stderr)
                        last_progress = progress
    
    print(f'下载完成: {output_path}', file=sys.stderr)
    return output_path

def main():
    if len(sys.argv) < 3:
        print('用法: python3 download_video.py <视频URL> <输出路径>', file=sys.stderr)
        sys.exit(2)
    
    video_url = sys.argv[1]
    output_path = sys.argv[2]
    
    try:
        download_file(video_url, output_path)
        print(json.dumps({'status': 'success', 'path': output_path}, indent=2))
    except Exception as e:
        print(json.dumps({'status': 'error', 'error': str(e)}, indent=2), file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()