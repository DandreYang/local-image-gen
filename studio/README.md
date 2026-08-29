# local studio

本机 Studio 的正式入口：

```bash
local-image-gen studio
```

一个 Python 进程同时服务 `studio/client/` 下的 React production build 与 `/studio-api/*`。默认只绑定 `127.0.0.1:8765`。开发源位于 `prototypes/future-studio-v1/`（`src/views`、`src/components`、`src/hooks`）；运行 `npm run build:local` 会把经过测试的构建原子提升到 `studio/client/`。

主路径：**描述 → 确认 → 生成 → 选择 → 打磨 → 导出**。

- 确认卡在本地确定性生成，不调用搜索/文本模型；卡上显示的终稿逐字等于发送给模型的文本。没有命中关键词、也没有选模板时使用「自由画面」，不附加任何模板约束，比例按描述里的词（16:9 / 竖版 / 方图…）推断，否则 1:1，来源会标在卡上。
- 「用 AI 改写终稿」是确认卡上的显式动作：按所选通路家族调用一次文本模型（`POST /api/optimize-draft`），不点就不会发生。
- 改稿终稿 = 基础终稿 + 一份有序「修改要求」列表，不再层层叠加。
- 选项即能力：设置里只列出 `doctor` 判定可用的通路、它们的模型，以及模型声明的清晰度 / 质量 / 比例；Codex / OpenAI 只开放 1:1、3:2、2:3，其它比例在 UI 禁用、服务端拒绝。
- 生图结果进入 job-private 临时目录，完成 MIME/像素校验（PNG / JPEG / WebP）后才和 receipt 一起进入本机素材库；回执分开记录 requested（含 `aspect_requested`）与 actual。素材库存放于 `~/.local-image-gen`，根目录权限收紧为当前用户可访问。
- 没有任何登录时，首屏显示「接通一条通路」：每条通路的确切命令与当前状态，「重新检测」无需重启。

零额度验收（假图只写入 `<share home>/fixture-outputs`，不碰真实素材库）：

```bash
local-image-gen studio --fixture
```

内部试用证据：

```bash
local-image-gen studio --report --days 7
```

报告只汇总完成率、中断、首张耗时、provider/model 和真实 MIME/像素覆盖率；不会输出提示词、路径、文件名、批次 ID 或失败正文。

`--lan` 会把本机后端暴露给同网段，并要求随机 Studio token；只在可信网络使用。当前支持的安全 Studio 通路由 `/api/doctor` 权威返回（`studio_runtime.outputs_root` 说明图片落在哪）；Antigravity/Cursor 因仍依赖全权限编程代理而不会出现在 Studio 选择器中。显式 Gemini 通路只调用官方 API，缺少 `GEMINI_API_KEY` 时直接失败，不会回退到这些代理。
