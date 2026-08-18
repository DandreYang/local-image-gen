# local-image-gen

用本机已经登录的编程助手订阅来生图、改图。官方 API Key 只是兜底，不是前提。

[English](README.md)

Python 3.9+，只用标准库。既可以当 CLI，也可以当 Claude / Codex / Grok / Cursor / Gemini 等助手的 portable skill（`SKILL.md`）。

## 为什么做这个

多数生图 skill 一上来就要付费 Key。如果你已经 `grok login`、`codex auth login`、装了 Antigravity `agy`，或登录过 `cursor-agent`，那次登录就应该能用。这个项目先走本地订阅，再走对应官方 API。

仓库**不会**内置非官方中转。API Key 路径默认只打官方地址：

| 供应方 | 官方默认 |
| --- | --- |
| xAI / Grok Key | `https://api.x.ai/v1` |
| OpenAI | `https://api.openai.com/v1` |
| Gemini Key | `https://generativelanguage.googleapis.com/v1beta` |

只有你显式设置 `--base-url` 或 `XAI_BASE_URL` / `OPENAI_BASE_URL` / `GEMINI_BASE_URL` 时才会改地址。

## 使用前请读

- 这是给你**自己的登录**或**自己的官方 Key** 用的本地编排，不是免费生图网关。
- 生图会消耗你所选后端的配额或账单。
- `codex` 供应方是**实验项**：复用 `~/.codex/auth.json` 打未公开的 ChatGPT Codex 生图接口。它可能随时失效，也可能与 OpenAI 条款冲突。需要受支持的 `gpt-image-2` 时，请用 `--provider openai` 加 `OPENAI_API_KEY`。
- 使用订阅通道前，请自行阅读 xAI、OpenAI、Google、Cursor 的服务条款。

## 安装

```bash
git clone https://github.com/Dandre126/local-image-gen.git
cd local-image-gen
python3 scripts/local_image_gen.py --list-providers
```

把 skill 链到本机各助手（只建符号链接，不会覆盖已有实体目录）：

```bash
chmod +x install.sh
./install.sh
```

也可以只链一个：

```bash
ln -s "$(pwd)" ~/.codex/skills/local-image-gen
```

## 用法

```bash
python3 scripts/local_image_gen.py --list-providers
python3 scripts/local_image_gen.py --list-models

python3 scripts/local_image_gen.py "极简科技封面，无文字" \
  --aspect-ratio 16:9 --quality high -o outputs/cover.png

python3 scripts/local_image_gen.py "电影感城市夜景" \
  --provider grok --model grok-imagine-image-2.0 \
  --aspect-ratio 16:9 --resolution 2k --quality medium -o outputs/city.png

python3 scripts/local_image_gen.py "水彩狐狸在雪林里" \
  --provider antigravity --model gemini-3.1-flash-image \
  --aspect-ratio 3:4 --resolution 2k -o outputs/fox.png

python3 scripts/local_image_gen.py "干净的产品静物" \
  --provider openai --model gpt-image-2 --aspect-ratio 1:1 -o outputs/still.png

python3 scripts/local_image_gen.py "test" --dry-run --aspect-ratio 1:1
```

已安装该 skill 的助手应直接运行 `scripts/local_image_gen.py`，不要只给命令建议。

## 供应方

| `--provider` | 默认模型 | 订阅 / CLI | 官方 API Key |
| --- | --- | --- | --- |
| `auto` | 自动选择 | 是 | 是 |
| `grok` | `grok-imagine-image-2.0` | `grok login` | `XAI_API_KEY` |
| `antigravity` | `gemini-3.1-flash-image` | 本地 `agy` | — |
| `cursor` | `gemini-3-pro-image` | 本地 `cursor-agent` | — |
| `gemini` | `gemini-3.1-flash-image` | Nano Banana：Antigravity → Cursor → Key | `GEMINI_API_KEY` |
| `codex` | `gpt-image-2` | 实验性 `codex auth login` | —（请用 `openai`） |
| `openai` | `gpt-image-2` | — | `OPENAI_API_KEY` |
| `xai` | `grok-imagine-image-2.0` | — | `XAI_API_KEY` |

未指定 Nano Banana 模型时，`auto` 优先 Grok，然后 Antigravity，再 Codex。Cursor 只加入 Nano Banana 链路，或在你写 `--provider cursor` 时使用。

参数对照见 [`references/providers.md`](references/providers.md)。模型清单以 `--list-models` 为准。

## 配置

Key 和可选自定义 base，进程环境之后按下面顺序取第一个：

1. `--api-key-file`
2. `./.env`
3. `~/.local-image-gen.env`
4. `~/.config/local-image-gen.env`

参考 [`.env.example`](.env.example)。不要提交真实 env 文件。

单次覆盖用 `--base-url` / `--api-base`。订阅通道忽略自定义 base，继续走官方登录入口。

## 开发

```bash
python3 tests/test_local_image_gen.py
python3 scripts/local_image_gen.py --version
```

没有第三方 Python 依赖。

## 许可证

[MIT](LICENSE)
