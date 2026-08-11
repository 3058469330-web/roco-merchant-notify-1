# 洛克王国远行商人提醒

远行商人刷新时，自动把商品信息推送到微信（pushplus）。**只有开市且有商品时才推送；未开市不打扰。**

> 面向使用者看本文档。**要修改维护本项目/把它交给 AI 改，请先读 [MAINTENANCE.md](./MAINTENANCE.md)**（含架构、坑位、自检清单）。

- 数据源：[咸鱼API开放平台](https://apii.xianyuw.cn/api/rocom-merchant)（免费，注册领令牌即可）
- 定时：cron-job.org 每天 08:03/12:03/16:03/20:03 准点触发（+ GitHub schedule 高频兜底）
- 推送：pushplus 微信消息推送（[pushplus.plus](https://www.pushplus.plus)，GitHub Secret `PUSHPLUS_TOKEN`）
- 运行环境：GitHub Actions（公开仓库免费）

**全链路零成本。**

## 触发架构

```text
cron-job.org（准点，4 个时间点）
   └─ POST → GitHub workflow_dispatch API（须带 PAT 的 Authorization）
          └─ notify.yml 跑 main.py
                └─ main.py 直接推送到 pushplus 微信

兜底：GitHub Actions on: schedule 每 15 分钟高频触发，
      脚本内时段去重保证每个时段只推一次
```

> 每个时段（8/12/16/20 点）只推送一次：脚本内部用去重缓存避免同时段重复推送。

## 部署步骤

1. **配置 Secrets**：仓库 Settings → Secrets and variables → Actions，
   配置 `ROCOM_TOKEN`（咸鱼API令牌）与 `PUSHPLUS_TOKEN`（pushplus 令牌）。

2. **配 cron-job.org 准点触发**（免延迟）：
   - 在 [cron-job.org](https://cron-job.org) 注册并新建 job
   - URL：`https://api.github.com/repos/3058469330-web/roco-merchant-notify-1/actions/workflows/notify.yml/dispatches`
   - Method：`POST`
   - Headers：`Authorization: Bearer <你的GitHub PAT>`、`Content-Type: application/json`
   - Body：`{"ref":"main"}`
   - Schedule：每天 08:03 / 12:03 / 16:03 / 20:03（Asia/Shanghai）
   - GitHub PAT：Classic token，勾选 `repo` + `workflow` 权限

3. **手动验证**：在 GitHub 仓库 Actions → `远行商人提醒` → **Run workflow** 跑一次。

## 本地测试

```bash
export ROCOM_TOKEN=你的咸鱼令牌
export PUSHPLUS_TOKEN=你的pushplus令牌
pip install requests && python main.py
```