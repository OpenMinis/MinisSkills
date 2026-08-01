#!/usr/bin/env python3
"""
install-skill.py — Minis Skill Installer
从 GitHub 仓库下载并安装 skill 到 /var/minis/skills/

用法:
  python3 install-skill.py <skill-name> [--repo <owner/repo>] [--branch <branch>]
  python3 install-skill.py <skill-name> --list   # 列出仓库中所有可用 skill

默认仓库: OpenMinis/MinisSkills
HyperFrames skills 仓库: heygen-com/hyperframes --subdir skills

示例:
  python3 install-skill.py notion-hub
  python3 install-skill.py hyperframes --repo heygen-com/hyperframes --subdir skills
  python3 install-skill.py hyperframes-cli --repo heygen-com/hyperframes --subdir skills
"""

import sys, os, json, argparse, urllib.request, urllib.error
from pathlib import Path

SKILLS_DIR = Path('/var/minis/skills')
DEFAULT_REPO = 'OpenMinis/MinisSkills'
DEFAULT_BRANCH = 'main'

parser = argparse.ArgumentParser(description='Minis Skill Installer')
parser.add_argument('skill', nargs='?', help='skill 名称')
parser.add_argument('--repo',   default=DEFAULT_REPO, help='GitHub 仓库 owner/repo')
parser.add_argument('--branch', default=DEFAULT_BRANCH, help='分支名')
parser.add_argument('--subdir', default='',  help='仓库内子目录（如 skills）')
parser.add_argument('--list',   action='store_true', help='列出仓库中所有可用 skill')
parser.add_argument('--force',  action='store_true', help='覆盖已安装的 skill')
args = parser.parse_args()

def fetch_json(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'minis-skill-installer/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        print(f"[ERROR] HTTP {e.code}: {url}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] 网络请求失败: {e}", file=sys.stderr)
        sys.exit(1)

def download_file(url, dest: Path):
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={'User-Agent': 'minis-skill-installer/1.0'})
    with urllib.request.urlopen(req, timeout=15) as r:
        dest.write_bytes(r.read())

def install_dir(api_url, local_dir: Path, depth=0):
    """递归下载 GitHub 目录到本地。"""
    items = fetch_json(api_url)
    count = 0
    for item in items:
        dest = local_dir / item['name']
        if item['type'] == 'file':
            download_file(item['download_url'], dest)
            indent = '  ' * (depth + 1)
            print(f"{indent}✓ {item['name']}")
            count += 1
        elif item['type'] == 'dir':
            count += install_dir(item['url'], dest, depth + 1)
    return count

def list_skills(repo, branch, subdir):
    """列出仓库中所有可用 skill（顶层目录）。"""
    path = subdir if subdir else ''
    url = f"https://api.github.com/repos/{repo}/contents/{path}?ref={branch}"
    items = fetch_json(url)
    dirs = [i['name'] for i in items if i['type'] == 'dir' and not i['name'].startswith('.')]
    return sorted(dirs)

def main():
    if args.list:
        skills = list_skills(args.repo, args.branch, args.subdir)
        print(f"\n可用 skills（{args.repo}）:")
        for s in skills:
            installed = (SKILLS_DIR / s).exists()
            status = ' ✓已安装' if installed else ''
            print(f"  {s}{status}")
        return

    if not args.skill:
        parser.print_help()
        sys.exit(1)

    skill_name = args.skill
    local_dir  = SKILLS_DIR / skill_name

    # 检查是否已安装
    if local_dir.exists() and not args.force:
        print(f"⚠️  {skill_name} 已安装（{local_dir}）")
        print(f"   使用 --force 强制重新安装")
        return

    # 构建 API URL
    subpath = f"{args.subdir}/{skill_name}" if args.subdir else skill_name
    api_url = f"https://api.github.com/repos/{args.repo}/contents/{subpath}?ref={args.branch}"

    print(f"📦 安装 {skill_name}")
    print(f"   来源: {args.repo}/{subpath} @ {args.branch}")
    print(f"   目标: {local_dir}")

    count = install_dir(api_url, local_dir)
    print(f"\n✅ 安装完成！共 {count} 个文件")
    print(f"   重启对话后 skill 即可生效")

if __name__ == '__main__':
    main()
