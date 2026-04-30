# FilamentManager

FilamentManager 是一个面向个人 3D 打印工作流的本地打印机运维与耗材管理系统。项目以 Bambu Lab 局域网模式为主要场景，读取本地 MQTT 与设备状态，将打印监控、AMS 状态、耗材库存、打印记录、维护提醒和调试导入导出整合在一个本地应用中。

系统默认不依赖外部云库存服务，运行数据存储在本地 SQLite 数据库中。打印机 IP、序列号、access code 等敏感配置由用户在本地填写和维护。

## 主要功能

- 打印机监控：查看打印状态、进度、温度、风扇、网络、HMS 告警、设备能力和局域网实时画面。
- AMS 管理：展示多 AMS / AMS HT 槽位、当前进料槽位、湿度温度、RFID 识别结果和槽位历史。
- 耗材管理：维护品牌、类型/系列、SKU、未开封库存、开封料卷、历史料卷、颜色映射和料卷位置。
- 自动识别：根据 AMS 上报的官方 UID、材料、系列、颜色和余量，自动关联或创建耗材记录，并处理换料过渡与历史 UID 冲突。
- 库存分析：统计总库存、未开封库存、开封库存、AMS 中料卷和各材料重量占比。
- 打印日志：根据设备状态推导打印开始、完成、取消、失败等记录。
- 延迟摄影与存储：读取打印机媒体目录，展示和下载本地可访问的延迟摄影文件。
- 维护与通知：提供本地维护提醒、事件记录、Webhook / ntfy 等通知配置。
- 调试与迁移：提供原始 MQTT、事件、系统信息、支持包、数据导出和 JSON 备份导入。

## 目录结构

```text
.
├── backend/             # FastAPI 后端，负责 API、数据库、MQTT、业务服务
├── frontend/
│   ├── vue/             # Vue 3 主前端
│   └── gradio/          # 早期开发/调试用 Gradio 前端
├── test/                # 后端测试、解析测试和合成设备 payload
├── .docs/               # 设计计划、本地说明和开发参考文档
└── filament_manager.db  # 本地 SQLite 数据库，已被 .gitignore 忽略
```

更细的代码目录说明见：

- [backend/README.md](backend/README.md)
- [frontend/README.md](frontend/README.md)

## 环境要求

- Python 3.11+
- `uv`
- Node.js 20+（推荐）
- `pnpm`
- 一台已启用局域网访问的 Bambu Lab 打印机

本项目约定：

- Python 相关命令统一使用 `uv`。
- Node 相关命令统一使用 `pnpm`。
- 不要将真实 access code、序列号、本地数据库或私有路径提交到仓库。

## 启动教程

### 1. 启动后端

在仓库根目录运行：

```bash
uv run --project backend uvicorn filament_manager.main:app --reload --host 127.0.0.1 --port 8000
```

启动后可访问：

- API 文档：`http://127.0.0.1:8000/docs`
- 健康检查：`http://127.0.0.1:8000/api/health`

默认数据库路径为启动目录下的 `filament_manager.db`。如果希望固定数据库位置，可使用环境变量：

```bash
FILAMENT_MANAGER_DATABASE_URL=sqlite:///./filament_manager.db \
uv run --project backend uvicorn filament_manager.main:app --reload --host 127.0.0.1 --port 8000
```

### 2. 启动 Vue 前端

保持后端运行，然后在另一个终端执行：

```bash
cd frontend/vue
pnpm install
pnpm dev
```

默认访问地址：

```text
http://127.0.0.1:5173
```

Vue 前端默认通过 Vite proxy 访问 `http://127.0.0.1:8000/api`。如需显式指定 API 地址：

```bash
VITE_FILAMENT_MANAGER_API_URL=http://127.0.0.1:8000/api pnpm dev
```

### 3. 配置打印机

进入前端后，在“打印机配置”中添加打印机：

- 名称
- IP / Host
- MQTT 端口，Bambu Lab 局域网模式常见为 `8883`
- 序列号
- access code
- TLS 相关选项

保存后可连接 MQTT，系统会开始接收状态、AMS、打印日志和事件数据。局域网扫描只用于发现候选设备，仍需要用户确认并填写 access code。

## 耗材与 AMS 规则

- SKU 去重以 `brand_id + type_series_id + color_name + color_hex + nominal_weight_g + filament_diameter_mm + tray_info_idx` 为准；未开封数量和备注不参与去重。
- 创建或修改 SKU 命中重复时，后端返回 `409 duplicate_filament_sku`，前端会提示编辑已有 SKU 或调整库存数量。
- 料卷状态包括 `opened_in_storage`、`loaded_in_ams`、`needs_location`、`empty`、`archived` 和 `unknown`。
- `empty` 与 `archived` 料卷保留历史记录，但不计入当前库存重量；可在“已归档/已用尽”视图中检索、查看和恢复。
- AMS 在打印中换料时会等待材料、颜色、UID 等信息稳定后再更新库存，避免过渡帧创建错误料卷。
- 如果 AMS 再次读到已用尽或已归档料卷的官方 UID，系统会进入待确认流程，由用户选择恢复旧料卷、创建新料卷或忽略本次识别。

## 设备大屏说明

- “设备大屏”将任务、温度、网络、硬件、HMS 告警和维护信息集中展示。
- HMS / 错误列表归入“网络、硬件与告警”模块：未解决记录全部显示，已解决或无影响记录只展示最近少量记录。
- 实时监控弹窗只转发局域网实时画面，不存储视频；弹窗按 16:9 等比例放大，并在小屏下自动限制尺寸。

### 4. 可选：启动 Gradio 调试前端

Gradio 页面主要用于早期开发和接口调试。后端运行后执行：

```bash
FILAMENT_MANAGER_API_URL=http://127.0.0.1:8000/api \
uv run --project backend python frontend/gradio/app.py
```

默认地址：

```text
http://127.0.0.1:7860
```

## 测试与构建

运行后端测试：

```bash
uv run --project backend --extra dev pytest
```

构建前端：

```bash
cd frontend/vue
pnpm build
```

## 贡献方法

欢迎围绕本地打印机运维、耗材管理、AMS 识别和 Bambu Lab 局域网工作流改进项目。建议按以下方式贡献：

1. 先阅读根目录 README、`backend/README.md` 和 `frontend/README.md`。
2. 新功能尽量先写清楚使用场景，避免直接引入复杂抽象。
3. 后端改动需要补充或更新 pytest 测试。
4. 前端改动需要确保 `pnpm build` 通过。
5. 不提交本地数据库、备份、日志、真实打印机凭据或私有路径。
6. 提交信息建议使用项目已有风格，例如 `feat(filament): ...`、`fix(ams): ...`。

推荐在提交前执行：

```bash
uv run --project backend --extra dev pytest
cd frontend/vue
pnpm build
```

## 安全与隐私

- `access_code` 在 API 响应中默认脱敏。
- 支持包导出会尽量脱敏，但仍建议在公开分享前人工检查。
- SQLite 数据库、运行时备份和本地虚拟环境已通过 `.gitignore` 忽略。
- 本项目只应在可信本地网络中运行，不建议直接暴露到公网。

## 开源协议

本项目采用 GNU Affero General Public License v3.0 only（`AGPL-3.0-only`）开源，完整协议见 [LICENSE](LICENSE)。

简单来说，你可以使用、学习、修改和分发本项目；如果你分发修改版，或将修改版作为网络服务提供给用户，也需要按 AGPL-3.0-only 的要求提供相应源码并保留版权与许可证声明。
