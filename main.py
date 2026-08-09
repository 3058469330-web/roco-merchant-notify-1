# -*- coding: utf-8 -*-
"""洛克王国远行商人提醒（cron-job.org 定时触发版）

数据源: 咸鱼API开放平台 https://apii.xianyuw.cn/api/v1/rocom-merchant
推送:   pushplus 微信消息推送 https://www.pushplus.plus/send
定时:   cron-job.org 通过 workflow_dispatch 触发本 workflow

规则:   只有商人开市且有商品时才推送提醒；未开市/暂无商品不打扰（仅日志）。
        最多轮询 2 次（约 1 分钟），未开市即结束，避免空等。

环境变量:
    ROCOM_TOKEN     必填  咸鱼API用户令牌（个人中心获取）
    PUSHPLUS_TOKEN  必填  pushplus 用户令牌（登录 https://www.pushplus.plus 查看）
"""

import os
import sys
import time

import requests

API_URL = "https://apii.xianyuw.cn/api/v1/rocom-merchant"
PUSH_URL = "https://www.pushplus.plus/send"

MAX_RETRIES = 2        # 数据未刷新时的重试次数（cron-job 按点触发，无需久等开市）
RETRY_INTERVAL = 60    # 重试间隔（秒）

KIND_LABEL = {"pet": "精灵", "prop": "道具", "item": "道具"}


def fetch_merchant(token: str, refresh: bool = False) -> dict:
    """拉取远行商人 JSON 数据，返回 data 字段。"""
    resp = requests.get(
        API_URL,
        params={"key": token, "refresh": "true" if refresh else "false"},
        timeout=30,
    )
    resp.raise_for_status()
    body = resp.json()
    if body.get("code") != 200:
        raise RuntimeError(f"接口返回异常: code={body.get('code')} msg={body.get('msg')}")
    return body["data"]


def build_markdown(data: dict) -> str:
    """把远行商人数据整理成 pushplus markdown 内容。"""
    round_info = data.get("round", {})
    lines = [
        f"## 🛒 {data.get('merchant_name', '远行商人')} 已开市",
        f"**{round_info.get('label', '')}**"
        f"（共 {round_info.get('total', 4)} 轮），"
        f"剩余 **{round_info.get('countdown', '未知')}**",
        "",
    ]
    for item in data.get("items", []):
        kind = KIND_LABEL.get(item.get("kind"), item.get("kind", ""))
        price = item.get("price")
        price_text = f"{price:,}" if isinstance(price, int) else str(price)
        lines.append(
            f"- 【{kind}】**{item.get('name')}**　"
            f"💰{price_text}　限购 {item.get('limit')}"
        )
    lines.append("")
    lines.append(f"时段 {data.get('subtitle', '')}")
    return "\n".join(lines)


def send_pushplus(token: str, title: str, content: str) -> None:
    resp = requests.post(
        PUSH_URL,
        json={
            "token": token,
            "title": title,
            "content": content,
            "template": "markdown",
        },
        timeout=30,
    )
    resp.raise_for_status()
    body = resp.json()
    if body.get("code") != 200:
        raise RuntimeError(f"pushplus 推送失败: code={body.get('code')} msg={body.get('msg')}")


def main() -> int:
    rocom_token = os.environ.get("ROCOM_TOKEN", "").strip()
    pushplus_token = os.environ.get("PUSHPLUS_TOKEN", "").strip()
    if not rocom_token or not pushplus_token:
        print("[error] 请配置 ROCOM_TOKEN 与 PUSHPLUS_TOKEN 环境变量")
        return 1

    # —— 轮询等待数据刷新/开市 ——
    data = None
    for attempt in range(1, MAX_RETRIES + 1):
        data = fetch_merchant(rocom_token, refresh=(attempt > 1))
        status = data.get("round", {}).get("status")
        if status == "open" and data.get("items"):
            break
        print(f"[info] 第 {attempt}/{MAX_RETRIES} 次: 状态={status}，"
              f"商品数={data.get('item_count', 0)}，{RETRY_INTERVAL}s 后重试")
        if attempt < MAX_RETRIES:
            time.sleep(RETRY_INTERVAL)

    status = data.get("round", {}).get("status")
    force_push = os.environ.get("FORCE_PUSH", "").strip().lower() in ("1", "true", "yes")

    # —— 只有开市且有商品才推送提醒 ——
    if not force_push and (status != "open" or not data.get("items")):
        print("[info] 商人未开市或暂无商品，本次不推送")
        return 0

    if force_push and (status != "open" or not data.get("items")):
        print("[info] FORCE_PUSH 已启用,忽略开市判断,强制推送当前数据")

    title = f"🛒 {data.get('merchant_name', '远行商人')} 已开市"
    send_pushplus(pushplus_token, title, build_markdown(data))
    print("[ok] pushplus 推送成功")
    return 0


if __name__ == "__main__":
    sys.exit(main())
