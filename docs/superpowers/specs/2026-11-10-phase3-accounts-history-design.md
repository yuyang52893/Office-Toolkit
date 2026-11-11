# 三期账号与个人历史设计

## 1. 目标

在保留全部办公工具匿名可用的前提下，增加账号、个人处理历史、管理员账号管理和管理员日志中心。

三期不引入常用配置、邮件服务、手机号、对象存储、Redis、团队空间、账号配额套餐或永久文件存储。

## 2. 核心规则

### 2.1 匿名与登录

- 首页、Excel/CSV 工作台、二维码和 MAC 工具继续允许匿名使用。
- 匿名用户不创建个人历史。
- 登录用户处理成功后自动尝试保存结果文件。
- 缺少、过期或失效 Token 时，登录专属接口返回 HTTP 401。
- 普通用户访问管理员接口时返回 HTTP 403。

### 2.2 用户名

- 仅允许 `0-9` 数字。
- 长度 8-18 位。
- 允许首位为 `0`。
- 全局唯一。
- 不允许负号、小数点、字母、空格或其他字符。
- Pydantic 校验与数据库唯一约束必须同时存在。

### 2.3 密码与找回

- 密码长度为 8-18 个字符，按用户输入保存哈希，不保存明文。
- 注册时必须填写自定义找回问题和找回答案。
- 找回问题和答案不得在管理员页面显示。
- 密码和找回答案使用 Argon2 安全哈希。
- 找回答案校验前执行去首尾空白、Unicode NFKC 规范化和英文大小写折叠。
- 找回密码时先验证用户名和答案，再设置新密码。
- 找回密码成功后提升会话版本，旧 Token 立即失效，用户重新登录。
- 登录、找回密码和密码修改受独立限流；响应不得通过错误文案泄露账号是否存在。

### 2.4 JWT Bearer 会话

- 登录成功后返回 JWT，前端使用 `Authorization: Bearer <token>`。
- Token 由前端保存到 `sessionStorage`，刷新页面保留，关闭标签页后清除。
- Token 有效期 12 小时，不提供刷新 Token。
- JWT 至少包含 `sub`、`role`、`sv`、`iat`、`exp` 和 `jti`。
- 每次登录专属请求校验签名、过期时间、用户状态和会话版本。
- 禁用账号、修改密码、找回密码、角色变更或管理员强制退出时递增会话版本。
- Token 不写入 URL、Cookie、应用日志、审计日志或错误告警。
- 前端必须启用严格 CSP，并使用 React 默认转义；不得使用 `dangerouslySetInnerHTML` 渲染用户内容。

### 2.5 角色与管理员

- 角色为 `user` 或 `admin`。
- 公开注册只能创建 `user`。
- 首个管理员通过服务器命令创建，不允许公开注册管理员。
- 管理员可查询用户、启用/禁用账号、修改角色、强制退出和重置密码。
- 管理员不能查看密码、密码哈希、找回答案或用户文件内容。
- 管理员重置密码时，系统生成一次性临时密码，仅在响应中显示一次。
- 临时密码仍只以哈希保存，用户登录后必须立即修改密码。
- 系统必须至少保留一个启用状态的管理员。
- 不能禁用、降级或删除最后一个启用的管理员。
- 用户不支持彻底删除，只支持禁用。

## 3. 个人历史与文件生命周期

### 3.1 保存范围

进入个人历史的结果包括：

- Excel/CSV 按工作表拆分结果 ZIP。
- Excel/CSV 按行数拆分结果 ZIP。
- Excel/CSV 按列值拆分结果 ZIP。
- Excel/CSV 合并结果 XLSX。
- 普通二维码生成 PNG。
- MAC 地址二维码 PNG。

不保存：

- 二维码图片解析出的文本。
- Excel/CSV 文件正文。
- 二维码解析上传的原始图片。
- 失败或未完成任务的临时文件。

二维码解析仅在管理员审计日志中记录成功/失败、识别数量和操作时间。

### 3.2 配额

- 每用户最多 10 个仍可下载的活跃结果。
- 每用户活跃结果总大小最多 200MB。
- 数量或容量以结果条目为单位计算，不按 ZIP 内部文件数量计算。
- 过期占位记录不占用数量或容量。
- 新增结果超限时，按完成时间从早到晚清理活跃记录，直到新结果能够保存。
- 若单个结果本身超过 200MB，则允许当前下载，但不写入个人历史；界面显示“结果过大，未保存到历史”。
- 文件保存失败不得使已成功完成的业务处理失败；当前临时结果仍允许下载，并显示历史保存失败提示。

