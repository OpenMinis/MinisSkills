#!/usr/bin/env python3
"""Experimental image-to-image generation via ChatGPT Codex responses image_generation tool."""
import argparse, base64, http.client, json, mimetypes, os, re, ssl, subprocess, sys, time

AUTH_CACHE = os.path.expanduser('~/.chatgpt_auth.json')
SCRIPT_DIR = os.path.dirname(__file__)


def get_token():
    if os.path.exists(AUTH_CACHE):
        try:
            with open(AUTH_CACHE) as f:
                c = json.load(f)
            if time.time() - c.get('_cached_at', 0) <= 8 * 3600 and c.get('accessToken'):
                print('[auth] Using cached token.', file=sys.stderr)
                return c['accessToken']
        except Exception:
            pass
    r = subprocess.run([sys.executable, os.path.join(SCRIPT_DIR, 'get_auth.py')], capture_output=True, text=True, timeout=360)
    if r.stderr:
        print(r.stderr, end='', file=sys.stderr)
    if r.returncode != 0:
        raise SystemExit(r.stdout + r.stderr)
    with open(AUTH_CACHE) as f:
        return json.load(f)['accessToken']


def data_url(path):
    mt = mimetypes.guess_type(path)[0] or 'image/png'
    with open(path, 'rb') as f:
        b64 = base64.b64encode(f.read()).decode('ascii')
    return 'data:%s;base64,%s' % (mt, b64)


def call_api(token, prompt, image_path, output, model, effort, schema):
    img = data_url(image_path)
    if schema == 'responses_multimodal':
        content = [
            {'type': 'input_text', 'text': 'Use the image generation tool to create a new image based on the reference image. Preserve the main person identity/style when relevant. Request: ' + prompt},
            {'type': 'input_image', 'image_url': img}
        ]
        input_obj = [{'role': 'user', 'content': content}]
    elif schema == 'chatgpt_multimodal':
        content = [
            {'type': 'text', 'text': 'Use the image generation tool to create a new image based on the reference image. Preserve the main person identity/style when relevant. Request: ' + prompt},
            {'type': 'image_url', 'image_url': {'url': img}}
        ]
        input_obj = [{'role': 'user', 'content': content}]
    else:
        raise ValueError(schema)

    payload = json.dumps({
        'model': model,
        'instructions': 'You are a helpful assistant. Use tools when available.',
        'input': input_obj,
        'store': False,
        'tools': [{'type': 'image_generation'}],
        'reasoning': {'effort': effort},
        'include': [],
        'tool_choice': 'auto',
        'parallel_tool_calls': True,
        'stream': True
    })
    conn = http.client.HTTPSConnection('chatgpt.com', context=ssl.create_default_context(), timeout=240)
    conn.request('POST', '/backend-api/codex/responses', body=payload, headers={
        'Authorization': 'Bearer ' + token,
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream'
    })
    resp = conn.getresponse()
    raw = resp.read().decode('utf-8', errors='replace')
    status = resp.status
    conn.close()
    if status != 200:
        return {'success': False, 'error': 'HTTP %s: %s' % (status, raw[:1000])}
    matches = re.findall(r'(iVBOR[A-Za-z0-9+/=]{1000,})', raw)
    if not matches:
        return {'success': False, 'error': 'No image data in response', 'raw_excerpt': raw[:1500]}
    img_bytes = base64.b64decode(matches[0])
    with open(output, 'wb') as f:
        f.write(img_bytes)
    revised = ''
    m = re.search(r'"revised_prompt"\s*:\s*"([^"]*)"', raw)
    if m:
        revised = m.group(1)
    return {'success': True, 'path': output, 'size': len(img_bytes), 'revised_prompt': revised, 'schema': schema}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('prompt')
    ap.add_argument('--image', required=True)
    ap.add_argument('-o', '--output', default='codex_image_edit.png')
    ap.add_argument('--model', default='gpt-5.4')
    ap.add_argument('--effort', default='low', choices=['low','medium','high'])
    ap.add_argument('--schema', default='responses_multimodal', choices=['responses_multimodal','chatgpt_multimodal'])
    args = ap.parse_args()
    token = get_token()
    print('Generating image from reference...', flush=True)
    res = call_api(token, args.prompt, args.image, args.output, args.model, args.effort, args.schema)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    if not res.get('success'):
        sys.exit(1)

if __name__ == '__main__':
    main()
