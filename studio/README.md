# local studio

本机 Studio。引擎仍是 `scripts/local_image_gen.py`。

```bash
python3 studio/server.py
```

打开 `http://127.0.0.1:8765`。默认只绑本机回环。

同一 Wi-Fi 下用手机访问：

```bash
python3 studio/server.py --lan
```

然后打开 `http://<这台电脑的局域网IP>:8765`。这会把本机订阅生图能力暴露给局域网，不要在不可信网络上开。

主路径：**整理任务** → 官方 Grok 检索补全 → 拆成单张 → 确认卡 → 每张先编译再 `--raw` 生图。出图后会用官方 Grok **看图**写评语；你再说一句，默认带着上一张改，不从零再赌。看图和改稿走官方 `api.x.ai`，没有登录/Key 时会写明，不会假装看过。

没有 `grok login` / `XAI_API_KEY` 时检索会失败，确认卡会写明，不会假装搜过。

