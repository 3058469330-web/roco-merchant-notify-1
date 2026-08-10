# -*- coding: utf-8 -*-
"""洛克王国远行商人提醒（GitHub Actions 定时版）

数据源: 咸鱼API开放平台 https://apii.xianyuw.cn/api/v1/rocom-merchant
推送:   pushplus 微信消息推送 https://www.pushplus.plus/send
定时:   GitHub Actions 每 30 分钟触发一次；脚本内部按"8/12/16/20 时段"去重

规则:
    - GitHub Actions cron 不可靠（延迟 5-40 分钟），所以高频触发 + 内部去重
    - 当前时段（HH:00 ± 30 分钟）首次触发且开市则推送；同时段重复触发则跳过
    - FORCE_PUSH=1 跳过去重，强制推送（调试用）

环境变量:
    ROCOM_TOKEN     必填  咸鱼API用户令牌（个人中心获取）
    PUSHPLUS_TOKEN  必填  pushplus 用户令牌（登录 https://www.pushplus.plus 查看）
    FORCE_PUSH      选填  设为 1/true/yes 时跳过去重与开市判断，强制推送
"""

import os
import sys
import time
from datetime import datetime, timezone, timedelta

import requests

API_URL = "https://apii.xianyuw.cn/api/v1/rocom-merchant"
PUSH_URL = "https://www.pushplus.plus/send"
HISTORY_URL = "https://www.pushplus.plus/api/msg/list"

MAX_RETRIES = 2
RETRY_INTERVAL = 60

KIND_LABEL = {"pet": "精灵", "prop": "道具", "item": "道具"}

# 时段锚点：8/12/16/20 点 ±30 分钟
SLOT_HOURS = (8, 12, 16, 20)
SLOT_WINDOW_MIN = 30

CN_TZ = timezone(timedelta(hours=8))


def fetch_merchant(token: str, refresh: bool = False) -> dict:
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


def already_pushed_this_slot(token: str, slot_hour: int, now_cn: datetime) -> bool:
    """查询 pushplus 当天历史消息，判断当前时段是否已发过开市推送。"""
    try:
        start_ts = int(now_cn.replace(hour=0, minute=0, second=0, microsecond=0).timestamp() * 1000)
        resp = requests.get(
            HISTORY_URL,
            params={"token": token, "startTime": start_ts, "endTime": int(now_cn.timestamp() * 1000), "pageSize": 50},
            timeout=15,
        )
        resp.raise_for_status()
        body = resp.json()
    except Exception as e:
        print(f"[warn] 查 pushplus 历史失败: {e}，按未推送处理")
        return False

    if body.get("code") not in (200, 0):
        print(f"[warn] pushplus 历史接口异常 code={body.get('code')}，按未推送处理")
        return False

    records = (body.get("data") or {}).get("list") or body.get("data") or []
    slot_prefix = f"[{slot_hour:02d}:"
    for r in records:
        title = r.get("title") or ""
        ts_ms = r.get("sendTime") or r.get("createTime") or 0
        if not title.startswith("🛒") or "已开市" not in title:
            continue
        if not title.startswith(slot_prefix):
            continue
        try:
            ts = datetime.fromtimestamp(int(ts_ms) / 1000, tz=CN_TZ)
        except Exception:
            continue
        if ts.date() != now_cn.date():
            continue
        print(f"[info] 当前时段 {slot_hour:02d}:00 已推过（{title} @ {ts.strftime('%H:%M:%S')}），跳过")
        return True
    return False


def main() -> int:
    rocom_token = os.environ.get("ROCOM_TOKEN", "").strip()
    pushplus_token = os.environ.get("PUSHPLUS_TOKEN", "").strip()
    if not rocom_token or not pushplus_token:
        print("[error] 请配置 ROCOM_TOKEN 与 PUSHPLUS_TOKEN 环境变量")
        return 1

    force_push = os.environ.get("FORCE_PUSH", "").strip().lower() in ("1", "true", "yes")

    # —— 判断是否处于有效时段（8/12/16/20 ±30 分钟）——
    now_cn = datetime.now(CN_TZ)
    current_slot = None
    for h in SLOT_HOURS:
        diff = abs((now_cn.hour - h) * 60 + now_cn.minute)
        if diff <= SLOT_WINDOW_MIN:
            current_slot = h
            break

    if not current_slot:
        print(f"[info] 当前 {now_cn.strftime('%H:%M')} 不在推送时段窗口（{SLOT_HOURS} ±{SLOT_WINDOW_MIN}min），跳过")
        return 0

    print(f"[info] 当前 {now_cn.strftime('%H:%M')} 命中时段 {current_slot:02d}:00 ±{SLOT_WINDOW_MIN}min")

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

    # —— 时段去重（仅正常推送模式生效）——
    if not force_push and already_pushed_this_slot(pushplus_token, current_slot, now_cn):
        return 0

    # —— 开市判断 ——
    if not force_push and (status != "open" or not data.get("items")):
        print("[info] 商人未开市或暂无商品，本次不推送")
        return 0

    if force_push and (status != "open" or not data.get("items")):
        print("[info] FORCE_PUSH 已启用,忽略开市判断,强制推送当前数据")

    merchant_name = data.get("merchant_name", "远行商人")
    title = f"🛒 [{current_slot:02d}:{now_cn.minute:02d}] {merchant_name} 已开市"
    send_pushplus(pushplus_token, title, build_markdown(data))
    print(f"[ok] pushplus 推送成功（title={title}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
