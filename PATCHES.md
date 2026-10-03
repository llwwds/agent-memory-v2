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
| P4 | `.github/workflows/`（整目录移除） | 删除上游 12 个 CI/发布 workflow | 均为上游 MemTensor 的 release 流水线，引用上游 secrets 与 runner，在本 fork 中不可运行且无意义；`.github/` 其余（issue 模板、scripts）保留 | 移除上游 CI commit |

## M0 必修 bug（companmem 审计，2026-10-03 对 v2.0.34 逐一复现确认）

| # | 文件 | 修改点 | 理由 | commit |
| --- | --- | --- | --- | --- |
| B1 | `src/memos/memories/textual/tree_text_memory/retrieve/recall.py` | —（待运行时复现） | 审计报告称 `_vector_recall` 断引用致向量召回静默返回 0；v2.0.34 静态检查显示该函数定义与调用均正常、`_vector_recall_ORIGINAL` 已不存在，**疑似上游已修**，M0 部署后运行时验证 | — |
| B2 | `src/memos/api/handlers/memory_handler.py`（`handle_delete_memories`） | —（待复现后修复） | 审计报告称 `/product/delete_memory` 返回成功但记忆仍可召回 | — |
| B3 | `src/memos/api/routers/server_router.py`（`router = APIRouter(prefix="/product")`） | —（待复现后修复） | 审计报告称 `/product` 路由无鉴权，任意 user_id 可读写他人记忆；本地单人风险低，暴露端口前必须修 | — |

## 已关闭（上游已修 / 决定不修）

| # | 原因 |
| --- | --- |
| — | 暂无 |
