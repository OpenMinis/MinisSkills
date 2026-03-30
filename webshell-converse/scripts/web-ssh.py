#!/usr/bin/env python3
"""
WebShell HTTP Client - 通过 HTTP API 执行远程 Shell 命令

使用方法:
    web-ssh "命令"              # 单次命令执行
    web-ssh                     # 交互模式
    
环境变量:
    WEB_SHELL_URL     服务器地址 (默认：http://127.0.0.1:8080/)
    WEB_SHELL_TOKEN   认证令牌 (默认：admin123)
"""
import os
import re
import sys
import urllib.parse
import urllib.request

# 配置（支持环境变量覆盖）
BASE_URL = os.environ.get('WEB_SHELL_URL', 'http://127.0.0.1:8080/')
TOKEN = os.environ.get('WEB_SHELL_TOKEN', 'admin123')
TIMEOUT = 30


def run_command(cmd):
    """
    执行远程命令并返回结果
    
    Args:
        cmd: Shell 命令字符串
        
    Returns:
        命令输出或错误信息
    """
    try:
        # URL 编码命令
        encoded_cmd = urllib.parse.quote(cmd, safe='')
        url = f"{BASE_URL}?cmd={encoded_cmd}&token={TOKEN}"
        
        # 发送请求
        req = urllib.request.Request(
            url,
            headers={'User-Agent': 'WebShell-Client/2.0'}
        )
        with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
            html = response.read().decode('utf-8', errors='ignore')
        
        # 使用正则提取 <pre> 标签内容（更稳健）
        match = re.search(r'<pre>(.*?)</pre>', html, re.DOTALL)
        if match:
            output = match.group(1).strip()
            return output if output else '(no output)'
        return f'Error: Unable to parse response'
        
    except urllib.error.URLError as e:
        return f'Error: Connection failed - {e.reason}'
    except TimeoutError:
        return 'Error: Command timed out after {}s'.format(TIMEOUT)
    except Exception as e:
        return f'Error: {type(e).__name__}: {e}'


def interactive_shell():
    """交互式 shell，类似 SSH 客户端体验"""
    print('=' * 55)
    print('WebShell Interactive Client v2.0')
    print(f'Target: {BASE_URL}')
    print(f'Token: {TOKEN[:4]}***')
    print('Commands: exit/quit to leave, ctrl+c to interrupt')
    print('=' * 55)
    
    prompt = '$ '
    
    while True:
        try:
            cmd = input('\n{}'.format(prompt)).strip()
            
            if not cmd:
                continue
            
            if cmd.lower() in ('exit', 'quit', 'q'):
                print('\nBye!')
                break
            
            result = run_command(cmd)
            if result:
                print(result)
                
        except KeyboardInterrupt:
            print('\n\nBye!')
            break
        except EOFError:
            print('\nBye!')
            break


def main():
    """主入口函数"""
    if len(sys.argv) > 1:
        # 单条命令模式
        cmd = ' '.join(sys.argv[1:])
        print(run_command(cmd))
        sys.exit(0 if run_command(cmd) else 1)
    else:
        # 交互模式
        interactive_shell()


if __name__ == '__main__':
    main()
