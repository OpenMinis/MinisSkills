#!/usr/bin/env python3
"""解析抖音分享链接，提取视频信息"""
import re
import json
import sys
import requests
from urllib.parse import urlparse, unquote

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) EdgiOS/121.0.2277.107 Version/17.0 Mobile/15E148 Safari/604.1',
}

def extract_first_url(text):
    """从文本中提取第一个URL"""
    match = re.search(r'https?://[^\s<>"{}|\\^`\[\]]+', text)
    return match.group(0) if match else None

def sanitize_title(title, video_id):
    """清理文件名中的非法字符，并生成长度安全的文件名"""
    # 先清理非法字符
    clean = re.sub(r'[\\/:*?"<>|]', '_', str(title or ''))
    
    # 如果清理后太长，尝试提取话题关键词
    if len(clean) > 30:
        # 提取 # 后面的话题词
        topics = re.findall(r'#(\w+)', clean)
        if topics:
            # 取第一个话题词
            clean = topics[0]
        else:
            # 没有话题，使用通用名 + 视频ID后4位（避免纯数字）
            vid_short = video_id[-4:] if len(video_id) >= 4 else video_id
            clean = f"抖音视频{vid_short}"
    
    return clean

def parse_video_id_from_final_url(final_url):
    """从最终URL中解析视频ID"""
    u = urlparse(final_url)
    parts = [p for p in u.path.split('/') if p]
    if not parts:
        raise ValueError(f'重定向URL路径异常: {final_url}')
    last = parts[-1]
    if last in ('video', 'note') and len(parts) >= 2:
        last = parts[-2]
    return last

def extract_router_data_json(html):
    """从HTML中提取window._ROUTER_DATA"""
    match = re.search(r'window\._ROUTER_DATA\s*=\s*(.*?)</script>', html, re.DOTALL)
    if not match or not match.group(1):
        raise ValueError('从HTML中解析视频信息失败（未找到 window._ROUTER_DATA）')
    raw = match.group(1).strip().rstrip(';')
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f'解析 window._ROUTER_DATA JSON 失败: {e}')

def pick_video_info_res(router_data):
    """从routerData中提取videoInfoRes"""
    loader_data = router_data.get('loaderData', {})
    if not loader_data or not isinstance(loader_data, dict):
        raise ValueError('window._ROUTER_DATA 结构异常（缺少 loaderData）')
    
    # 尝试常见的key
    for key in ['video_(id)/page', 'note_(id)/page']:
        if key in loader_data and loader_data[key].get('videoInfoRes'):
            return loader_data[key]['videoInfoRes']
    
    # 兜底：从任意key中找videoInfoRes
    for v in loader_data.values():
        if v and isinstance(v, dict) and v.get('videoInfoRes'):
            return v['videoInfoRes']
    
    raise ValueError('无法从 window._ROUTER_DATA.loaderData 中定位 videoInfoRes')

def parse_douyin_share_text(share_text):
    """解析抖音分享文本，返回视频信息"""
    share_url = extract_first_url(share_text)
    if not share_url:
        raise ValueError('未找到有效的分享链接')
    
    # 1) 跟随短链重定向，获取最终URL
    resp = requests.get(share_url, headers=HEADERS, allow_redirects=True, timeout=30)
    if not resp.ok:
        raise ValueError(f'访问分享链接失败: {resp.status_code}')
    
    final_url = resp.url
    video_id = parse_video_id_from_final_url(final_url)
    
    # 2) 请求分享页HTML，提取window._ROUTER_DATA
    page_url = f'https://www.iesdouyin.com/share/video/{video_id}'
    html_resp = requests.get(page_url, headers=HEADERS, timeout=30)
    if not html_resp.ok:
        raise ValueError(f'访问分享页失败: {html_resp.status_code}')
    
    router_data = extract_router_data_json(html_resp.text)
    video_info_res = pick_video_info_res(router_data)
    
    item_list = video_info_res.get('item_list', [])
    if not item_list:
        raise ValueError('无法从 videoInfoRes.item_list 中读取视频数据')
    
    item = item_list[0]
    play_addr = item.get('video', {}).get('play_addr', {})
    url_list = play_addr.get('url_list', [])
    
    if not url_list:
        raise ValueError('无法从 item.video.play_addr.url_list[0] 中读取播放地址')
    
    raw_play_url = url_list[0]
    title = sanitize_title(item.get('desc', '').strip() or f'douyin_{video_id}', video_id)
    download_url = raw_play_url.replace('playwm', 'play')
    
    return {
        'video_id': video_id,
        'title': title,
        'download_url': download_url,
        'raw_url': raw_play_url,
        'share_url': share_url,
        'redirected_url': final_url,
        'iesdouyin_url': page_url,
    }

def main():
    if len(sys.argv) < 2:
        # 尝试从stdin读取
        input_text = sys.stdin.read().strip()
    else:
        input_text = ' '.join(sys.argv[1:]).strip()
    
    if not input_text:
        print('用法: python3 parse_douyin.py "抖音分享文本或链接"', file=sys.stderr)
        sys.exit(2)
    
    try:
        result = parse_douyin_share_text(input_text)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as e:
        print(json.dumps({'status': 'error', 'error': str(e)}, ensure_ascii=False, indent=2), file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()