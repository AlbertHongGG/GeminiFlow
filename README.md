# gemini_flow

## Install

```bash
cd projects/gemini_flow
uv sync
```

## Run

```bash
uv run python cli.py chat -c user_cookies "用繁中回覆一句：測試成功"
```

Choose model:

```bash
uv run python cli.py chat -m gemini-3-pro -c user_cookies "用繁中回覆一句：測試成功"
uv run python cli.py chat -m gemini-3.5-flash -c user_cookies "用繁中回覆一句：測試成功"
```

Debug mode (prints token/response previews):

```bash
uv run python cli.py chat --debug -c user_cookies "hello"
```

## Server

Start an HTTP server:

```bash
uv run python server.py --host 127.0.0.1 --port 8000
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

Chat (returns full text + any saved image paths):

```bash
curl -X POST http://127.0.0.1:8000/chat \
	-H "Content-Type: application/json" \
	-d '{"prompt":"用繁中回覆一句：測試成功","model":"gemini-3.5-flash"}'
```

Stream (SSE):

```bash
curl -N -X POST http://127.0.0.1:8000/stream \
	-H "Content-Type: application/json" \
	-d '{"prompt":"講一個故事"}'
```

## Cookie file format

The cookies directory should contain one or more `*.json` files exported from Chrome/extensions.
Each file must be a JSON list of objects including at least: `domain`, `name`, `value`.

## Notes
- If you see `SNlM0e token not found`, your cookies are likely expired.
```
chrome.exe --user-data-dir="C:\...\GeminiFlow\user_cookies\.pw-profile"
```
