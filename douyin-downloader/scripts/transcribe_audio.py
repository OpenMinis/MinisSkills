#!/usr/bin/env python3
"""
音频转录脚本 - 火山引擎 ASR
将音频文件转换为文字
"""
import os
import sys
import json
import base64
import time
import uuid
import argparse
import urllib.request
import urllib.error

FLASH_URL = 'https://openspeech.bytedance.com/api/v3/auc/bigmodel/recognize/flash'
SUBMIT_URL = 'https://openspeech.bytedance.com/api/v3/auc/bigmodel/submit'
QUERY_URL = 'https://openspeech.bytedance.com/api/v3/auc/bigmodel/query'


def parse_args():
    parser = argparse.ArgumentParser(description='音频转文字 - 火山引擎 ASR')
    parser.add_argument('input_path', help='音频文件路径')
    parser.add_argument('--out', dest='output_path', help='输出 JSON 路径')
    parser.add_argument('--text-out', dest='text_path', help='输出文本文件路径')
    parser.add_argument('--app-key', dest='app_key', default=os.environ.get('VOLC_APP_KEY', ''),
                        help='火山引擎 APP Key')
    parser.add_argument('--access-key', dest='access_key', default=os.environ.get('VOLC_ACCESS_KEY', ''),
                        help='火山引擎 Access Key')
    parser.add_argument('--resource-id', dest='resource_id', default='volc.bigasr.auc_turbo',
                        help='资源ID')
    parser.add_argument('--model', dest='model_name', default='bigmodel',
                        help='模型名')
    parser.add_argument('--mode', dest='mode', default='auto', choices=['auto', 'flash', 'standard'],
                        help='模式: auto/flash/standard')
    parser.add_argument('--poll-interval-ms', dest='poll_interval_ms', type=int, default=1500,
                        help='轮询间隔(毫秒)')
    parser.add_argument('--poll-timeout-ms', dest='poll_timeout_ms', type=int, default=120000,
                        help='轮询超时(毫秒)')
    return parser.parse_args()


def choose_mode(mode, resource_id):
    if mode in ('flash', 'standard'):
        return mode
    return 'standard' if resource_id == 'volc.seedasr.auc' else 'flash'


def build_body_by_mode(mode, app_key, audio_b64, model_name):
    if mode == 'flash':
        return {
            'user': {'uid': str(app_key)},
            'audio': {'data': audio_b64},
            'request': {'model_name': model_name}
        }
    
    # standard 模式
    return {
        'user': {'uid': '豆包语音'},
        'audio': {
            'data': audio_b64,
            'format': 'mp3',
            'codec': 'raw',
            'rate': 16000,
            'bits': 16,
            'channel': 1
        },
        'request': {
            'model_name': model_name,
            'enable_itn': True,
            'enable_punc': True,
            'enable_ddc': False,
            'enable_speaker_info': False,
            'enable_channel_split': False,
            'show_utterances': False,
            'vad_segment': False,
            'sensitive_words_filter': ''
        }
    }


def make_request(url, headers, data):
    """发送 HTTP 请求"""
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode('utf-8'),
        headers=headers,
        method='POST'
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp, resp.read().decode('utf-8')
    except urllib.error.HTTPError as e:
        return e, e.read().decode('utf-8') if e.fp else '{}'


def call_flash(opts, request_id, body):
    headers = {
        'Content-Type': 'application/json',
        'X-Api-App-Key': str(opts.app_key),
        'X-Api-Access-Key': str(opts.access_key),
        'X-Api-Resource-Id': str(opts.resource_id),
        'X-Api-Request-Id': request_id,
        'X-Api-Sequence': '-1'
    }
    res, text = make_request(FLASH_URL, headers, body)
    return res, text, 'flash'


