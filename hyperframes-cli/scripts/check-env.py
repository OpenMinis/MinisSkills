#!/usr/bin/env python3
"""
check-env.py — HyperFrames 环境自检
检查 minis-browser-use、ffmpeg、依赖 skill 是否就绪。
输出 JSON，供 SKILL.md 中的检查流程使用。

用法:
  python3 check-env.py           # 完整检查，打印人类可读报告
  python3 check-env.py --json    # 输出 JSON（供脚本使用）
  python3 check-env.py --fix     # 自动安装缺失的 skill
"""

import sys, os, json, shutil, subprocess, argparse
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--json', action='store_true', dest='as_json')
parser.add_argument('--fix',  action='store_true')
args = parser.parse_args()

SKILLS_DIR = Path('/var/minis/skills')

# ── 需要检查的依赖 ─────────────────────────────────────────────────────────────
REQUIRED_SKILLS = [
    {
        'name': 'hyperframes',
        'repo': 'heygen-com/hyperframes',
        'subdir': 'skills',
        'desc': '合成创作（HTML + GSAP 动画）',
    },
    {
        'name': 'hyperframes-cli',
        'repo': 'heygen-com/hyperframes',
        'subdir': 'skills',
        'desc': 'CLI 工具 + Minis 渲染（hf-render.py）',
    },
]

REQUIRED_TOOLS = [
    {
        'name': 'minis-browser-use',
        'check': lambda: shutil.which('minis-browser-use') is not None,
        'desc': 'Minis 内置浏览器控制工具',
        'fix': None,  # 内置工具，无法自动安装
    },
    {
        'name': 'ffmpeg',
        'check': lambda: shutil.which('ffmpeg') is not None,
        'desc': '视频编码工具',
        'fix': 'apk add ffmpeg',
    },
]

# ── 检查函数 ───────────────────────────────────────────────────────────────────
def check_tool(tool):
    ok = tool['check']()
    return {'name': tool['name'], 'ok': ok, 'desc': tool['desc'], 'fix': tool['fix']}

def check_skill(skill):
    path = SKILLS_DIR / skill['name']
    skill_md = path / 'SKILL.md'
    ok = path.exists() and skill_md.exists()
    return {
        'name': skill['name'],
        'ok': ok,
        'desc': skill['desc'],
        'path': str(path),
        'repo': skill['repo'],
        'subdir': skill['subdir'],
    }

def install_skill(skill_info):
    """调用 install-skill.py 安装缺失的 skill。"""
    installer = Path(__file__).parent / 'install-skill.py'
    if not installer.exists():
        # fallback: 同目录下找
        installer = SKILLS_DIR / 'hyperframes-cli' / 'scripts' / 'install-skill.py'
    cmd = [
        sys.executable, str(installer),
        skill_info['name'],
        '--repo', skill_info['repo'],
        '--subdir', skill_info['subdir'],
    ]
    result = subprocess.run(cmd, capture_output=False)
    return result.returncode == 0

def install_tool(tool):
    """安装缺失的系统工具。"""
    if not tool['fix']:
        return False
    result = subprocess.run(tool['fix'].split(), capture_output=False)
    return result.returncode == 0

# ── 主检查流程 ─────────────────────────────────────────────────────────────────
def main():
    tool_results  = [check_tool(t) for t in REQUIRED_TOOLS]
    skill_results = [check_skill(s) for s in REQUIRED_SKILLS]

    all_ok = all(r['ok'] for r in tool_results + skill_results)

    if args.as_json:
        print(json.dumps({
            'ok': all_ok,
            'tools': tool_results,
            'skills': skill_results,
        }, ensure_ascii=False, indent=2))
        return

    # ── 人类可读报告 ──────────────────────────────────────────────────────────
    print("\n🔍 HyperFrames 环境检查\n")

    print("工具依赖:")
    for r in tool_results:
        icon = '✅' if r['ok'] else '❌'
        print(f"  {icon} {r['name']} — {r['desc']}")
        if not r['ok']:
            if r['fix']:
                print(f"     修复: {r['fix']}")
            else:
                print(f"     ⚠️  {r['name']} 是 Minis 内置工具，请更新 Minis App 到最新版本")

    print("\nSkill 依赖:")
    for r in skill_results:
        icon = '✅' if r['ok'] else '❌'
        print(f"  {icon} {r['name']} — {r['desc']}")
        if not r['ok']:
            print(f"     安装命令:")
            print(f"     python3 {SKILLS_DIR}/hyperframes-cli/scripts/install-skill.py \\")
            print(f"       {r['name']} --repo {r['repo']} --subdir {r['subdir']}")

    if all_ok:
        print("\n✅ 环境检查通过，可以开始使用 HyperFrames！")
    else:
        print("\n❌ 存在缺失依赖，请按上面的指引安装后重试。")

        if args.fix:
            print("\n🔧 自动修复模式...\n")
            for r in tool_results:
                if not r['ok'] and r['fix']:
                    print(f"安装 {r['name']}...")
                    install_tool(next(t for t in REQUIRED_TOOLS if t['name'] == r['name']))
            for r in skill_results:
                if not r['ok']:
                    print(f"\n安装 skill: {r['name']}...")
                    ok = install_skill(r)
                    if ok:
                        print(f"✅ {r['name']} 安装成功")
                    else:
                        print(f"❌ {r['name']} 安装失败，请手动安装")
            print("\n重启对话后所有 skill 即可生效。")

if __name__ == '__main__':
    main()
