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
    SLOT_CACHE_FILE 选填  时段去重缓存文件路径
"""

import os
import sys
import time
from datetime import datetime, timezone, timedelta

import requests

API_URL = "https://apii.xianyuw.cn/api/v1/rocom-merchant"
PUSH_URL = "https://www.pushplus.plus/send"

MAX_RETRIES = 3
RETRY_INTERVAL = 45

KIND_LABEL = {"pet": "精灵", "prop": "道具", "item": "道具"}

# 时段锚点：8/12/16/20 点 ±75 分钟
SLOT_HOURS = (8, 12, 16, 20)
SLOT_WINDOW_MIN = 75

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


def already_pushed_this_slot(slot_hour: int, now_cn: datetime) -> bool:
    """通过读取本地 cache 文件判断当前时段是否已推过。

    cache 文件由 notify.yml 在两次运行之间通过 actions/cache 保留，
    内容格式：每行 "YYYY-MM-DD HH"，代表当天该时段已推过。
    """
    cache_file = os.environ.get("SLOT_CACHE_FILE", "/tmp/rocom_slot_cache.txt")
    if not os.path.exists(cache_file):
        return False
    try:
        today = now_cn.strftime("%Y-%m-%d")
        slot_key = f"{today} {slot_hour:02d}"
        with open(cache_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip() == slot_key:
                    print(f"[info] 当前时段 {slot_hour:02d}:00 已推过（cache hit），跳过")
                    return True
    except Exception as e:
        print(f"[warn] 读 slot cache 失败: {e}，按未推送处理")
    return False


def mark_pushed_this_slot(slot_hour: int, now_cn: datetime) -> None:
    """记录当前时段已推送，写入 cache 文件。"""
    cache_file = os.environ.get("SLOT_CACHE_FILE", "/tmp/rocom_slot_cache.txt")
    try:
        today = now_cn.strftime("%Y-%m-%d")
        slot_key = f"{today} {slot_hour:02d}"
        existing = set()
        if os.path.exists(cache_file):
            with open(cache_file, "r", encoding="utf-8") as f:
                existing = {line.strip() for line in f if line.strip()}
        existing.add(slot_key)
        with open(cache_file, "w", encoding="utf-8") as f:
            f.write("\n".join(sorted(existing)) + "\n")
    except Exception as e:
        print(f"[warn] 写 slot cache 失败: {e}")


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
        if force_push:
            current_slot = now_cn.hour
            print(f"[info] FORCE_PUSH 已启用，跳过时段窗口判断")
        else:
            print(f"[info] 当前 {now_cn.strftime('%H:%M')} 不在推送时段窗口（{SLOT_HOURS} ±{SLOT_WINDOW_MIN}min），跳过")
            return 0

    print(f"[info] 当前 {now_cn.strftime('%H:%M')} 命中时段 {current_slot:02d}:00 ±{SLOT_WINDOW_MIN}min")

    # —— 轮询等待数据刷新/开市 ——
    data = None
    for attempt in range(1, MAX_RETRIES + 1):
        data = fetch_merchant(rocom_token, refresh=(attempt > 1))
        status = data.get("round", {}).get("status")
        if data.get("items"):
            break
        print(f"[info] 第 {attempt}/{MAX_RETRIES} 次: 状态={status}，"
              f"商品数={data.get('item_count', 0)}，{RETRY_INTERVAL}s 后重试")
        if attempt < MAX_RETRIES:
            time.sleep(RETRY_INTERVAL)

    status = data.get("round", {}).get("status")

    # —— 时段去重（仅正常推送模式生效）——
    if not force_push and already_pushed_this_slot(current_slot, now_cn):
        return 0

    # —— 开市判断（以商品数据为准；status 切换有滞后，有商品即视为已开市）——
    if not force_push and not data.get("items"):
        print("[info] 商人暂无商品，本次不推送")
        return 0

    if force_push and not data.get("items"):
        print("[info] FORCE_PUSH 已启用,忽略开市判断,强制推送当前数据")

    merchant_name = data.get("merchant_name", "远行商人")
    title = f"🛒 [{current_slot:02d}:{now_cn.minute:02d}] {merchant_name} 已开市"
    send_pushplus(pushplus_token, title, build_markdown(data))
    if not force_push:
        mark_pushed_this_slot(current_slot, now_cn)
    print(f"[ok] pushplus 推送成功（title={title}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())

