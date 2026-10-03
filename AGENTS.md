# AGENTS.md — agent-memory-v2 项目操作契约

## 项目定位

MemOS v2.0.34 基线上的二次开发项目：补齐云版「按类别抽取 + 按视图分发」管线能力。
权威开发计划与设计正文在知识库
`obsidian_file/02 项目/021 专业项目/0211 个人项目/agent_sql_memory/`（不在本仓库），
本仓库只存与源码版本绑定的正式文档（`docs/`）。

## 关键目录与入口

- `src/memos/`：上游 MemOS 源码。自有管线代码集中放新模块；对上游文件的就地修改必须登记 `PATCHES.md`。
- `src/memos/api/`：FastAPI 服务（`server_api.py` 入口 / `server_router.py` 路由 / `product_models.py` 响应契约 / `mcp_serve.py` MCP）。
- `src/memos/memories/textual/tree_text_memory/retrieve/`：召回链路（searcher/recall）。
- `docker/`：上游 compose 原件。实际部署副本在设备本地 `~/llwwds_application/docker_file/memos/`（不在同步区、不在本仓库）。
- `docs/upstream/`：被替换的上游根文档存档。

## 硬性规则

1. **基线纪律**：不重排、不格式化、不"顺手重构"上游代码；每个对上游文件的修改都要能独立回滚并在 `PATCHES.md` 有对应条目。
2. **密钥红线**：API key / token 不进源码、文档、compose 提交文件、git；真实配置只存在于部署目录 `.env`（已 gitignore），仓库只留 `.env.example`。
3. **位置契约**：运行时数据（数据卷、日志、构建缓存）只在设备本地 `llwwds_application/docker_file/memos/`；本仓库内不放 venv、缓存、日志、数据。
4. **Git**：commit/push 需用户当次授权；版本号四段式（A.B.C.D）。新增文件前检查密钥与产物。
5. **不改存储引擎**：开发只动管线两端（写入分类抽取、读出分类分发），Neo4j/Qdrant/PG 适配层保持上游原样，除非修 bug（登记 PATCHES.md）。

## 常用命令

```bash
# 语法/静态检查（本仓库无独立 lint 配置时用上游标准）
python3 -m py_compile <改动文件>

# 部署栈操作（在部署目录）
cd ~/llwwds_application/docker_file/memos && docker compose up -d && docker compose ps

# 服务冒烟
curl -s localhost:8000/health || docker compose logs memos --tail 50
```

上游测试用 pytest（`tests/`），跑之前先确认依赖安装方式（见 `docs/upstream/README.md` 或 pyproject.toml）。

## 验证要求

- 每个修改点按风险做最小验证：改召回链路至少跑一次 `/product/search/memory` 基线；改写入链路至少跑一次 add→search 闭环。
- 三个 M0 必修 bug（`_vector_recall` 断引用 / delete 不生效 / `/product` 无鉴权）修复时必须先复现、修后回归。
- 里程碑推进同步知识库计划文档与 events.db（事件 `agent_sql_memory`）。
