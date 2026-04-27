# FilamentManager Backend

第一阶段后端使用 FastAPI、SQLite 和 Bambu Lab 本地 MQTT。所有打印机连接信息都必须由用户在运行时通过 API 或 Gradio UI 显式填写。

启动开发服务：

```bash
uv run uvicorn filament_manager.main:app --reload
```

默认数据库路径为 `backend/filament_manager.db`，可通过环境变量 `FILAMENT_MANAGER_DATABASE_URL` 覆盖。
