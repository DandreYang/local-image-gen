# local studio

本机 Studio 的正式入口：

```bash
local-image-gen studio
```

一个 Python 进程同时服务 `studio/client/` 下的 React production build 与 `/studio-api/*`。默认只绑定 `127.0.0.1:8765`。开发源位于 `prototypes/future-studio-v1/`；运行 `npm run build:local` 会把经过测试的构建原子提升到 `studio/client/`。

主路径：**描述 → 确认 → 生成 → 选择 → 打磨 → 导出**。确认卡在本地确定性生成，不会提前调用搜索/文本模型。生图结果进入 job-private 临时目录，完成 MIME/像素校验后才和 receipt 一起进入本机素材库。素材库存放于 `~/.local-image-gen`，根目录权限会收紧为当前用户可访问。

零额度验收：

```bash
local-image-gen studio --fixture
```

内部试用证据：

```bash
local-image-gen studio --report --days 7
```

报告只汇总完成率、中断、首张耗时、provider/model 和真实 MIME/像素覆盖率；不会输出提示词、路径、文件名、批次 ID 或失败正文。

`--lan` 会把本机后端暴露给同网段，并要求随机 Studio token；只在可信网络使用。当前支持的安全 Studio 通路由 `/api/doctor` 权威返回；Antigravity/Cursor 因仍依赖全权限编程代理而不会出现在 Studio 选择器中。显式 Gemini 通路只调用官方 API，缺少 `GEMINI_API_KEY` 时直接失败，不会回退到这些代理。
