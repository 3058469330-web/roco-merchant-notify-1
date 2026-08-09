# 洛克王国远行商人提醒

远行商人刷新时，自动把商品信息推送到微信（pushplus）。**只有开市且有商品时才推送；未开市不打扰。**

> 面向使用者看本文档。**要修改维护本项目/把它交给 AI 改，请先读 [MAINTENANCE.md](./MAINTENANCE.md)**（含架构、坑位、自检清单）。

- 数据源：[咸鱼API开放平台](https://apii.xianyuw.cn/api/rocom-merchant)（免费，注册领令牌即可）
- 定时：cron-job.org 每天北京时间 08/12/16/20 点触发 GitHub Actions
- 推送：pushplus 微信消息推送（[pushplus.plus](https://www.pushplus.plus)，GitHub Secret `PUSHPLUS_TOKEN`）
- 运行环境：GitHub Actions（公开仓库免费）

**全链路零成本。**

## 触发架构

```text
cron-job.org（准时，4 个时间点）
   └─ POST → GitHub workflow_dispatch API（须带 PAT 的 Authorization）
          └─ notify.yml 跑 main.py
                └─ main.py 直接推送到 pushplus 微信
```

## 仓库 Secrets

仓库 Settings → Secrets and variables → Actions，需配置：

| Secret 名称 | 说明 |
|---|---|
| `ROCOM_TOKEN` | 咸鱼API令牌（[apii.xianyuw.cn](https://apii.xianyuw.cn/) 个人中心获取） |
| `PUSHPLUS_TOKEN` | pushplus 用户令牌（[pushplus.plus](https://www.pushplus.plus) 登录后「一对多消息」页查看） |

> ⚠️ 两个都是敏感值，务必放 Secrets，不要写进代码或日志。

## 部署步骤（cron-job.org）

1. **获取 GitHub PAT**：`https://github.com/settings/tokens` 生成 Classic token，勾选 `repo` 和 `workflow` 权限。

2. **在 cron-job.org 建 4 个 job**（每天 08/12/16/20 点，Asia/Shanghai），每个 job 配置：
   - URL：`https://api.github.com/repos/wwwqqq001/roco-merchant-notify/actions/workflows/notify.yml/dispatches`
   - 方法：`POST`
   - Headers：`Authorization: Bearer <你的PAT>`、`Content-Type: application/json`
   - Body：`{"ref":"main"}`

3. **手动验证**：在 GitHub 仓库 Actions → `远行商人提醒` → **Run workflow** 跑一次。

## 本地测试

```bash
export ROCOM_TOKEN=你的咸鱼令牌
export PUSHPLUS_TOKEN=你的pushplus令牌
pip install requests && python main.py
```