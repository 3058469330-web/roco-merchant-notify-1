# 洛克王国远行商人提醒 · 维护文档

> 面向未来要修改此项目的 AI / 开发者。先读本文，再动手。
> 目标：让后来者（含 AI）不看长对话也能准确理解架构、改对地方、不踩坑。

---

## 1. 这是什么

一个**完全免费**的远行商人商品提醒脚本：每天固定几个时间点拉取「咸鱼API开放平台」的远行商人数据，**只在这位商人开市且有商品时**，把商品清单（markdown 文字）推送到**微信（pushplus）**。

- 数据源：咸鱼API开放平台（[apii.xianyuw.cn](https://apii.xianyuw.cn/)），免费注册领 Token
- 推送出口：pushplus（[www.pushplus.plus/send](https://www.pushplus.plus/send)，markdown 模板）
- 运行引擎：GitHub Actions（公开仓库，免费额度）
- 定时器：Cloudflare Worker Cron Triggers 准点触发（主）+ GitHub Actions `on: schedule` 高频兜底

**全链路零成本。**

---

## 2. 触发架构（最重要，先看这）

```
GitHub Actions 内置 schedule（每 15 分钟触发，8/12/16/20 点前后各 1.5 小时）
   ▼
GitHub Actions 跑「远行商人提醒」workflow（.github/workflows/notify.yml）
   │  checkout → setup-python → pip install requests → python main.py
   ▼
main.py
   │  1) 轮询咸鱼API（最多 3 次）取商人数据
   │  2) 若 有商品 → 推 pushplus 微信（markdown）
   │  3) 若 暂无商品 → 只打日志，不推送
   ▼
微信（pushplus 服务号）
```

**分工清晰**：
- **Cloudflare Worker Cron = 准点定时器**（每天 08:03/12:03/16:03/20:03，稳定准时）
- **GitHub schedule = 高频兜底**（每 15 分钟，容忍其延迟，Worker 失效时不漏推）
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
├── cloudflare-worker-notify-cron.js  Cloudflare Worker 定时触发代码（主触发）
└── main.py                        主脚本（逻辑 + 推送）
```

---

## 4. 每个配置块的现状与改动方式

### 4.1 定时触发（双保险：外部准点 + GitHub schedule 兜底）

**策略**：Cloudflare Worker Cron Triggers 在 8/12/16/20 点准点触发 `workflow_dispatch`（主触发）；
GitHub 内置 schedule 保留为高频兜底（万一 Worker 失效也不漏）。
脚本内时段去重保证**每个时段只推一次**，双触发不会重复推送。

#### A. GitHub 内置 schedule（兜底，勿删）

- 位置：`.github/workflows/notify.yml` 的 `on.schedule`
- **cron**：`0,15,30,45 6-9,10-13,14-17,18-21 * * *`（Asia/Shanghai）
  - 即 8/12/16/20 点前后各 1.5 小时、每 15 分钟触发一次
- 高频原因是 **GitHub Actions 的 schedule 触发存在不可控延迟**（实测可到 70+ 分钟），
  必须靠多触发点 + 脚本内时段去重兜底，不能依赖单点准时触发

**关键认知（踩过的坑）**：

1. GitHub 官方明确 schedule 事件不保证准时，延迟几分钟到 1 小时+ 都可能。
2. 每个时段锚点 8/12/16/20 ±75 分钟窗口内，脚本只推送一次（靠 cache 去重）。

#### B. Cloudflare Worker 准点触发（主触发，已启用）

- 平台：Cloudflare Workers（免费版每天 Cron 限额 10 次，本方案用 4 次，够用）
- Worker 名称：`roco-notify-cron`（部署域：`roco-notify-cron.<account>.workers.dev`）
- 代码：仓库内 `cloudflare-worker-notify-cron.js`，`scheduled` handler 在每次 Cron 触发时
  调 GitHub `workflows/dispatches` API 触发 `notify.yml`
- 每天 08:03 / 12:03 / 16:03 / 20:03（Asia/Shanghai）各触发一次
- 设 `:03` 是为了避开整点高峰

**Cron 时间换算（Cloudflare 用 UTC，北京 = UTC+8）**：

| 北京 | UTC cron |
|---|---|
| 08:03 | `3 0 * * *` |
| 12:03 | `3 4 * * *` |
| 16:03 | `3 8 * * *` |
| 20:03 | `3 12 * * *` |

**Worker 环境变量（Secret）**：

| Secret | 值 |
|---|---|
| `GH_REPO` | `3058469330-web/roco-merchant-notify-1` |
| `GH_WORKFLOW` | `notify.yml` |
| `GH_PAT` | GitHub Classic token，权限勾选 **`repo`** + **`workflow`** |
| `GH_BRANCH` | `main`（可省略，默认 main） |

**部署/修改方式（wrangler CLI，需账号 CF API Token）**：

```bash
export CLOUDFLARE_API_TOKEN=<你的token> CLOUDFLARE_ACCOUNT_ID=<你的account id>
# 部署代码 + 4 条 Cron（UTC，见上表）
wrangler deploy cloudflare-worker-notify-cron.js --name roco-notify-cron \
  --triggers "3 0 * * *" "3 4 * * *" "3 8 * * *" "3 12 * * *"
# 逐个写 Secret
echo "3058469330-web/roco-merchant-notify-1" | wrangler secret put GH_REPO --name roco-notify-cron
echo "notify.yml"                             | wrangler secret put GH_WORKFLOW --name roco-notify-cron
echo "<你的GitHub PAT>"                       | wrangler secret put GH_PAT --name roco-notify-cron
```

**CF API Token 要求**（踩过的坑）：必须选「编辑 Cloudflare Workers」模板，
权限含 `账户 → Workers 脚本 → 编辑`，且**账户资源必须绑定账户**（选「所有账户」或指定账户），
只读 token（`Workers 脚本 - 读取`）无法部署。创建时在向导第 3 步把「账户资源」从默认
「不包括任何账户资源」改成「包括 → 所有账户」。

### 4.2 GitHub Secrets（改这里）

仓库 `3058469330-web/roco-merchant-notify-1` → Settings → Secrets and variables → Actions：

| Secret | 作用 | 备注 |
|---|---|---|
| `ROCOM_TOKEN` | 咸鱼API数据源令牌 | 必填，从 apii.xianyuw.cn 个人中心获取 |
| `PUSHPLUS_TOKEN` | pushplus 用户令牌 | 必填，脚本用它调推送接口 |

**曾经有/别混淆**：`WEBHOOK_TOKEN`/`CALLBACK_URL` 是「接入 checkin-cron-worker 平台」时代的残留，**已删除**；本方案不连该平台，不要加回。

### 4.3 GitHub workflow（.github/workflows/notify.yml）

- `name`: 远行商人提醒
- 触发：`workflow_dispatch`（Cloudflare Worker 准点调用）+ `on: schedule`（高频兜底，见 §4.1）
- job `notify`（ubuntu-latest, timeout 15min）：checkout → setup-python 3.11 → pip install requests → `python main.py`
- 环境变量：`ROCOM_TOKEN: ${{ secrets.ROCOM_TOKEN }}`、`PUSHPLUS_TOKEN: ${{ secrets.PUSHPLUS_TOKEN }}`

### 4.4 main.py 关键点

- `API_URL = "https://apii.xianyuw.cn/api/v1/rocom-merchant"`（v1 路径）
- `PUSH_URL = "https://www.pushplus.plus/send"`（pushplus 发送接口，POST JSON）
- `MAX_RETRIES = 3`、`RETRY_INTERVAL = 45`：暂无商品时最多轮询 3 次约 1.5 分钟即结束，避免空等
- `build_markdown()`：把商人数据拼成 markdown（pushplus `template=markdown`）
- `send_pushplus()`：POST pushplus 接口，`code != 200` 视为失败
- **触发逻辑**（核心规则）：**只要接口返回商品（`items` 非空）就推送**。
  不再要求 `round.status == "open"`，因为数据源在开市前后 `status` 切换有滞后
  （实测出现过 `status=not_open` 但 `items` 已有 1 件的情况，死等 open 会漏推）。

---

## 5. 给未来 AI 的硬规则（禁止项）

1. **不要**把任何真实令牌写进代码、注释、README、文档或日志（`ROCOM_TOKEN`、`PUSHPLUS_TOKEN`、Cloudflare Worker 里的 `GH_PAT` 全部只放 Secret/外部配置）。
2. **不要**把 `on: schedule` 移除——它是 Cloudflare Worker 失效时的兜底。两者叠加靠脚本时段去重，不会重复推送。
3. **不要**把开市判断改回 `status == "open"` 硬性条件（status 有滞后，会漏推；以 `items` 是否有数据为准）。
4. **不要**为了「回调」「平台」而给这个方案引入 checkin-cron-worker（已弃用）。
5. **不要**在 Worker 代码里硬编码 GitHub PAT 或仓库名——统一用 `env.GH_*` 读 Secret。
6. **不要**把 Cloudflare 的 cron 时间按北京时间写——Cloudflare 用 UTC，北京 = UTC+8，需换算（见 §4.1 表格）。
7. 改数据源路径、字段名（`items`、`round.status`、`items[].name/price/limit/kind`）时要对照咸鱼 API 实际返回，别凭猜。
8. pushplus 需要账号完成实名认证才能调用发送接口（返回码 `905`）；文字消息超长会被 pushplus 截断（`build_markdown` 已精简，不再发卡片图）。
9. Windows 下 git 会提示 LF→CRLF，正常，不影响。

---

## 6. 如何手动跑一次验证

推荐**直接在 GitHub 跑**（和 Cloudflare Worker 触发的是同一条 workflow）：

```bash
gh workflow run "远行商人提醒" --repo 3058469330-web/roco-merchant-notify-1 --ref main
```

或浏览器：仓库 → Actions → 远行商人提醒 → **Run workflow**。

看日志：

```bash
gh run list --repo 3058469330-web/roco-merchant-notify-1 --workflow="远行商人提醒" --limit=1
gh run view <runId> --repo 3058469330-web/roco-merchant-notify-1 --log
```

**期望输出**（有商品时）：
```
[ok] pushplus 推送成功
```
暂无商品时（正常，不算失败）：
```
[info] 第 1/3 次: 状态=not_open...   (可能重复 3 次)
[info] 商人暂无商品，本次不推送
```

> ⚠️ 想验证推送，最好选**商人刷新后**（每天 08/12/16/20 点前后几分钟）去手动跑，否则会因暂无商品而不推送（这是设计内行为）。

---

## 7. 改动后建议自检清单

- [ ] `python -m py_compile main.py` 语法通过
- [ ] 代码里 `grep` 无真实 token / secret 明文
- [ ] 改了 workflow 记得 `git push`
- [ ] 手动触发一次，日志看到预期分支
- [ ] 同步更新本文档（README 或 MAINTENANCE）