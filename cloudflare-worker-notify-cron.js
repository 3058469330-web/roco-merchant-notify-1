// 远行商人提醒 · Cloudflare Worker 定时触发
// 每天北京时间 08:03 / 12:03 / 16:03 / 20:03 触发 GitHub workflow_dispatch,
// 由 GitHub Actions 跑 main.py 推送 pushplus 微信。
//
// Cloudflare Cron Triggers 使用 UTC 时间,北京 = UTC+8:
//   北京 08:03 = UTC 00:03  ->  cron: 3 0 * * *
//   北京 12:03 = UTC 04:03  ->  cron: 3 4 * * *
//   北京 16:03 = UTC 08:03  ->  cron: 3 8 * * *
//   北京 20:03 = UTC 12:03  ->  cron: 3 12 * * *
//
// 环境变量(Secret):
//   GH_REPO    = 3058469330-web/roco-merchant-notify-1
//   GH_WORKFLOW = notify.yml
//   GH_PAT     = 你的 GitHub Classic token(勾选 repo + workflow 权限)
//   GH_BRANCH  = main(可省略,默认 main)

export default {
  async scheduled(event, env, ctx) {
    const repo = env.GH_REPO;
    const workflow = env.GH_WORKFLOW || 'notify.yml';
    const branch = env.GH_BRANCH || 'main';
    const pat = env.GH_PAT;

    if (!repo || !pat) {
      return;
    }

    const url = `https://api.github.com/repos/${repo}/actions/workflows/${workflow}/dispatches`;
    const resp = await fetch(url, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${pat}`,
        'Accept': 'application/vnd.github+json',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ ref: branch }),
    });

    console.log(`[notify-cron] dispatch ${url} -> HTTP ${resp.status}`);
  },

  async fetch(request, env, ctx) {
    return new Response('远行商人提醒定时触发器,请勿直接访问', { status: 404 });
  },
};
