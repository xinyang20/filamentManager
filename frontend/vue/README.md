# FilamentManager Vue Frontend

Vue3 release 前端，默认通过 Vite proxy 访问本地 FastAPI：

```bash
pnpm install
pnpm dev
```

默认后端地址为 `http://127.0.0.1:8000`。如需改 API 根地址：

```bash
VITE_FILAMENT_MANAGER_API_URL=http://127.0.0.1:8000/api pnpm dev
```
