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

`pnpm exec playwright test` 会在演示模式下运行桌面端和移动端测试。真实前后端链路测试会自动启动 FastAPI 和设置为 `NEXT_PUBLIC_DEMO_MODE=false` 的前端：

```powershell
cd frontend
pnpm test:e2e:real
```

## Docker

需要 Docker Desktop 或 Docker Engine，并启用 Docker Compose v2。

```powershell
docker compose up --build
```

访问 `http://localhost:8080`。容器构建固定使用真实模式，Nginx 统一代理页面和 `/api`，上传结果存放在 `office-temp` 临时卷中。

### 日志

实时查看容器日志：

```powershell
docker compose logs -f backend
docker compose logs -f nginx
```

后端同时写入可轮转的 JSON Lines 文件：

```powershell
Get-Content -Wait .\logs\backend\app.jsonl
Select-String .\logs\backend\app.jsonl -Pattern '"level":"ERROR"'
```

单份日志达到 10MB 后轮转，保留 7 份。Docker 容器日志使用相同的大小和保留策略。

### 二期运维配置

复制根目录的 `.env.example` 为 `.env` 后可调整：

- `RATE_LIMIT_PER_MINUTE`：普通 API 每 IP 每分钟请求上限，默认 60。
- `EXCEL_RATE_LIMIT_PER_MINUTE`：Excel 检查、拆分和合并每 IP 每分钟上限，默认 10。
- `CORS_ORIGINS`：逗号分隔的独立前端域名；同源部署留空。
- `ALERT_WEBHOOK_URL`：可选错误告警地址，默认留空即关闭。
- `ALERT_COOLDOWN_SECONDS`：相同接口告警冷却时间，默认 60 秒。

Webhook 仅在发生未处理的 HTTP 500 错误时由后台发送，不包含上传文件内容或原始异常详情。日志网页查询属于三期管理员功能。

## 项目文档

- [产品设计文档](docs/PRODUCT_DESIGN.md)：产品定位、功能规则、路线图和验收标准。
- [工程化指南](docs/ENGINEERING_GUIDE.md)：技术栈、目录分层、API、测试和开发规范。

