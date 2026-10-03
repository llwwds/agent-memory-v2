# UPSTREAM — 上游基线登记

本仓库是 [MemTensor/MemOS](https://github.com/MemTensor/MemOS)（Apache-2.0）的二次开发项目，
采用 **固定版本 vendoring** 模式：上游源码整体导入本仓库作为基线，自有开发叠加其上。

## 修改声明（Apache-2.0 §4(b) 合规）

This repository is a modified version of MemOS, licensed under the Apache License, Version 2.0.
Original copyright and license are retained in [`LICENSE`](./LICENSE). All intentional deviations
from the upstream baseline are tracked in [`PATCHES.md`](./PATCHES.md).

## 当前基线

| 项 | 值 |
| --- | --- |
| 上游仓库 | https://github.com/MemTensor/MemOS |
| 上游版本 | `v2.0.34`（tag） |
| 上游 commit | `41bf5c7fa89ee08ebedf3c662638b06fc29aca8d` |
| 上游 tag 日期 | 2026-09-23 |
| 导入日期 | 2026-10-03 |
| 本仓库首 commit | 基线导入 commit（message 中注明上述 hash） |

## 基线组成

- `commit 1` = 上游 `v2.0.34` 原始源码树 + 本文件（UPSTREAM.md）。
- 上游 `LICENSE`（Apache-2.0）原样保留于仓库根部；上游无 NOTICE 文件。
- 上游自带的 `README.md` / `README_ZH.md` / `AGENTS.md` 在后续项目叠层 commit 中被本项目的同名文件替换，
  原文存档于 `docs/upstream/`，并登记在 `PATCHES.md`。

## 升级流程

1. 对比上游新 tag 与当前基线的增量（`git diff` 上游 tag 树）。
2. 增量合并后，逐条重验 `PATCHES.md` 清单中的每个修改点是否仍然成立、是否需要适配。
3. 更新本文件的「当前基线」表格（新 tag、新 commit hash、导入日期）。
4. 跑全量回归（部署冒烟 + 六路管线测试）。

## 向上游提交

向上游回馈修复 PR 属于另议事项（见开发计划），不在默认流程内。