### 3.3 到期与占位

- 文件从处理完成时间起 30 分钟有效。
- 到期或因数量/容量清理后，立即删除物理文件。
- 记录保留为不可下载的“已过期/已清理”占位，并在过期原因中区分：
  - 30 分钟自然到期。
  - 超过数量上限。
  - 超过容量上限。
- 占位记录在文件失效 3 小时后删除。
- 前端历史页面展示过期原因、失效时间和占位最终清除时间。

### 3.4 存储与一致性

- MySQL 保存结果元数据和文件所有权。
- 文件保存在只允许后端访问的个人历史卷。
- 数据库不保存 ZIP、XLSX 或 PNG 二进制。
- 文件目录使用服务端生成的用户 ID、历史 ID 和存储键，不直接使用用户名或用户文件名。
- 保存新历史时使用用户级并发锁和数据库事务，防止并发请求突破配额。
- 数据库记录创建失败时删除刚写入的文件。
- 物理文件删除失败时记录 ERROR 日志，并在下一轮清理中重试。
- 当前临时目录清理任务与个人历史清理任务必须分开。

## 4. 数据库设计

数据库使用 MySQL 8.4、SQLAlchemy 2.0、PyMySQL 和 Alembic。

### 4.1 `users`

| 字段 | 说明 |
| --- | --- |
| `id` | BIGINT 主键 |
| `username` | VARCHAR(18)，唯一，仅数字 |
| `password_hash` | VARCHAR(255) |
| `recovery_question` | VARCHAR(200) |
| `recovery_answer_hash` | VARCHAR(255) |
| `role` | VARCHAR(16)，`user` 或 `admin` |
| `is_active` | BOOLEAN，默认启用 |
| `session_version` | INTEGER，默认 0 |
| `must_change_password` | BOOLEAN，默认关闭 |
| `created_at` | UTC DATETIME |
| `updated_at` | UTC DATETIME |
| `last_login_at` | UTC DATETIME，可为空 |

### 4.2 `user_history`

| 字段 | 说明 |
| --- | --- |
| `id` | CHAR(32) 服务端生成 ID |
| `user_id` | 用户外键 |
| `tool` | 工具类型 |
| `operation` | 具体操作 |
| `result_filename` | 结果文件名 |
| `storage_key` | 服务端存储键 |
| `size_bytes` | 结果大小 |
| `summary` | 清洗后的处理摘要 JSON |
| `status` | `active` 或 `expired` |
| `completed_at` | 完成时间 |
| `expires_at` | 完成时间加 30 分钟 |
| `expired_at` | 实际失效时间 |
| `expire_reason` | `timeout`、`quota_count`、`quota_size` |
| `purge_after` | 占位记录删除时间 |

索引至少包括 `user_id/status/expires_at` 和 `purge_after`。

### 4.3 `audit_logs`

| 字段 | 说明 |
| --- | --- |
| `id` | BIGINT 主键 |
| `request_id` | 请求追踪 ID |
| `actor_user_id` | 操作人，可为空 |
| `target_user_id` | 目标用户，可为空 |
| `event` | 结构化事件名 |
| `outcome` | `success` 或 `failure` |
| `ip` | 客户端 IP |
| `details` | 清洗后的非敏感 JSON |
| `created_at` | UTC DATETIME |

审计日志保留 30 天，每日清理。日志中不得出现密码、找回答案、临时密码、JWT、二维码文本或文件正文。

## 5. API 设计

所有 JSON 接口继续使用统一响应结构。

