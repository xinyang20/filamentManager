# FilamentManager

FilamentManager 是一个面向个人 3D 打印耗材管理的本地系统。第一阶段聚焦于 Bambu Lab 打印机的局域网 MQTT 状态读取、AMS 槽位快照、耗材身份识别、库存建档、槽位绑定和事件记录。

当前版本包含：

- FastAPI 后端服务
- SQLite 本地数据库
- Bambu Lab 本地 MQTT 客户端封装
- 基于 `8883/tcp` 和 `990/tcp` 的局域网候选设备扫描
- AMS 槽位与耗材身份解析
- 打印状态机与事件去重
- Gradio 开发期前端
- Vue3 release 前端
- 合成 MQTT payload 测试

Vue3 前端已提供只读数据大屏、历史趋势、只读存储、AMS/库存和调试工作台。不集成外部库存系统。

## 目录结构

```text
.
├── backend/           # FastAPI 后端，使用 uv 管理 Python 项目
├── frontend/
│   ├── gradio/        # 开发期 Gradio UI
│   └── vue/           # Vue3 release 前端
├── test/              # 单元测试、解析测试、集成测试和合成 payload fixture
└── .docs/             # 项目开发文档和本地人工参考文档
```

## 环境要求

- Python 3.11+
- `uv`

本项目的 Python 工作流统一使用 `uv`。不要直接使用系统 Python 或 `pip` 管理项目环境。

## 启动后端

在仓库根目录运行：

```bash
uv run --project backend uvicorn filament_manager.main:app --reload --host 127.0.0.1 --port 8000
```

启动后可访问：

- API 文档：`http://127.0.0.1:8000/docs`
- 健康检查：`http://127.0.0.1:8000/api/health`

默认数据库为当前工作目录下的 `filament_manager.db`。如果从仓库根目录启动，数据库会生成在根目录；如果从 `backend/` 目录启动，数据库会生成在 `backend/` 目录。

如需指定数据库路径：

```bash
FILAMENT_MANAGER_DATABASE_URL=sqlite:///./backend/filament_manager.db \
uv run --project backend uvicorn filament_manager.main:app --reload --host 127.0.0.1 --port 8000
```

## 启动 Gradio 开发前端

先保持后端服务运行，然后在仓库根目录运行：

```bash
FILAMENT_MANAGER_API_URL=http://127.0.0.1:8000/api \
uv run --project backend python frontend/gradio/app.py
```

默认访问地址：

```text
http://127.0.0.1:7860
```

Gradio 页面包含：

- 打印机配置
- 局域网候选设备扫描，并预填候选设备的主机、名称和序列号
- 连接、断开、手动 `pushall`
- 打印状态与最近事件
- AMS 槽位状态
- 库存料卷创建与槽位绑定
- 原始 MQTT payload 与调试事件查看

## 启动 Vue3 前端

先保持后端服务运行，然后在仓库根目录运行：

```bash
cd frontend/vue
pnpm install
pnpm dev
```

默认访问地址：

```text
http://127.0.0.1:5173
```

Vue 前端默认通过 Vite proxy 访问 `http://127.0.0.1:8000/api`。如需指定 API 根地址：

```bash
VITE_FILAMENT_MANAGER_API_URL=http://127.0.0.1:8000/api pnpm dev
```

## 配置打印机

系统不会内置任何打印机地址、序列号或 access code。需要在 Gradio UI 或 REST API 中手动填写：

- `host`
- `port`
- `serial`
- `access_code`
- TLS 相关选项

保存配置后才能连接打印机 MQTT。Bambu Lab 局域网 MQTT 常用端口为 `8883`，但真实连接信息必须由用户显式输入。

也可以在 Gradio 的打印机配置页点击“扫描局域网设备”。系统会扫描当前局域网内的 `8883/tcp` 和 `990/tcp`，只保留两个特征端口同时开放、且 SSDP 返回了预期 Bambu 设备类型和基础信息的设备。可获取的信息包括设备名、型号、序列号、连接模式、绑定状态和固件版本。扫描阶段不需要 access code；扫描结果只作为候选配置，仍需用户确认并填写 access code 后保存。

## 运行测试

```bash
uv run --project backend --extra dev pytest
```

测试覆盖：

- `tray_uuid` 优先识别
- `tag_uid` 兜底识别
- 无法识别耗材时要求手动绑定
- `remain=-1` 过渡状态处理
- 打印状态机事件去重
- `stop SUCCESS` 后 `FAILED` 识别为用户取消
- `access_code` API 响应脱敏
- 手动库存料卷绑定 AMS 槽位

## 常用 API

- `GET /api/health`
- `GET /api/discovery/scan`
- `GET /api/printers`
- `POST /api/printers`
- `POST /api/printers/{printer_id}/connect`
- `POST /api/printers/{printer_id}/disconnect`
- `POST /api/printers/{printer_id}/refresh`
- `GET /api/printers/{printer_id}/state`
- `GET /api/printers/{printer_id}/ams/slots`
- `GET /api/spools`
- `POST /api/spools`
- `POST /api/ams/slots/{slot_id}/bind`
- `GET /api/debug/raw-mqtt`
- `GET /api/debug/events`

完整接口可查看 FastAPI 自动文档：`http://127.0.0.1:8000/docs`。

## 安全说明

- `access_code` 在 API 响应中默认脱敏。
- 代码中不应写入真实打印机 IP、序列号、access code 或本地私有路径。
- `.docs/local_bambu_test_environment.md` 仅供人工参考，不应被运行时代码、测试代码或工具脚本读取。
- SQLite 数据库和本地虚拟环境已通过 `.gitignore` 忽略。
