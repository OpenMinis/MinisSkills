---
name: korea-stock
description: >
  查询韩国股市行情，包括 KOSPI / KOSDAQ 指数及成分股行情。
  使用 Naver 财经（finance.naver.com）手机版页面，无需登录。
  当用户说"韩股"、"韩国股市"、"KOSPI"、"KOSDAQ"、"三星电子"、"SK 海力士"时触发。
version: 1.0.0
---

# 韩国股市行情查询

## 数据源

Naver 财经手机版 — `finance.naver.com`
- 直接 browser_use 配合 get_readable 即可获取完整数据
- 无需任何账号，中国 IP 可直接访问

## 查询 KOSPI 指数

navigate: https://finance.naver.com/sise/sise_index.naver?code=KOSPI
wait_for_dom_stable
get_readable: 提取页面全文

读取数据包括：
- KOSPI 指数当前点位、涨跌点数、涨跌幅
- 成交量（千股）、成交额（百万韩元）
- 当日最高/最低、52 周最高/最低
- 涨跌家数
- 个人/外资/机构净买卖额
- 热门成分股实时价格

## 查询 KOSDAQ 指数

navigate: https://finance.naver.com/sise/sise_index.naver?code=KOSDAQ
get_text: 提取数据

## 查询个股行情

| 股票 | Naver 代码 |
|------|-----------|
| 三星电子 | 005930 |
| SK 海力士 | 000660 |

## 汇报格式

KOSPI: 8,476.15 (+3.55%)
  最高: 8,476.15 | 最低: 8,273.74

## 注意事项

- Naver 使用韩文，关键数据均为数值不受语言影响
- 韩国股市交易时间：北京时间 08:00-14:30
- 数据延迟约 15-20 分钟
- 中国 IP 可直接访问，无需 VPN
