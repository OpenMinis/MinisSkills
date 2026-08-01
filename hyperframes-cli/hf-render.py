#!/usr/bin/env python3
"""
hf-render.py — HyperFrames Minis Renderer
使用 minis-browser-use set_viewport 将浏览器精确设为合成尺寸，
截图即为 Retina 高分辨率的合成画面，ffmpeg 下采样编码为 MP4。

用法:
  python3 hf-render.py <project_dir> [options]

选项:
  --fps N                        帧率 (默认 24)
  --output PATH                  输出路径 (默认 <project_dir>/renders/output.mp4)
  --quality draft|standard|high  画质 (默认 standard)
  --width W                      覆盖合成宽度 (默认从 data-width 读取)
  --height H                     覆盖合成高度 (默认从 data-height 读取)

示例:
  python3 hf-render.py /var/minis/workspace/my-video
  python3 hf-render.py /var/minis/workspace/my-video --fps 30 --quality high
"""

import sys, json, base64, subprocess, time, argparse, re, signal
from pathlib import Path

# ── CLI 参数 ───────────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser(description='HyperFrames Minis Renderer')
parser.add_argument('project_dir', help='项目目录（含 index.html）')
parser.add_argument('--fps',     type=int, default=24)
parser.add_argument('--output',  default=None)
parser.add_argument('--quality', choices=['draft','standard','high'], default='standard')
parser.add_argument('--width',   type=int, default=None)
parser.add_argument('--height',  type=int, default=None)
args = parser.parse_args()

PROJECT    = Path(args.project_dir).resolve()
INDEX      = PROJECT / 'index.html'
FPS        = args.fps
FRAMES_DIR = PROJECT / '.render_frames'
OUTPUT     = Path(args.output) if args.output else PROJECT / 'renders' / 'output.mp4'
QUALITY_BITRATE = {'draft': '2000k', 'standard': '4000k', 'high': '8000k'}[args.quality]
QUALITY_CRF     = {'draft': 28,      'standard': 23,       'high': 18     }[args.quality]

WORKSPACE = Path('/var/minis/workspace')

# ── 工具函数 ───────────────────────────────────────────────────────────────────
def mbu(*cmd_args):
    """调用 minis-browser-use，返回 data 字段。出错时打印并退出。"""
    r = subprocess.run(
        ['minis-browser-use'] + list(cmd_args) + ['--compact'],
        capture_output=True, text=True
    )
    if r.returncode != 0:
        print(f"[ERROR] minis-browser-use {cmd_args[0]}:\n{r.stderr}", file=sys.stderr)
        sys.exit(1)
    return json.loads(r.stdout).get('data', {})

def log(msg): print(msg, flush=True)

def parse_plist(text):
    """解析 Apple plist 风格 'key = value;' 文本为 dict。"""
    result = {}
    for m in re.finditer(r'(\w+)\s*=\s*([^;\n\}]+)', str(text)):
        k = m.group(1).strip()
        v = m.group(2).strip().rstrip(';').strip().strip('"')
        if   v in ('1', 'true'):  result[k] = True
        elif v in ('0', 'false'): result[k] = False
        else:
            try:    result[k] = float(v)
            except: result[k] = v
    return result

def jpeg_dimensions(data: bytes):
    """从 JPEG 字节流读取宽高（像素）。"""
    i = 0
    while i < len(data) - 4:
        if data[i] != 0xFF: i += 1; continue
        m = data[i + 1]
        if m in (0xC0, 0xC1, 0xC2):
            return (data[i+7]<<8)|data[i+8], (data[i+5]<<8)|data[i+6]
        i += 2 + ((data[i+2]<<8)|data[i+3]) if m not in (0xD8,0xD9,0xDA) else 2
    return None, None

def read_comp_meta():
    """从 index.html 的 data-width / data-height 属性读取合成尺寸。"""
    html = INDEX.read_text(encoding='utf-8')
    w = re.search(r'data-width=["\'](\d+)["\']', html)
    h = re.search(r'data-height=["\'](\d+)["\']', html)
    return (int(w.group(1)) if w else None), (int(h.group(1)) if h else None)

