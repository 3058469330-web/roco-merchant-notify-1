# 洛克王国远行商人提醒 · 部署指南

把这个项目部署到你的 GitHub 仓库,定时抓取远行商人商品并推送到微信（pushplus）。

## 你需要先准备 3 样东西

| 项目 | 在哪获取 | 说明 |
|---|---|---|
| GitHub 仓库 | github.com 新建一个仓库 | 存放本项目代码 |
| 咸鱼 API 令牌 | https://apii.xianyuw.cn 注册,个人中心领取 | 免费,用于拉取商人数据 |
| pushplus 用户令牌 | https://www.pushplus.plus 注册,登录后「一对多消息」页查看 | 免费,用于接收微信推送 |

> 这两个值(GitHub Secrets `ROCOM_TOKEN` 和 `PUSHPLUS_TOKEN`)都是敏感信息,只能填进仓库的 Secrets,不要写进代码或聊天记录。

## 第一步:推到你的 GitHub 仓库

```bash
# 在项目目录初始化并推送
cd roco-merchant-notify
git init
git add .
git commit -m "feat: 洛克王国远行商人提醒"

# 换成你自己的仓库地址
git remote add origin https://github.com/<你的用户名>/<仓库名>.git
git push -u origin main
```

## 第二步:配置仓库 Secrets

GitHub 仓库 → Settings → Secrets and variables → Actions → New repository secret,添加两个:

- `ROCOM_TOKEN` = 咸鱼 API 令牌
- `PUSHPLUS_TOKEN` = pushplus 用户令牌

## 第三步:配置定时触发

**方式 A(推荐,免 PAT)**:在仓库的 `.github/workflows/notify.yml` 顶部加 cron 定时:

```yaml
on:
  workflow_dispatch:
  schedule:
    - cron: '0 0 12 16 20 * *'   # 每天 8/12/16/20 点(UTC+8)
```

推送后 GitHub 会自动按点触发。

**方式 B(原项目方式,cron-job.org)**:在 cron-job.org 建 4 个 job(每天 08/12/16/20,Asia/Shanghai):

```text
URL: https://api.github.com/repos/<你的用户名>/<仓库名>/actions/workflows/notify.yml/dispatches
方法: POST
Headers: Authorization: Bearer <GitHub PAT>  /  Content-Type: application/json
Body: {"ref":"main"}
```

GitHub PAT 在 github.com/settings/tokens 生成,勾选 `repo` 和 `workflow` 权限。

## 第四步:手动验证

仓库 Actions → `远行商人提醒` → Run workflow,看日志是否推送成功。

只有商人开市且有商品时才会推送;未开市不打扰(符合原项目规则)。

## 本地测试(可选)

```bash
export ROCOM_TOKEN=你的咸鱼令牌
export PUSHPLUS_TOKEN=你的pushplus令牌
python3 main.py
```

## 常见问题

- **收到 401**:ROCOM_TOKEN 没配或失效,去咸鱼 API 平台核对令牌。
- **不推送**:多半是当前商人未开市或没有商品,属正常(原项目就是这样设计的)。
- **pushplus 报错**:确认 PUSHPLUS_TOKEN 正确且账号已完成实名认证(pushplus 要求实名后才能调发送接口)。

详细架构与维护说明见 [MAINTENANCE.md](./MAINTENANCE.md)。
