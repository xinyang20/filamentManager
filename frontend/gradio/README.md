# FilamentManager Gradio UI

开发期 Gradio 前端通过 HTTP 调用 FastAPI 后端。

先启动后端：

```bash
cd backend
uv run uvicorn filament_manager.main:app --reload
```

再启动 Gradio：

```bash
cd backend
uv run python ../frontend/gradio/app.py
```

可通过 `FILAMENT_MANAGER_API_URL` 指定后端地址，默认使用 `http://127.0.0.1:8000/api`。

界面默认使用简体中文，页面顶部可切换为 English。

打印机配置页支持扫描当前局域网候选设备。扫描会检查 `8883/tcp` 和 `990/tcp` 特征端口，并读取 SSDP 基础信息；只有两个端口都开放且基础信息符合预期的设备才会展示。扫描不需要 access code，结果不会自动保存配置，仍需用户确认并填写 access code。