def project_url():
    """
    将项目路径转换为 minis:// URL。
    支持 workspace 根目录和子目录项目。
    项目必须在 /var/minis/workspace/ 下。
    """
    try:
        rel = PROJECT.relative_to(WORKSPACE)
        return f"minis://workspace/{rel}/index.html"
    except ValueError:
        print(f"[ERROR] 项目必须在 {WORKSPACE} 下，当前路径: {PROJECT}", file=sys.stderr)
        sys.exit(1)

def cleanup_frames():
    """清理临时帧目录。"""
    try:
        if FRAMES_DIR.exists():
            for f in FRAMES_DIR.iterdir():
                f.unlink()
            FRAMES_DIR.rmdir()
    except Exception as e:
        log(f"⚠️  清理失败（可手动删除 {FRAMES_DIR}）: {e}")

# ── 主流程 ─────────────────────────────────────────────────────────────────────
def main():
    if not INDEX.exists():
        print(f"[ERROR] {INDEX} not found", file=sys.stderr); sys.exit(1)

    comp_w, comp_h = read_comp_meta()
    W = args.width  or comp_w
    H = args.height or comp_h
    if not W or not H:
        print("[ERROR] 无法读取合成尺寸，请用 --width/--height 指定", file=sys.stderr)
        sys.exit(1)

    log(f"📐 合成尺寸: {W}×{H}  FPS: {FPS}  质量: {args.quality}")

    FRAMES_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    # 注册中断处理：Ctrl-C 时也要还原 viewport
    def on_interrupt(sig, frame):
        log("\n⚠️  中断，还原 viewport...")
        mbu('set_viewport', '--reset')
        cleanup_frames()
        sys.exit(1)
    signal.signal(signal.SIGINT, on_interrupt)
    signal.signal(signal.SIGTERM, on_interrupt)

    # ── Step 1: 设置 viewport = 合成尺寸 ──────────────────────────────────────
    log(f"🖥  设置 viewport → {W}×{H}")
    mbu('set_viewport', '--width', str(W), '--height', str(H))

    try:
        # ── Step 2: 导航到合成页面 ────────────────────────────────────────────
        url = project_url()
        log(f"🌐 加载: {url}")
        mbu('navigate', '--url', url)

        # ── Step 3: 等待 runtime 就绪 ─────────────────────────────────────────
        # __hf 协议必须就绪（{ duration, seek }）
        # __timelines 有值说明 GSAP 已加载；纯 CSS 动画时 __timelines 为空也允许通过
        log("⏳ 等待 runtime...")
        for _ in range(50):
            r = mbu('execute_js', '--script', '''
              var hf = window.__hf;
              var ready = !!(hf && typeof hf.seek === "function" && hf.duration > 0);
              var hasTimelines = Object.keys(window.__timelines || {}).length > 0;
              // 纯 CSS 动画时 __timelines 为空，只要 __hf 就绪即可
              return { ready: ready, dur: hf ? hf.duration : 0, hasTimelines: hasTimelines }
            ''')
            s = parse_plist(r.get('text', ''))
            if s.get('ready') and float(s.get('dur', 0)) > 0:
                DURATION = float(s['dur'])
                has_tl   = bool(s.get('hasTimelines'))
                break
            time.sleep(0.3)
        else:
            print("[ERROR] window.__hf 未就绪（超时 15s）\n"
                  "  检查 index.html 是否在 <script> 末尾暴露了:\n"
                  "  window.__hf = { get duration() { return N; }, seek(t) { ... } }",
                  file=sys.stderr)
            sys.exit(1)

        total_frames = int(DURATION * FPS)
        log(f"✅ 就绪  时长={DURATION:.2f}s  帧数={total_frames}  GSAP={'yes' if has_tl else 'no (CSS only)'}")

        # ── Step 4: 探测截图实际像素尺寸（DPR）──────────────────────────────
        log("🔍 探测截图尺寸...")
        # 先 seek 到 t=0，再截探针帧（不复用为 frame_0，避免 seek 时序问题）
        mbu('execute_js', '--script', 'window.__hf.seek(0); return true')
        probe = mbu('screenshot', '--with-base64')
        probe_bytes = base64.b64decode(probe.get('image_base64', ''))
        shot_w, shot_h = jpeg_dimensions(probe_bytes)
        if not shot_w:
            print("[ERROR] 无法读取截图尺寸", file=sys.stderr); sys.exit(1)
        dpr = round(shot_w / W)
        log(f"   截图: {shot_w}×{shot_h}  DPR={dpr}x")

        # ── Step 5: 逐帧 seek + screenshot ───────────────────────────────────
        # 每帧独立 seek，不依赖探针帧，确保 frame_0 也是精确 seek(0) 的结果
        log(f"🎬 渲染 {total_frames} 帧...")
        t0 = time.time()
        saved = 0

        for i in range(total_frames):
            t = i / FPS
            mbu('execute_js', '--script', f'window.__hf.seek({t:.6f}); return true')
            data = mbu('screenshot', '--with-base64')
            b64  = data.get('image_base64', '')
            if not b64:
                print(f"\n[WARN] 帧 {i} 截图为空，跳过", file=sys.stderr)
                continue

            (FRAMES_DIR / f"frame_{i:06d}.jpg").write_bytes(base64.b64decode(b64))
            saved += 1

            elapsed  = time.time() - t0
            fps_real = saved / elapsed if elapsed else 0
            eta      = (total_frames - saved) / fps_real if fps_real else 0
            print(f"\r  {i+1:4d}/{total_frames}  {fps_real:.1f}fps  ETA {eta:.0f}s   ", end='', flush=True)

        print()
        elapsed_cap = time.time() - t0
        log(f"✅ 截图完成  {saved}帧  {elapsed_cap:.1f}s  ({saved/elapsed_cap:.1f}fps)")

        if saved == 0:
            print("[ERROR] 没有成功截到任何帧", file=sys.stderr); sys.exit(1)

        # ── Step 6: ffmpeg 编码 ────────────────────────────────────────────────
        # Retina 截图（shot_w × shot_h）→ lanczos 下采样到目标尺寸（W × H）
        log("🎞  ffmpeg 编码...")
        vf = f"scale={W}:{H}:flags=lanczos"
        cmd = [
            'ffmpeg', '-y',
            '-framerate', str(FPS),
            '-i', str(FRAMES_DIR / 'frame_%06d.jpg'),
            '-vf', vf,
            '-c:v', 'h264_videotoolbox',
            '-b:v', QUALITY_BITRATE,
            '-pix_fmt', 'yuv420p',
            '-movflags', '+faststart',
            str(OUTPUT)
        ]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            log("⚠️  h264_videotoolbox 不可用，回退到 libx264...")
            cmd = [
                'ffmpeg', '-y',
                '-framerate', str(FPS),
                '-i', str(FRAMES_DIR / 'frame_%06d.jpg'),
                '-vf', vf,
                '-c:v', 'libx264',
                '-crf', str(QUALITY_CRF),
                '-pix_fmt', 'yuv420p',
                '-movflags', '+faststart',
                str(OUTPUT)
            ]
            r = subprocess.run(cmd, capture_output=True, text=True)
            if r.returncode != 0:
                print(f"[ERROR] ffmpeg 失败:\n{r.stderr}", file=sys.stderr); sys.exit(1)

        size_kb = OUTPUT.stat().st_size // 1024
        log(f"✅ 输出: {OUTPUT}  ({size_kb} KB)")

    finally:
        # ── Step 7: 清理 + 还原 viewport（无论成功失败都执行）────────────────
        cleanup_frames()
        mbu('set_viewport', '--reset')
        log("🔄 viewport 已还原")

    total_t = time.time() - t0
    log(f"\n🎉 完成！{DURATION:.1f}s 视频  {saved}帧  用时 {total_t:.1f}s")

if __name__ == '__main__':
    main()
