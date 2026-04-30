# FilamentManager Backend

后端使用 FastAPI、SQLite 和本地 MQTT 处理打印机状态、AMS 信息、耗材库存、事件、打印日志、局域网实时画面转发、导入导出和调试接口。

## 启动

建议在仓库根目录运行：

```bash
uv run --project backend uvicorn filament_manager.main:app --reload --host 127.0.0.1 --port 8000
```

默认数据库为启动目录下的 `filament_manager.db`。可以通过 `FILAMENT_MANAGER_DATABASE_URL` 指定 SQLite 路径。

## 测试

在仓库根目录运行：

```bash
uv run --project backend --extra dev pytest
```

## 目录说明

```text
backend/
├── pyproject.toml       # 后端项目配置和依赖声明
├── uv.lock              # uv 锁定文件
└── src/filament_manager/
    ├── main.py          # FastAPI 应用入口
    ├── schemas.py       # API 输入输出模型
    ├── api/             # HTTP 路由
    ├── core/            # 配置、安全和通用基础能力
    ├── data/            # 本地静态数据，例如 HMS 码表
    ├── db/              # SQLAlchemy 模型、会话和迁移辅助
    ├── mqtt/            # Bambu Lab MQTT 客户端、解析器和状态机
    └── services/        # 业务服务：AMS、耗材、打印日志、维护、通知、导入导出等
```

后端代码按“路由接收请求，服务层处理业务，数据库层保存状态”的方式组织。新增功能时优先复用已有 service 和 schema，不建议把业务逻辑直接写进路由函数。

## 主要接口与服务

- 打印机与状态：`/api/printers`、连接/断开、手动刷新、状态快照、实时画面和媒体存储。
- AMS：维护 AMS / AMS HT 单元、槽位、当前进料位、RFID 原始信息、槽位标签和槽位历史。
- 耗材基础数据：品牌、类型/系列、颜色映射、SKU、未开封库存和开封料卷。
- 耗材生命周期：`/api/filament/spools/{spool_id}/status` 可将料卷标记为 `empty`、`archived` 或恢复到当前库存状态。
- UID 冲突确认：`/api/filament/spools/{spool_id}/resolve-uid-conflict` 用于处理已用尽/已归档官方 UID 再次被 AMS 识别的场景。
- 观测与事件：维护提醒、HMS 语义化、事件中心、打印日志、通知配置、支持包和 JSON 导入导出。

## 耗材业务规则

- SKU 重复判断使用 `brand_id + type_series_id + color_name + color_hex + nominal_weight_g + filament_diameter_mm + tray_info_idx`；`sealed_quantity` 和 `note` 不参与判断。
- 创建、更新 SKU 或改绑类型/系列导致重复时返回 HTTP `409`，响应体包含 `duplicate_filament_sku` 和已有 SKU 摘要。
- 料卷状态保留历史，不通过“用尽”或“归档”物理删除；状态变更会写入 `FilamentSpoolEvent`。
- 当前库存重量只统计未开封库存、开封未用尽库存和 AMS 中料卷；`empty`、`archived` 不计入库存重量。
- AMS 自动识别会跳过换料/RFID 过渡帧，等材料、颜色、UID 等稳定后再绑定或创建料卷。
- 已用尽或已归档料卷的 `official_spool_uid` 再次出现时，不会静默复用，而是创建待确认冲突供前端处理。

## 数据库与迁移

当前项目使用本地 SQLite。`backend/src/filament_manager/db/session.py` 会在启动时执行轻量 schema 补齐，适合本地单机使用。涉及结构变更时，需要同时更新：

- SQLAlchemy 模型：`backend/src/filament_manager/db/models.py`
- API schema：`backend/src/filament_manager/schemas.py`
- schema 补齐逻辑：`backend/src/filament_manager/db/session.py`
- 对应 pytest：`test/`

## 注意事项

- 不要在代码、测试或文档中提交真实 access code。
- 本地数据库、运行时备份和虚拟环境不应进入版本控制。
- 与打印机交互的功能应优先保留只读或可回退行为，避免误操作设备。
- 实时画面接口只做本地转发，不应引入服务端持久化视频逻辑。
