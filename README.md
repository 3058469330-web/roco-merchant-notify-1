# 洛克王国远行商人提醒

远行商人刷新时，自动把商品信息推送到微信（pushplus）。**只有开市且有商品时才推送；未开市不打扰。**

> 面向使用者看本文档。**要修改维护本项目/把它交给 AI 改，请先读 [MAINTENANCE.md](./MAINTENANCE.md)**（含架构、坑位、自检清单）。

- 数据源：[咸鱼API开放平台](https://apii.xianyuw.cn/api/rocom-merchant)（免费，注册领令牌即可）
- 定时：GitHub Actions `on: schedule` 高频触发（8/12/16/20 点前后各 1.5 小时、每 15 分钟一次）
- 推送：pushplus 微信消息推送（[pushplus.plus](https://www.pushplus.plus)，GitHub Secret `PUSHPLUS_TOKEN`）
- 运行环境：GitHub Actions（公开仓库免费）

**全链路零成本。**

## 触发架构

```text
GitHub Actions schedule（每 15 分钟，8/12/16/20 点前后各 1.5 小时）
   └─ notify.yml 跑 main.py
         └─ main.py 直接推送到 pushplus 微信
```

> 每个时段（8/12/16/20 点）只推送一次：脚本内部用去重缓存避免同时段重复推送。

## 仓库 Secrets

仓库 Settings → Secrets and variables → Actions，需配置：

| Secret 名称 | 说明 |
|---|---|
| `ROCOM_TOKEN` | 咸鱼API令牌（[apii.xianyuw.cn](https://apii.xianyuw.cn/) 个人中心获取） |
| `PUSHPLUS_TOKEN` | pushplus 用户令牌（[pushplus.plus](https://www.pushplus.plus) 登录后「一对多消息」页查看） |

> ⚠️ 两个都是敏感值，务必放 Secrets，不要写进代码或日志。

## 部署步骤

1. **配置 Secrets**：仓库 Settings → Secrets and variables → Actions，
   配置 `ROCOM_TOKEN`（咸鱼API令牌）与 `PUSHPLUS_TOKEN`（pushplus 令牌）。

2. **手动验证**：在 GitHub 仓库 Actions → `远行商人提醒` → **Run workflow** 跑一次。

## 本地测试

```bash
export ROCOM_TOKEN=你的咸鱼令牌
export PUSHPLUS_TOKEN=你的pushplus令牌
pip install requests && python main.py
```