"""Personal center commands: applied, interviews."""

from __future__ import annotations

import logging

import click
from rich.table import Table

from ._common import (
    console,
    handle_command,
    require_auth,
    structured_output_options,
)

logger = logging.getLogger(__name__)


@click.command()
@click.option("-p", "--page", default=1, type=int, help="页码 (默认: 1)")
@structured_output_options
def applied(page: int, as_json: bool, as_yaml: bool) -> None:
    """查看已投递的职位"""
    cred = require_auth()

    def _render(data: dict) -> None:
        card_list = data.get("cardList", [])
        total = data.get("totalCount", 0)

        if not card_list:
            console.print("[yellow]暂无投递记录[/yellow]")
            return

        table = Table(title=f"📮 已投递 ({total} 个)", show_lines=True)
        table.add_column("#", style="dim", width=3)
        table.add_column("职位", style="bold cyan", max_width=25)
        table.add_column("公司", style="green", max_width=20)
        table.add_column("薪资", style="yellow", max_width=12)
        table.add_column("状态", max_width=10)
        table.add_column("时间", style="dim", max_width=15)

        for i, card in enumerate(card_list, 1):
            job_info = card.get("jobInfo", card)
            brand_info = card.get("brandInfo", card)
            status_info = card.get("deliverStatusDesc", card.get("statusDesc", "-"))

            table.add_row(
                str(i),
                job_info.get("jobName", card.get("jobName", "-")),
                brand_info.get("brandName", card.get("brandName", "-")),
                job_info.get("salaryDesc", card.get("salaryDesc", "-")),
                str(status_info),
                card.get("updateTimeDesc", card.get("createTimeDesc", "-")),
            )

        console.print(table)
        if page * 15 < total:
            console.print(f"\n  [dim]▸ 更多: boss applied -p {page + 1}[/dim]")

    handle_command(cred, action=lambda c: c.get_deliver_list(page=page), render=_render, as_json=as_json, as_yaml=as_yaml)


@click.command()
@structured_output_options
def interviews(as_json: bool, as_yaml: bool) -> None:
    """查看面试邀请"""
    cred = require_auth()

    def _render(data: dict) -> None:
        interview_list = data.get("interviewList", [])

        if not interview_list:
            console.print("[yellow]暂无面试邀请[/yellow]")
            return

        table = Table(title=f"📋 面试邀请 ({len(interview_list)} 个)", show_lines=True)
        table.add_column("#", style="dim", width=3)
        table.add_column("职位", style="bold cyan", max_width=25)
        table.add_column("公司", style="green", max_width=20)
        table.add_column("时间", style="yellow", max_width=20)
        table.add_column("地点", style="blue", max_width=25)
        table.add_column("状态", max_width=10)

        for i, interview in enumerate(interview_list, 1):
            table.add_row(
                str(i),
                interview.get("jobName", "-"),
                interview.get("brandName", "-"),
                interview.get("interviewTime", "-"),
                interview.get("address", "-"),
                interview.get("statusDesc", "-"),
            )

        console.print(table)

    handle_command(cred, action=lambda c: c.get_interview_data(), render=_render, as_json=as_json, as_yaml=as_yaml)
