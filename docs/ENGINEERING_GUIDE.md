# 轻办公工具箱：工程化指南

## 1. 技术栈

### 前端

- Next.js App Router
- React
- TypeScript
- Tailwind CSS
- Playwright

### 后端

- FastAPI
- Python 3.12
- Pydantic
- openpyxl、xlrd、Python csv
- qrcode、Pillow、zxing-cpp

### 工具与部署

- pnpm
- uv
- pytest、Ruff
- Docker Compose + Nginx

一期不引入 pandas、MySQL、Redis 或任务队列。只有对应阶段出现明确需求时再增加，避免个人项目技术面过宽。

## 2. 仓库结构

- `frontend/`：Next.js 页面、交互组件、演示数据和端到端测试。
- `backend/`：FastAPI 路由、业务服务、临时文件仓储和接口测试。
- `docs/`：产品设计与工程化文档。

前端页面入口位于 `frontend/app`，API 请求集中在 `frontend/lib/api.ts`。演示数据实现位于 `frontend/lib/demo-api.ts`，不能散落到组件内部。

## 3. 后端分层

请求按以下方向流动：

```text
Router -> Schema -> Service -> Repository -> File System
                      |
                    Common
```

- Router：接收参数、调用服务、封装响应，不写业务规则。
- Schema：Pydantic 参数和响应模型。
- Service：Excel/CSV 处理、二维码和 MAC 业务逻辑。
- Repository：临时文件创建、读取、下载和清理，不承载业务判断。
- Common：统一响应、异常、配置、日志和通用工具。

未来接入数据库后，数据库 CRUD 放入独立的 DAO/Repository，Service 不直接写 SQL。

## 4. 前端分层

- `app/`：路由、页面元数据和页面级布局。
- `features/` 或页面专属组件：单一工具的业务交互。
- `components/`：可复用按钮、状态提示、返回入口等。
- `lib/`：API、类型、格式化、演示数据和通用客户端工具。

当页面文件持续增大时，应按“上传、工作表选择、处理规则、结果展示”等职责拆分，避免单个组件同时管理所有业务。

## 5. 演示模式与真实模式

前端通过 `NEXT_PUBLIC_DEMO_MODE` 控制数据来源：

- 默认 `true`：不依赖后端，Excel 处理和二维码解析使用模拟数据。
- 设置为 `false`：请求现有 FastAPI 接口。

模拟层与真实 API 必须保持相同的 TypeScript 类型和调用入口。组件不能判断“是否演示”后直接编造业务数据，所有模拟逻辑集中在 `frontend/lib/demo-api.ts`。

## 6. API 约定

JSON 响应统一为：

```json
{
  "success": true,
  "data": {},
  "error": null,
  "request_id": "request-id"
}
```

当前接口：

- `POST /api/v1/excel/inspect`
- `POST /api/v1/excel/split`
- `POST /api/v1/excel/merge`
- `GET /api/v1/results/{result_id}`
- `POST /api/v1/qrcode/generate`
- `POST /api/v1/qrcode/decode`
- `POST /api/v1/qrcode/mac/parse`
- `GET /api/v1/health`

约定：

- 时间使用 ISO 8601 UTC。
- 临时资源使用服务端 UUID 或不可猜测 ID。
- 文件下载成功时直接返回二进制。
- 文件路径永不直接使用用户提供的名称。

## 7. 文件与安全

- 上传时流式写入磁盘并实时计算大小。
- 同时检查扩展名、MIME、文件特征和实际解析结果。
- CSV 的 MIME 不可靠，必须尝试识别编码和分隔符。
- 限制单文件、单任务、解压体积、压缩条目、行数和列数。
- 默认额外限制单任务解压后总量 500MB、选中工作表总量 200 万单元格。
- 输出文件名和 ZIP 条目名称需要清理非法字符。
- 上传文件、结果和中间文件必须具有明确生命周期。
- 日志不得记录文件正文或敏感内容。

## 8. 测试与质量门槛

### 后端

```powershell
cd backend
uv run ruff check .
uv run pytest
```

测试覆盖正常流程、参数错误、损坏文件、超限、空行、重复行、表头策略、CSV 编码和过期清理。

### 前端

```powershell
cd frontend
pnpm lint
pnpm typecheck
pnpm build
pnpm exec playwright test
pnpm test:e2e:real
```

Playwright 至少覆盖：

- 首页功能入口与模式预选。
- Excel/CSV 拆分并下载结果。
- 二维码生成。
- 二维码图片解析。
- MAC 地址规范化与二维码生成。

## 9. 开发与提交规范

- 修改前先确认需求和验收标准。
- 新功能或缺陷修复先添加会失败的测试，再实现。
- 每次可回滚的改动完成后执行相关验证并创建 Git commit。
- 提交信息使用 `feat:`、`fix:`、`docs:`、`test:` 或 `chore:` 前缀。
- 不提交 `.env.local`、虚拟环境、构建产物和临时文件。
- 不在一个提交中混入无关重构。

## 10. 部署原则

- 单机部署使用 Docker Compose。
- Nginx 统一代理前端与 `/api`，避免不必要的跨域。
- 限制请求体大小、代理超时和后端处理并发。
- 前后端同源时无需开放通配 CORS。
- 公网环境启用 HTTPS，并将上传目录挂载到受控临时卷。

## 11. 当前状态与后续优先事项

当前已完成：

- 纯前端可交互演示。
- 首页功能选择与详情页模式预选。
- 真实模式页面标识、结果下载与服务端错误处理。
- 后端分层、主要接口、上传类型校验、任务资源预算和临时文件清理。
- 真实前后端桌面端全链路测试与演示模式移动端测试。
- Docker Compose、前后端镜像和 Nginx 同源代理配置。

正式验收前应优先：

1. 在安装 Docker 的环境中实际构建并启动 Compose。
2. 按二期路线评估日志、限流、请求追踪和错误告警。
3. 只有出现明确任务耗时或排队瓶颈后，再进入异步任务阶段。

