# PATCHES — 对上游 MemOS 的就地修改清单

本仓库采用固定版本 vendoring（基线见 `UPSTREAM.md`）。凡对上游源码树的就地修改
（包括 bug 修复、文件替换、配置调整）逐条登记于此：**文件 + 修改点 + 理由**，
保证升级对比上游新 tag 时可逐条重验。

格式：`| # | 文件 | 修改点 | 理由 | 对应 commit |`

## 活跃清单

| # | 文件 | 修改点 | 理由 | commit |
| --- | --- | --- | --- | --- |
| P1 | `AGENTS.md` | 上游原文件移至 `docs/upstream/AGENTS.md`，替换为本项目 Agent 操作契约 | 项目规范要求根部 AGENTS.md 为本项目的操作契约；上游版本留档供升级比对 | 项目叠层 commit |
| P2 | `README.md` / `README_ZH.md` | 上游原文件移至 `docs/upstream/`，`README.md` 替换为本项目说明 | 本仓库是独立公开仓库，根 README 须描述本项目而非上游产品 | 项目叠层 commit |
| P3 | `.gitignore` | 追加本项目忽略项（`.env` 已由上游覆盖，确认无遗漏后按需追加） | 防止密钥与本地状态入库 | 项目叠层 commit |
| P4 | `.github/workflows/`（整目录移除） | 删除上游 12 个 CI/发布 workflow | 均为上游 MemTensor 的 release 流水线，引用上游 secrets 与 runner，在本 fork 中不可运行且无意义；`.github/` 其余（issue 模板、scripts）保留 | `1701156` |
| B3 | `src/memos/api/routers/server_router.py` | 新增 `_verify_api_key` 依赖并挂到 `/product` router：`MEMOS_API_KEY` 设置时强制校验 `X-API-Key` 头，未设置时保持上游开放行为 | companmem 审计 bug ③（2026-10-03 于 v2.0.34 运行时复现：任意 user_id 可读写他人记忆）；单机回环部署风险低，暴露端口前必须修 | 本 commit |

## 新增自有模块（非上游修改，不占 PATCH 条目，列出便于升级时识别）

| 位置 | 说明 |
| --- | --- |
| `UPSTREAM.md` / `PATCHES.md` | 基线与差异登记 |
| `docker/Dockerfile.v2` | 本项目 API 镜像（上游 `docker/Dockerfile` 保留未动） |
| `docker/.env.example-v2` | 本项目部署脱敏模板（上游 `.env.example*` 保留未动） |
| `apps/api-mcp-bridge/` | stdio MCP → `/product` HTTP API 桥接（上游 `mcp_serve.py` 为进程内 MOS，绕开 API 管线，不满足 v2 需求） |
| `docs/upstream/` | 被替换的上游根文档存档 |

## M0 必修 bug 复现结论（companmem 审计清单 vs v2.0.34，2026-10-03）

| # | 结论 | 依据 |
| --- | --- | --- |
| B1 `_vector_recall` 断引用 | **上游已修，不复现** | 静态：`recall.py` 中 `_vector_recall` 定义（L370）与调用（L144/212/232）均正常，`_vector_recall_ORIGINAL` 已不存在；运行时：qdrant 集合 `neo4j_vec_db` 写入/检索正常（1024 维 bge-m3） |
| B2 delete 不生效 | **上游已修（召回层面），不复现** | 运行时：`/product/delete_memory` 删除后 search 返回 0、neo4j 节点移除。残留卫生问题：qdrant 孤儿向量不清理（读取时因图库回源取全量节点而被屏蔽，不影响正确性；不做存储引擎改动，仅记录） |
| B3 `/product` 无鉴权 | **复现 → 已修复** | 复现：无凭据可 `POST /product/search` 读写他人 cube；修复见活跃清单 B3（无 key 401 / 错 key 401 / 对 key 200 / `/health` 不受影响） |

## 已关闭（上游已修 / 决定不修）

| # | 原因 |
| --- | --- |
| B1 | 上游 v2.0.34 已修（见复现结论） |
| B2 | 上游 v2.0.34 已修召回正确性；孤儿向量残留仅卫生问题，按「不改存储引擎」原则不修 |
