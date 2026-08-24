# Local Studio prototype state matrix

Source direction: `qa/source-1440x1024.png`

All states are implemented in one React flow. Stateful pages are reached through the real API journey so they retain the compiled brief, batch, selected media item, receipt, and version lineage.

| State | Trigger | Purpose | Primary action |
| --- | --- | --- | --- |
| First launch | `?state=start` | Choose provider/model/template/aspect/resolution/quality and describe an image | 开始生成 |
| Generation consent | Successful `/api/brief` | Verify compiled prompt, real settings, count, and quota impact | 确认并生成 |
| Generating | Active batch | Show non-blocking backend progress | 后台继续，打开素材库 |
| Candidate selection | Completed initial batch | Compare real library results and receipts | 选择 01 / 02 |
| Refine | Select candidate or library item | Look, revise, and preserve parent-linked versions | 生成下一版 |
| Version comparison | At least two versions | Compare the last two receipt-backed versions | 返回精修 |
| Export | Selected library item | Preview and download the current version | 导出 |
| Library | 素材库 | Reopen receipt-backed works and upload local images | 打开作品 |
| Empty library | Library has no items | Explain where local works will appear | 开始第一张 |
| Recoverable error | API or batch failure | Explain impact, preserve work, and retry safely | 重试 |

Core flow: `start → confirm → generating → candidates → refine → compare/export`.

The prototype uses the real local Studio contract:

`/api/doctor + /api/models → /api/upload → /api/brief → /api/confirm-generate → /api/batch → /api/library`

- Live local preview defaults to the real Studio at `127.0.0.1:8765`.
- QA can explicitly point `STUDIO_BACKEND_URL` to a `--fixture` Studio; fixture mode is visibly labelled and does not consume provider quota.
- `/studio-api` is guarded to loopback clients only. Hosted builds return a fail-closed 503 because a remote Worker cannot safely access the user's local Studio.
