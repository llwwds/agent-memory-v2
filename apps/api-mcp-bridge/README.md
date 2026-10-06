# api-mcp-bridge

agent-memory-v3 自有模块：把 MemOS `/product` HTTP API 桥接成 stdio MCP，供 Codex 等编码 agent 接入。

与上游 `memos.api.mcp_serve` 的区别：上游 MCP 在进程内实例化完整 MOS、绕开 FastAPI 管线；
本桥接只做 HTTP 转发，保证 MCP 路径与 v2 开发的「分类抽取 + 视图分发」管线同路。

## 运行（容器内，宿主机零安装）

```bash
docker run -i --rm \
  --network memos-dev_memos_network \
  -e MEMOS_API_BASE=http://memos:8000 \
  -e MEMOS_API_KEY=<见部署目录 .env> \
  memos-api-v2:dev python /app/apps/api-mcp-bridge/server.py
```

## 环境变量

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `MEMOS_API_BASE` | `http://memos:8000` | MemOS API 地址 |
| `MEMOS_API_KEY` | 空 | API 鉴权 key（B3 修复后服务端强制校验 `X-API-Key`） |
| `MEMOS_DEFAULT_USER_ID` | `llwwds` | 未显式传 user_id 时的默认用户 |
| `MEMOS_API_TIMEOUT` | `120` | HTTP 超时秒数（add 路径含 LLM 抽取，较慢） |

## Codex 接入（`~/.codex/config.toml`）

```toml
[mcp_servers.memos]
command = "docker"
args = ["run", "-i", "--rm", "--network", "memos-dev_memos_network",
        "-e", "MEMOS_API_BASE=http://memos:8000",
        "-e", "MEMOS_API_KEY=<key>",
        "memos-api-v2:dev",
        "python", "/app/apps/api-mcp-bridge/server.py"]
```

## 工具

- `remember(content, user_id?)` → `POST /product/add`
- `recall(query, user_id?)` → `POST /product/search`
