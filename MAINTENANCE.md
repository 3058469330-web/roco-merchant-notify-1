# 洛克王国远行商人提醒 · 维护文档

> 面向未来要修改此项目的 AI / 开发者。先读本文，再动手。
> 目标：让后来者（含 AI）不看长对话也能准确理解架构、改对地方、不踩坑。

---

## 1. 这是什么

一个**完全免费**的远行商人商品提醒脚本：每天固定几个时间点拉取「咸鱼API开放平台」的远行商人数据，**只在这位商人开市且有商品时**，把商品清单（markdown 文字）推送到**微信（pushplus）**。

- 数据源：咸鱼API开放平台（[apii.xianyuw.cn](https://apii.xianyuw.cn/)），免费注册领 Token
- 推送出口：pushplus（[www.pushplus.plus/send](https://www.pushplus.plus/send)，markdown 模板）
- 运行引擎：GitHub Actions（公开仓库，免费额度）
- 定时器：cron-job.org（外部精准定时，替代 GitHub 内置 `schedule`）

**全链路零成本。**

---

## 2. 触发架构（最重要，先看这）

```
cron-job.org（每天北京时间 08:03 / 12:03 / 16:03 / 20:03 触发）
   │  POST https://api.github.com/repos/wwwqqq001/roco-merchant-notify/actions/workflows/notify.yml/dispatches
   │  Headers: Authorization: Bearer <GitHub PAT>   Content-Type: application/json
   │  Body:    {"ref":"main"}
   ▼
GitHub Actions 跑「远行商人提醒」workflow（.github/workflows/notify.yml）
   │  checkout → setup-python → pip install requests → python main.py
   ▼
main.py
   │  1) 轮询咸鱼API（最多 2 次）取商人数据
   │  2) 若 开市 且有商品 → 推 pushplus 微信（markdown）
   │  3) 若 未开市 → 只打日志，不推送
   ▼
微信（pushplus 服务号）
```

**分工清晰**：
- **cron-job.org = 定时器**（保证按点、精准触发）
- **GitHub Actions = 执行引擎**（真实跑 Python）
- **pushplus = 通知出口**（脚本直接调）

---

## 3. 仓库文件

```
roco-merchant-notify/
├── .github/workflows/notify.yml   workflow：仅 workflow_dispatch 触发，无 inputs
├── .gitignore                     忽略 __pycache__ / *.pyc
├── README.md                      面向使用者的部署说明
├── MAINTENANCE.md                 本文档（面向维护者/AI）
└── main.py                        主脚本（逻辑 + 推送）
```

---

## 4. 每个配置块的现状与改动方式

### 4.1 cron-job.org 定时（外部，改这里要动 cron-job 账号）

- 平台：cron-job.org
- **jobId：`8203256`**，标题「远行商人提醒(08/12/16/20)」
- 一个 job 覆盖 4 个时间点，通过 `schedule.hours: [8,12,16,20]` + `minutes: [3]`
- 时区 ${timezone}=Asia/Shanghai
- 通过 **REST API** 管理（不是网页点按钮）

**关键 API 认知（踩过的坑，务必记住）**：

1. **没有「立即运行」API**。手动跑请直接走 GitHub（见 §6），别想着调 cron-job 触发。
2. 请求头/请求体字段**不在顶层**，而在 `extendedData` 下：
   ```json
   {
     "job": {
       "extendedData": {
         "headers": { "Authorization": "Bearer <PAT>", "Content-Type": "application/json" },
         "body": "{\"ref\":\"main\"}"
       }
     }
   }
   ```
   顶层 `requestHeaders`/`requestBody` 是**错的**、不会生效（我第一次就建空 headers 进坑）。若 job 详情里 `extendedData.headers` 为空数组，说明没配好。
3. 改定时用 `PATCH /jobs/<jobId>`，只传要改的字段。
4. 增删请求头/请求体后，务必 `GET /jobs/<jobId>` 复核 `extendedData.headers` 与 `extendedData.body` 是否真正写入。

**当前调度**：每天 **08:03 / 12:03 / 16:03 / 20:03**（时区 Asia/Shanghai）。设 `:03` 是为了避开整点高峰。

### 4.2 GitHub Secrets（改这里）

仓库 `wwwqqq001/roco-merchant-notify` → Settings → Secrets and variables → Actions：

| Secret | 作用 | 备注 |
|---|---|---|
| `ROCOM_TOKEN` | 咸鱼API数据源令牌 | 必填，从 apii.xianyuw.cn 个人中心获取 |
| `PUSHPLUS_TOKEN` | pushplus 用户令牌 | 必填，脚本用它调推送接口 |

**曾经有/别混淆**：`WEBHOOK_TOKEN`/`CALLBACK_URL` 是「接入 checkin-cron-worker 平台」时代的残留，**已删除**；本方案不连该平台，不要加回。

### 4.3 GitHub workflow（.github/workflows/notify.yml）

- `name`: 远行商人提醒
- 触发：仅 `workflow_dispatch:`（**没有** `on: schedule`，定时全交给 cron-job）
- 没有必填 inputs（cron-job 直接 POST，不需要 job_id/run_id/callback_url）
- job `notify`（ubuntu-latest, timeout 15min）：checkout → setup-python 3.11 → pip install requests → `python main.py`
- 环境变量：`ROCOM_TOKEN: ${{ secrets.ROCOM_TOKEN }}`、`PUSHPLUS_TOKEN: ${{ secrets.PUSHPLUS_TOKEN }}`

### 4.4 main.py 关键点

- `API_URL = "https://apii.xianyuw.cn/api/v1/rocom-merchant"`（v1 路径）
- `PUSH_URL = "https://www.pushplus.plus/send"`（pushplus 发送接口，POST JSON）
- `MAX_RETRIES = 2`、`RETRY_INTERVAL = 60`：未开市最多轮询 2 次约 1 分钟即结束，避免空等
- `build_markdown()`：把商人数据拼成 markdown（pushplus `template=markdown`）
- `send_pushplus()`：POST pushplus 接口，`code != 200` 视为失败
- **触发逻辑**（核心规则）：只有 `status == "open" and items` 才推送；否则只 log `商人未开市，本次不推送` 并 `return 0`

---

## 5. 给未来 AI 的硬规则（禁止项）

1. **不要**把任何真实令牌写进代码、注释、README、文档或日志（`ROCOM_TOKEN`、`PUSHPLUS_TOKEN`、cron-job key、GitHub PAT 全部只放 Secret/外部配置）。
2. **不要**恢复 `on: schedule` 内置定时（会和 cron-job 双触发）。
3. **不要**把 cron-job 的 headers/body 放回顶层 `requestHeaders`（不生效，要在 `extendedData` 下）。
4. **不要**为了「回调」「平台」而给这个方案引入 checkin-cron-worker（已弃用）。
5. 改数据源路径、字段名（`items`、`round.status`、`items[].name/price/limit/kind`）时要对照咸鱼 API 实际返回，别凭猜。
6. pushplus 需要账号完成实名认证才能调用发送接口（返回码 `905`）；文字消息超长会被 pushplus 截断（`build_markdown` 已精简，不再发卡片图）。
7. Windows 下 git 会提示 LF→CRLF，正常，不影响。

---

## 6. 如何手动跑一次验证

推荐**直接在 GitHub 跑**（和 cron-job 触发的是同一条 workflow）：

```bash
gh workflow run "远行商人提醒" --repo wwwqqq001/roco-merchant-notify --ref main
```

或浏览器：仓库 → Actions → 远行商人提醒 → **Run workflow**。

看日志：

```bash
gh run list --repo wwwqqq001/roco-merchant-notify --workflow="远行商人提醒" --limit=1
gh run view <runId> --repo wwwqqq001/roco-merchant-notify --log
```

**期望输出**（开市时）：
```
[ok] pushplus 推送成功
```
未开市时（正常，不算失败）：
```
[info] 第 1/2 次: 状态=not_open...   (可能重复 2 次)
[info] 商人未开市或暂无商品，本次不推送
```

> ⚠️ 想验证推送，最好选**开市时段**（每天 08/12/16/20 点前后几分钟）去手动跑，否则会因未开市而不推送（这是设计内行为）。

---

## 7. 改动后建议自检清单

- [ ] `python -m py_compile main.py` 语法通过
- [ ] 代码里 `grep` 无真实 token / secret / webhook 明文
- [ ] 改了 workflow 记得 `git push`
- [ ] 改了 cron-job 记得 `PATCH` 并 `GET` 复核（看 `extendedData.headers` 非空、schedule 正确）
- [ ] 手动触发一次，日志看到预期分支
- [ ] 同步更新本文档（README 或 MAINTENANCE）