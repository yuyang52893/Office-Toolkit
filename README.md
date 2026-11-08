# 轻办公工具箱

免登录的 Excel/CSV 拆分合并、二维码与 MAC 地址工具。

## 技术栈

- 前端：Next.js、React、TypeScript、Tailwind CSS
- 后端：FastAPI、Python 3.12、openpyxl、xlrd、qrcode、zxing-cpp
- 部署：Docker Compose + Nginx

## 本地开发

### 页面演示模式

```powershell
cd frontend
pnpm install
pnpm dev
```

默认使用纯前端模拟数据，打开 `http://localhost:3000` 即可评审页面和操作流程，无需启动后端。二维码会真实生成；Excel 处理和二维码解析使用模拟结果。

需要连接真实接口时，在 `frontend/.env.local` 设置：

```text
NEXT_PUBLIC_DEMO_MODE=false
```

### 完整前后端

```powershell
cd backend
uv sync --dev
uv run uvicorn app.main:app --reload
```

```powershell
cd frontend
pnpm install
pnpm dev
```

前端开发服务器会把 `/api` 代理到 `http://127.0.0.1:8000`。

## 验证

```powershell
cd backend
uv run ruff check .
uv run pytest
```

```powershell
cd frontend
pnpm lint
pnpm typecheck
pnpm build
pnpm exec playwright test
```

## Docker

```powershell
docker compose up --build
```

访问 `http://localhost:8080`。

详细产品规则与验收标准见 [docs/MVP_SPEC.md](docs/MVP_SPEC.md)。

