# 项目重构说明 (Project Restructuring)

该项目已被改造为 **Antigravity-Manager** 的自动镜像备份系统。

## 📂 核心文件

- **`check_version.py`**: 核心逻辑脚本。
  - 功能：查询 GitHub API，下载资源，更新 README，生成历史记录。
  - 命令：
    - `python check_version.py`: 检查最新版并更新（用于 Hourly Job）。
    - `python check_version.py --api-history`: 输出所有版本 JSON（用于 Matrix）。
    - `python check_version.py --download <tag>`: 下载指定版本的资源。

- **`.github/workflows/auto-update.yml`**: 自动更新工作流。
  - 触发：每小时 (`0 * * * *`)。
  - 行为：若发现新版本，自动下载资源并发布 Release 到本仓库。

- **`.github/workflows/manual-backup-all.yml`**: 手动全量备份工作流。
  - 触发：手动 (`workflow_dispatch`)。
  - 行为：遍历目标仓库的**所有历史版本**，逐个同步到本仓库的 Release 中。

## 🚀 使用指南

### 1. 启用自动更新
工作流文件已就绪。你需要确保 GitHub 仓库设置中：
- `Settings` -> `Actions` -> `General` -> `Workflow permissions` 设为 **Read and write permissions** (否则无法创建 Release)。

### 2. 只有第一次需要做：全量备份
前往 GitHub 仓库的 **Actions** 页面，选择 **手动一键备份所有历史版本**，点击 **Run workflow**。
这将把 `lbjlaq/Antigravity-Manager` 的所有历史版本拉取并发布到本仓库。

### 3. 观察自动运行
之后每小时脚本会自动运行，如有新版本，会自动同步。

## ⚠️ 注意事项
- 本地 `history.json`, `VERSION`, `README.md` 已被重置，初次运行时会自动生成。
- 确保 `GITHUB_TOKEN` 权限足够。
