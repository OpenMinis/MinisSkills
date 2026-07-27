#!/usr/bin/env python3
"""渲染子进程：在自定义 fontconfig 环境下运行 weasyprint"""
import sys, os

html_path = sys.argv[1]
out_pdf = sys.argv[2]
fc_conf = sys.argv[3]

# 设置 fontconfig 配置文件
os.environ['FONTCONFIG_FILE'] = fc_conf

from weasyprint import HTML
HTML(filename=html_path).write_pdf(out_pdf)