def call_standard(opts, request_id, body):
    # 提交请求
    submit_headers = {
        'Content-Type': 'application/json',
        'x-api-key': str(opts.app_key),
        'X-Api-Resource-Id': str(opts.resource_id),
        'X-Api-Request-Id': request_id,
        'X-Api-Sequence': '-1'
    }
    submit_res, submit_text = make_request(SUBMIT_URL, submit_headers, body)
    
    # 检查响应是否成功
    if not (hasattr(submit_res, 'ok') and submit_res.ok) and not (hasattr(submit_res, 'status') and 200 <= submit_res.status < 300):
        return submit_res, submit_text, 'submit'
    
    # 轮询结果
    start = time.time()
    poll_interval = opts.poll_interval_ms / 1000
    
    while (time.time() - start) * 1000 < opts.poll_timeout_ms:
        time.sleep(poll_interval)
        
        query_headers = {
            'Content-Type': 'application/json',
            'x-api-key': str(opts.app_key),
            'X-Api-Resource-Id': str(opts.resource_id),
            'X-Api-Request-Id': request_id
        }
        query_res, query_text = make_request(QUERY_URL, query_headers, {})
        
        # 检查响应是否成功
        query_ok = hasattr(query_res, 'ok') and query_res.ok if hasattr(query_res, 'ok') else (hasattr(query_res, 'status') and 200 <= query_res.status < 300)
        status_code = query_res.headers.get('x-api-status-code', '') if hasattr(query_res, 'headers') and hasattr(query_res.headers, 'get') else ''
        
        try:
            parsed = json.loads(query_text) if query_text else {}
        except:
            parsed = {'raw': query_text}
        
        result_text = parsed.get('result', {}).get('text') or parsed.get('payload_msg', {}).get('result', {}).get('text', '')
        
        if query_ok and status_code == '20000000':
            return query_res, query_text, 'query'
        
        # 文本已可用
        if query_ok and result_text:
            return query_res, query_text, 'query'
        
        # 处理中，继续轮询
        if query_ok and (status_code == '20000001' or query_text.strip() == '{}' or not result_text):
            continue
        
        # 错误
        if not query_ok:
            return query_res, query_text, 'query'
    
    # 超时
    error_res = type('obj', (object,), {'ok': False, 'status': 408, 'headers': {}})()
    return error_res, json.dumps({'status': 'error', 'error': 'standard query timeout'}), 'query'


def get_result_text(parsed):
    return parsed.get('result', {}).get('text') or parsed.get('payload_msg', {}).get('result', {}).get('text', '')


def main():
    opts = parse_args()
    
    if not opts.input_path:
        print('用法: python3 transcribe_audio.py <音频文件> [--out result.json] [--text-out result.txt] --app-key KEY --access-key KEY')
        sys.exit(2)
    
    if not opts.app_key:
        print(json.dumps({'status': 'error', 'error': '缺少 app-key'}, ensure_ascii=False))
        sys.exit(1)
    
    if not os.path.exists(opts.input_path):
        print(json.dumps({'status': 'error', 'error': f'文件不存在: {opts.input_path}'}, ensure_ascii=False))
        sys.exit(1)
    
    # 检查文件大小
    file_size = os.path.getsize(opts.input_path)
    if file_size > 100 * 1024 * 1024:
        print(json.dumps({'status': 'error', 'error': '文件超过100MB限制'}, ensure_ascii=False))
        sys.exit(1)
    
    mode = choose_mode(opts.mode, opts.resource_id)
    request_id = str(uuid.uuid4())
    
    # 读取音频文件并转为 base64
    with open(opts.input_path, 'rb') as f:
        audio_b64 = base64.b64encode(f.read()).decode('utf-8')
    
    body = build_body_by_mode(mode, opts.app_key, audio_b64, opts.model_name)
    
    # 调用 API
    if mode == 'flash':
        res, text, stage = call_flash(opts, request_id, body)
    else:
        res, text, stage = call_standard(opts, request_id, body)
    
    # 检查响应是否成功
    is_ok = hasattr(res, 'ok') and res.ok if hasattr(res, 'ok') else (hasattr(res, 'status') and 200 <= res.status < 300)
    
    try:
        parsed = json.loads(text) if text else {}
    except:
        parsed = {'raw': text}
    
    result_text = get_result_text(parsed)
    
    out_obj = {
        'status': 'success' if is_ok else 'error',
        'mode': mode,
        'stage': stage,
        'request_id': request_id,
        'http_status': res.status if hasattr(res, 'status') else 0,
        'api_status_code': res.headers.get('x-api-status-code', '') if hasattr(res, 'headers') and hasattr(res.headers, 'get') else '',
        'api_message': res.headers.get('x-api-message', '') if hasattr(res, 'headers') and hasattr(res.headers, 'get') else '',
        'log_id': res.headers.get('x-tt-logid', '') if hasattr(res, 'headers') and hasattr(res.headers, 'get') else '',
        'result_text': result_text,
        'result': parsed
    }
    
    # 写入输出文件
    if opts.output_path:
        os.makedirs(os.path.dirname(opts.output_path) or '.', exist_ok=True)
        with open(opts.output_path, 'w', encoding='utf-8') as f:
            json.dump(out_obj, f, ensure_ascii=False, indent=2)
    
    if opts.text_path:
        os.makedirs(os.path.dirname(opts.text_path) or '.', exist_ok=True)
        with open(opts.text_path, 'w', encoding='utf-8') as f:
            f.write(result_text or '')
    
    # 输出到 stdout
    print(json.dumps(out_obj, ensure_ascii=False, indent=2))
    
    if out_obj['status'] == 'error':
        sys.exit(1)


if __name__ == '__main__':
    main()
