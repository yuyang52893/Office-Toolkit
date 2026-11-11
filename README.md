# 轻办公工具箱

免登录的 Excel/CSV 拆分合并、二维码与 MAC 地址工具。

## 技术栈

- 前端：Next.js、React、TypeScript、Tailwind CSS
- 后端：FastAPI、Python 3.12、MySQL 8.4、SQLAlchemy、Alembic、openpyxl、xlrd、qrcode、zxing-cpp
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
uv run alembic upgrade head
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

### 三期账号与历史

首次启动容器前，根据 `.env.example` 创建 `.env` 并修改 MySQL 密码和 JWT 密钥：

```powershell
Copy-Item .env.example .env
docker compose up -d --build
```

创建首个管理员：

```powershell
docker compose exec backend python -m app.cli create-admin
```

注册、登录、找回密码、个人历史、账号管理和日志中心均继续使用现有页面；五个办公工具保持匿名可用。个人历史最多保存 10 个结果或 200MB，结果 30 分钟后失效，过期占位显示 3 小时。

### 日志

实时查看容器日志：

```powershell
docker compose logs -f backend
docker compose logs -f nginx
```

运行错误按日期写入持久化 JSON Lines 文件：

```powershell
docker compose exec backend sh -c "ls /data/logs/runtime-errors"
$day = Get-Date -Format yyyy-MM-dd
docker compose exec backend tail -f "/data/logs/runtime-errors/runtime-errors-$day.jsonl"
```

运行错误日志单日最大 5MB、保留 14 天、总量硬上限 64MB。普通 INFO 请求只进入 Docker 日志。管理员也可在 `/admin/logs` 查看和下载。

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