### 5.1 认证

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/logout`
- `GET /api/v1/auth/me`
- `POST /api/v1/auth/recovery-question`
- `POST /api/v1/auth/reset-password`
- `POST /api/v1/auth/change-password`

### 5.2 个人历史

- `GET /api/v1/history`
- `GET /api/v1/history/{history_id}/download`

历史下载必须验证 Token、记录所有者和 `status=active`。

### 5.3 管理员账号

- `GET /api/v1/admin/users`
- `PATCH /api/v1/admin/users/{user_id}/status`
- `PATCH /api/v1/admin/users/{user_id}/role`
- `POST /api/v1/admin/users/{user_id}/logout`
- `POST /api/v1/admin/users/{user_id}/reset-password`

### 5.4 管理员日志

- `GET /api/v1/admin/audit-logs`
- `GET /api/v1/admin/audit-logs/download?date=YYYY-MM-DD&format=json|csv`
- `GET /api/v1/admin/runtime-errors?date=YYYY-MM-DD`
- `GET /api/v1/admin/runtime-errors/download?date=YYYY-MM-DD`

管理员每次查看或下载日志都必须生成审计事件。

### 5.5 错误约定

- 无 Token：401 `AUTH_REQUIRED`。
- Token 无效或过期：401 `AUTH_INVALID`。
- 非管理员：403 `FORBIDDEN`。
- 历史文件已过期：410 `HISTORY_EXPIRED`。
- 历史文件不属于当前用户：404 `HISTORY_NOT_FOUND`，不暴露记录是否存在。
- 最后一个管理员保护：409 `LAST_ADMIN_REQUIRED`。

## 6. 页面与交互

### 6.1 新增页面

- `/register`：账号注册。
- `/login`：登录。
- `/recover`：找回密码。
- `/history`：个人处理历史。
- `/admin/users`：管理员用户管理。
- `/admin/logs`：管理员日志中心。

### 6.2 公共页面

- 顶部导航增加登录入口和已登录账号菜单。
- 登录后显示“个人历史”和“退出登录”。
- 管理员额外显示“账号管理”和“日志中心”。
- 匿名用户不显示个人历史入口，也无权访问对应接口。

### 6.3 历史页面

- 有效文件显示文件名、工具、大小、完成时间、剩余有效期和下载按钮。
- 过期占位显示不可下载状态、清理原因和最终移除时间。
- 文件保存成功或清理旧文件时，工作台通过状态横幅提示。

### 6.4 管理员日志页面

- “操作审计”和“运行错误”两个页签。
- 操作审计支持日期、用户名、事件类型、结果和 `request_id` 筛选。
- 运行错误支持按日期查看和下载原始 JSON Lines 错误文件。
- 操作审计支持按日期下载 CSV 或 JSON。
- 所有列表分页，禁止一次读取整月日志。

## 7. 运行日志调整

- 普通 INFO 访问日志只进入 Docker 日志，不重复写入持久化文件。
- 持久化运行文件只保存 WARNING 和 ERROR。
- 运行错误文件按自然日命名，单日最大 5MB。
- 运行错误文件保留 14 天，总容量硬上限 64MB。
- 超过总容量时删除最旧日期文件。
- Docker 日志调整为每个服务 5MB × 3 份，最大约 15MB/服务。
- 日志达到单日上限后停止继续写入文件，并在 Docker/stdout 中输出一条限流提示。

## 8. 部署

- Docker Compose 新增 MySQL 8.4 服务，不向宿主机公开数据库端口。
- MySQL 数据、个人历史文件和日志分别使用命名卷或受控目录。
- 后端启动前执行 `alembic upgrade head`。
- 数据库连接、JWT 密钥和初始管理员配置只通过环境变量或服务器命令提供。
- `.env` 不提交；`.env.example` 只包含安全占位值。
- 后端仍以非 root 用户运行。

## 9. 测试与验收

### 后端

- 注册、登录、登出、Token 过期、签名错误、会话版本失效。
- 用户名长度、数字限制、允许前导零和唯一性。
- 密码 8-18 位、Argon2 哈希和找回答案验证。
- SQL 注入字符串被参数化查询安全处理。
- 普通用户不能访问管理员接口或他人的历史文件。
- 管理员不能查看密码和找回答案。
- 管理员重置临时密码并强制修改。
- 最后一个管理员不能禁用或降级。
- 历史 10 个/200MB 配额和并发保存。
- 30 分钟过期、3 小时占位、自然到期和配额清理原因。
- 单个结果超过 200MB 时不保存但当前下载可用。
- 审计日志 30 天清理和运行错误日志 14 天/64MB 清理。
- CSV/JSON 审计下载和按日期运行错误文件下载。

### 前端

- 注册、登录、找回密码和退出。
- 无 Token 时登录专属页面提示并跳转。
- 匿名工具流程不受影响。
- 登录用户处理成功后可查看和下载历史。
- 过期占位和配额清理提示。
- 普通用户看不到管理员入口。
- 管理员用户管理、日志筛选和日志下载。

### 全量回归

- Ruff、pytest、ESLint、TypeScript、Next.js 构建。
- Demo 桌面端和移动端 Playwright。
- 真实前后端 Playwright。
- Docker Compose 实际构建、迁移和启动。
- 数据库迁移可在空库执行，并可从上一版结构升级。

## 10. 非目标

- 邮箱、手机号和邮件验证。
- 忘记用户名。
- 第三方登录。
- 刷新 Token。
- 永久保存文件。
- 文件分享链接。
- 管理员查看用户文件。
- 常用配置。
- 团队、组织、付费或复杂角色系统。
