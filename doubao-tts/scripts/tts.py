#!/usr/bin/env -S uv run --script --cache-dir /root/.cache/uv
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Doubao TTS - 豆包语音合成脚本（V3 HTTP SSE 单向流式接口）
文档：https://www.volcengine.com/docs/6561/1598757
接口：https://openspeech.bytedance.com/api/v3/tts/unidirectional/sse
鉴权：X-Api-App-Id + X-Api-Access-Key Header（即 AppID + Token）
"""

import argparse
import base64
import json
import os
import sys
import uuid
import urllib.request
import urllib.error

API_URL = "https://openspeech.bytedance.com/api/v3/tts/unidirectional/sse"


def synthesize(
    text: str,
    output_path: str,
    appid: str,
    token: str,
    resource_id: str = "seed-tts-2.0",
    speaker: str = "zh_female_shuangkuaisisi_uranus_bigtts",
    fmt: str = "mp3",
    sample_rate: int = 24000,
    speech_rate: int = 0,
    emotion: str = None,
    emotion_scale: float = None,
    loudness_rate: int = 0,
    uid: str = "minis_user",
) -> dict:
    """调用豆包 TTS V3 SSE 接口合成语音，保存到 output_path，返回结果摘要。"""

    req_id = str(uuid.uuid4())

    audio_params = {
        "format": fmt,
        "sample_rate": sample_rate,
        "speech_rate": speech_rate,
        "loudness_rate": loudness_rate,
    }
    if emotion is not None:
        audio_params["emotion"] = emotion
    if emotion_scale is not None:
        audio_params["emotion_scale"] = emotion_scale

    payload = {
        "user": {"uid": uid},
        "req_params": {
            "text": text,
            "speaker": speaker,
            "audio_params": audio_params,
        },
    }

    headers = {
        "X-Api-App-Id": appid,
        "X-Api-Access-Key": token,
        "X-Api-Resource-Id": resource_id or "seed-tts-2.0",
        "X-Api-Request-Id": req_id,
        "Content-Type": "application/json",
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(API_URL, data=data, headers=headers, method="POST")

    audio_chunks = []
    usage = {}

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            # SSE 流式读取：每行解析 data: {...}
            buffer = b""
            while True:
                chunk = resp.read(4096)
                if not chunk:
                    break
                buffer += chunk
                # 按换行分割处理 SSE 行
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    line = line.strip()
                    if not line or line.startswith(b"event:"):
                        continue
                    if line.startswith(b"data:"):
                        raw = line[5:].strip()
                        try:
                            obj = json.loads(raw)
                        except Exception:
                            continue
                        code = obj.get("code", 0)
                        msg = obj.get("message", "")

                        # 结束帧
                        if code == 20000000:
                            usage = obj.get("usage", {})
                            continue

                        # 错误帧
                        if code != 0:
                            _handle_error(code, msg)

                        # 音频帧
                        audio_b64 = obj.get("data")
                        if audio_b64:
                            audio_chunks.append(base64.b64decode(audio_b64))

    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        print(f"[ERROR] HTTP {e.code}: {err_body}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"[ERROR] Network error: {e.reason}", file=sys.stderr)
        sys.exit(1)

    if not audio_chunks:
        print("[ERROR] 未收到任何音频数据，合成失败。", file=sys.stderr)
        sys.exit(1)

    audio_bytes = b"".join(audio_chunks)
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(audio_bytes)

    return {
        "output": output_path,
        "size_bytes": len(audio_bytes),
        "text_words": usage.get("text_words", "unknown"),
    }


def _handle_error(code: int, msg: str):
    print(f"[ERROR] TTS failed (code={code}): {msg}", file=sys.stderr)
    if "quota exceeded" in msg and "concurrency" in msg:
        print("[HINT] 并发超限，请减少并发或增购。", file=sys.stderr)
    elif "speaker permission denied" in msg or "access denied" in msg:
        print("[HINT] 音色未授权，请在控制台购买或使用免费音色。", file=sys.stderr)
    elif "exceed max limit" in msg:
        print("[HINT] 文本长度超限，请缩短文本。", file=sys.stderr)
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="豆包语音合成 CLI（火山引擎 V3 HTTP SSE 单向流式接口）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  uv run --script --cache-dir /root/.cache/uv tts.py --text "你好世界" --output /tmp/hello.mp3
  uv run --script --cache-dir /root/.cache/uv tts.py --text "今天天气真好" --speaker zh_female_cancan_uranus_bigtts --output /tmp/out.mp3
  uv run --script --cache-dir /root/.cache/uv tts.py --text "Hello!" --speaker en_female_dacey_uranus_bigtts --output /tmp/en.mp3

环境变量（优先级低于命令行参数）：
  DOUBAO_TTS_APPID       AppID（X-Api-App-Id）
  DOUBAO_TTS_TOKEN       Access Token（X-Api-Access-Key）
  DOUBAO_TTS_RESOURCE_ID Resource ID（留空默认用 seed-tts-2.0）

Resource ID 说明：
  seed-tts-2.0         豆包语音合成模型 2.0（默认，支持 *_uranus_bigtts 音色）
  seed-tts-1.0         豆包语音合成模型 1.0（支持 BV*_streaming 音色）
  seed-tts-1.0-concurr 豆包语音合成模型 1.0 并发版

语速说明（--speech-rate）：
  取值范围 [-50, 100]，0 为默认，100 为 2 倍速，-50 为 0.5 倍速
        """,
    )
    parser.add_argument("--text", required=True, help="要合成的文本")
    parser.add_argument("--output", required=True, help="输出音频文件路径（如 /tmp/out.mp3）")
    parser.add_argument("--appid", default=None, help="AppID（优先于环境变量）")
    parser.add_argument("--token", default=None, help="Access Token（优先于环境变量）")
    parser.add_argument("--resource-id", default=None,
                        help="Resource ID（默认 seed-tts-1.0）")
    parser.add_argument("--speaker", default="zh_female_shuangkuaisisi_uranus_bigtts",
                        help="音色 speaker（默认 zh_female_shuangkuaisisi_uranus_bigtts 爽快思思 2.0）")
    parser.add_argument("--encoding", default="mp3",
                        choices=["mp3", "pcm", "ogg_opus"],
                        help="音频格式（默认 mp3）")
    parser.add_argument("--sample-rate", type=int, default=24000,
                        choices=[8000, 16000, 22050, 24000, 32000, 44100, 48000],
                        help="采样率（默认 24000）")
    parser.add_argument("--speech-rate", type=int, default=0,
                        help="语速 [-50, 100]，0 为默认，100 为 2 倍速（默认 0）")
    parser.add_argument("--loudness", type=int, default=0,
                        help="音量 [-50, 100]，0 为默认（默认 0）")
    parser.add_argument("--emotion", default=None,
                        help="情感（如 happy/sad/angry/surprise/narrator 等）")
    parser.add_argument("--emotion-scale", type=float, default=None,
                        help="情绪强度 [1, 5]（需配合 --emotion 使用）")
    parser.add_argument("--uid", default="minis_user", help="用户标识（任意非空字符串）")
    parser.add_argument("--json", action="store_true", dest="json_output",
                        help="以 JSON 格式输出结果")

    args = parser.parse_args()

    # 读取凭证（命令行 > 环境变量）
    appid = args.appid or os.environ.get("DOUBAO_TTS_APPID", "")
    token = args.token or os.environ.get("DOUBAO_TTS_TOKEN", "")
    resource_id = args.resource_id or os.environ.get("DOUBAO_TTS_RESOURCE_ID", "")

    if not appid:
        print("[ERROR] 未设置 AppID。请通过 --appid 参数或 DOUBAO_TTS_APPID 环境变量提供。", file=sys.stderr)
        sys.exit(1)
    if not token:
        print("[ERROR] 未设置 Token。请通过 --token 参数或 DOUBAO_TTS_TOKEN 环境变量提供。", file=sys.stderr)
        sys.exit(1)

    print(f"[INFO] 合成中... speaker={args.speaker} format={args.encoding} speech_rate={args.speech_rate}", file=sys.stderr)

    result = synthesize(
        text=args.text,
        output_path=args.output,
        appid=appid,
        token=token,
        resource_id=resource_id,
        speaker=args.speaker,
        fmt=args.encoding,
        sample_rate=args.sample_rate,
        speech_rate=args.speech_rate,
        emotion=args.emotion,
        emotion_scale=args.emotion_scale,
        loudness_rate=args.loudness,
        uid=args.uid,
    )

    if args.json_output:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"[OK] 音频已保存：{result['output']}")
        print(f"     大小：{result['size_bytes']} bytes  |  计费字符数：{result['text_words']}")


if __name__ == "__main__":
    main()
