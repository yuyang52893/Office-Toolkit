# 三期账号与个人历史 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在保持所有办公工具匿名可用的前提下，增加 JWT Bearer 账号、个人历史文件、管理员账号管理和可下载的管理员日志中心。

**Architecture:** FastAPI 使用同步 SQLAlchemy 2.0 + PyMySQL 访问 MySQL；账号、历史元数据和审计事件存数据库，结果文件存独立历史卷。JWT 使用 Bearer Token，前端存 `sessionStorage`；所有登录专属能力由后端统一鉴权，前端守卫只负责体验。运行错误日志按日分文件并设置严格磁盘上限。

**Tech Stack:** Next.js 16、React 19、TypeScript、FastAPI、Python 3.12、SQLAlchemy 2.0、PyMySQL、Alembic、MySQL 8.4、PyJWT、Argon2、pytest、Playwright、Docker Compose。

**Spec:** `docs/superpowers/specs/2026-11-10-phase3-accounts-history-design.md`

## Global Constraints

- 现有五个工具始终允许匿名使用。
- 用户名仅允许 `0-9`，长度 8-18，允许首位为 `0`，全局唯一。
- 密码长度 8-18，密码和找回答案只保存 Argon2 哈希。
- JWT 有效期 12 小时，不提供刷新 Token，Bearer Token 存 `sessionStorage`。
- 密码、找回答案、临时密码和 JWT 不得写入日志或审计详情。
- 普通注册只能创建 `user`；首个 `admin` 只能通过服务器命令创建。
- 至少保留一个启用状态的管理员。
- 每用户最多 10 个活跃历史结果，总大小最多 200MB。
- 历史文件完成后 30 分钟失效；过期占位保留 3 小时。
- 管理员审计日志保留 30 天。
- 运行错误日志保留 14 天，单日 5MB，总上限 64MB。
- Docker 日志每服务 5MB × 3 份。
- 数据迁移必须使用 Alembic，不调用生产环境 `create_all()`。
- 每个任务先写失败测试，再实现，测试通过后单独提交。

---

## File Structure

### Backend

- `backend/app/db/base.py`：SQLAlchemy 声明基类。
- `backend/app/db/models.py`：用户、历史、审计日志模型。
- `backend/app/db/session.py`：数据库 Engine 和 Session 工厂。
- `backend/app/security/passwords.py`：Argon2 密码和找回答案。
- `backend/app/security/tokens.py`：JWT 创建、解析和 claims。
- `backend/app/repositories/users.py`：用户查询与持久化。
- `backend/app/repositories/history.py`：历史记录与配额查询。
- `backend/app/repositories/audit.py`：审计事件与清理。
- `backend/app/repositories/history_storage.py`：历史文件写入、读取和删除。
- `backend/app/repositories/runtime_logs.py`：按日期读取和下载错误文件。
- `backend/app/services/auth.py`：注册、登录、找回、改密。
- `backend/app/services/admin.py`：用户管理和管理员保护。
- `backend/app/services/history.py`：保存、配额、过期和占位生命周期。
- `backend/app/services/audit.py`：审计事件写入。
- `backend/app/services/runtime_logs.py`：错误日志查询。
- `backend/app/dependencies/auth.py`：可选用户、必须登录、管理员依赖。
- `backend/app/schemas/auth.py`、`admin.py`、`history.py`、`logs.py`：接口模型。
- `backend/app/routers/auth.py`、`history.py`、`admin.py`：三期路由。
- `backend/app/cli.py`：初始化管理员命令。
- `backend/alembic.ini`、`backend/migrations/`：数据库迁移。

### Frontend

- `frontend/lib/auth-storage.ts`：`sessionStorage` Token 读写。
- `frontend/lib/auth-api.ts`：认证和管理员 API。
- `frontend/components/auth-provider.tsx`：登录态上下文。
- `frontend/components/account-nav.tsx`：账号菜单。
- `frontend/components/auth-guard.tsx`：登录专属页面体验守卫。
- `frontend/app/login/page.tsx`、`register/page.tsx`、`recover/page.tsx`、`change-password/page.tsx`。
- `frontend/app/history/page.tsx`：个人历史。
- `frontend/app/admin/users/page.tsx`、`app/admin/logs/page.tsx`：管理员页面。
- `frontend/proxy.ts`：nonce CSP。

### Tests

- `backend/tests/test_database.py`
- `backend/tests/test_security.py`
- `backend/tests/test_auth_api.py`
- `backend/tests/test_admin_api.py`
- `backend/tests/test_history.py`
- `backend/tests/test_runtime_logs.py`
- `frontend/tests/e2e/accounts.spec.ts`
- `frontend/tests/e2e-real/accounts-history.spec.ts`

---

### Task 0: 数据库基础、模型与 MySQL 部署

**Files:**
- Modify: `backend/pyproject.toml`
- Modify: `backend/app/config.py`
- Modify: `backend/app/main.py`
- Create: `backend/app/db/__init__.py`
- Create: `backend/app/db/base.py`
- Create: `backend/app/db/models.py`
- Create: `backend/app/db/session.py`
- Create: `backend/alembic.ini`
- Create: `backend/migrations/env.py`
- Create: `backend/migrations/script.py.mako`
- Create: `backend/migrations/versions/20261110_0001_phase3_accounts.py`
- Create: `backend/tests/test_database.py`
- Modify: `backend/tests/conftest.py`
- Modify: `compose.yaml`
- Modify: `.env.example`
- Modify: `backend/.env.example`

**Interfaces:**
- Produces: `Base`, `User`, `UserHistory`, `AuditLog`
- Produces: `build_engine(database_url)`, `build_session_factory(engine)`
- Produces: settings `database_url: str`, `jwt_secret: str`, `jwt_expire_minutes: int`

- [ ] **Step 1: 写数据库模型失败测试**

```python
def test_username_is_unique(db_session):
    db_session.add(make_user(username="00123456"))
    db_session.commit()
    db_session.add(make_user(username="00123456"))
    with pytest.raises(IntegrityError):
        db_session.commit()
```

同时断言三张表存在，`user_history` 有 `user_id/status/expires_at` 索引，`audit_logs.created_at` 有索引。

- [ ] **Step 2: 运行失败测试**

Run: `uv run pytest tests/test_database.py -q`

Expected: FAIL，`app.db.models` 不存在。

- [ ] **Step 3: 添加依赖、配置和模型**

依赖添加：

```toml
"alembic>=1.16,<2",
"argon2-cffi>=25,<26",
"PyJWT>=2.10,<3",
"PyMySQL>=1.1,<2",
"SQLAlchemy>=2.0,<2.1",
```

模型必须使用：

```python
username: Mapped[str] = mapped_column(String(18), unique=True, nullable=False)
password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
recovery_answer_hash: Mapped[str] = mapped_column(String(255), nullable=False)
role: Mapped[str] = mapped_column(String(16), nullable=False, default="user")
session_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
```

历史时间字段：

```python
completed_at: Mapped[datetime]
expires_at: Mapped[datetime]
expired_at: Mapped[datetime | None]
purge_after: Mapped[datetime | None]
```

- [ ] **Step 4: 配置 Session 与测试数据库**

测试 fixture 使用 SQLite `StaticPool`，生产 URL 默认 MySQL：

```python
settings = test_settings.model_copy(
    update={"database_url": "sqlite+pysqlite:///:memory:"}
)
engine = build_engine(settings.database_url)
Base.metadata.create_all(engine)
```

应用启动时创建 Engine 和 Session 工厂，退出时 `engine.dispose()`。

- [ ] **Step 5: 创建 Alembic 初始迁移和 MySQL Compose**

Compose 新增 MySQL 8.4、健康检查、`mysql-data` 卷、后端 `DATABASE_URL` 和不公开数据库端口。后端启动命令改为：

```yaml
command: ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
```

- [ ] **Step 6: 验证**

Run:

```powershell
cd backend
uv run ruff check .
uv run pytest tests/test_database.py -q
docker compose config --quiet
```

Expected: 全部通过。

- [ ] **Step 7: 提交**

```powershell
git add backend/pyproject.toml backend/uv.lock backend/app/config.py backend/app/main.py backend/app/db backend/alembic.ini backend/migrations backend/tests/test_database.py backend/tests/conftest.py compose.yaml .env.example backend/.env.example
git commit -m "feat: 增加三期数据库基础与迁移"
```

---

### Task 1: 密码、找回答案与 JWT 安全基础

**Files:**
- Create: `backend/app/security/__init__.py`
- Create: `backend/app/security/passwords.py`
- Create: `backend/app/security/tokens.py`
- Create: `backend/tests/test_security.py`

**Interfaces:**
- Produces: `hash_password(value: str) -> str`
- Produces: `verify_password(value: str, password_hash: str) -> bool`
- Produces: `normalize_recovery_answer(value: str) -> str`
- Produces: `create_access_token(user_id: int, role: str, session_version: int, settings: Settings) -> str`
- Produces: `decode_access_token(token: str, settings: Settings) -> TokenClaims`

- [ ] **Step 1: 写安全失败测试**

```python
def test_password_hash_is_irreversible_and_verifiable():
    value = "Strong-Pass-1"
    hashed = hash_password(value)
    assert value not in hashed
    assert verify_password(value, hashed) is True
    assert verify_password("wrong-pass", hashed) is False


def test_jwt_rejects_tampered_token(settings):
    token = create_access_token(1, "user", 3, settings)
    with pytest.raises(InvalidTokenError):
        decode_access_token(token[:-1] + "x", settings)
```

再验证 claims 包含 `sub`、`role`、`sv`、`iat`、`exp`、`jti`，并验证找回答案的 NFKC、空白和大小写归一化。

- [ ] **Step 2: 运行失败测试**

Run: `uv run pytest tests/test_security.py -q`

Expected: FAIL，安全模块不存在。

- [ ] **Step 3: 实现 Argon2 与 JWT**

使用 `argon2.PasswordHasher()`；JWT 使用 PyJWT `HS256`，密钥不足 32 字符时启动失败。解析异常统一转换为应用 `InvalidTokenError`，不向接口泄露 PyJWT 内部错误。

- [ ] **Step 4: 验证**

Run:

```powershell
uv run ruff check app/security tests/test_security.py
uv run pytest tests/test_security.py -q
```

Expected: 全部通过。

- [ ] **Step 5: 提交**

```powershell
git add backend/app/security backend/tests/test_security.py backend/uv.lock backend/pyproject.toml
git commit -m "feat: 增加密码与 JWT 安全基础"
```

---

### Task 2: 注册、登录、找回与改密

**Files:**
- Create: `backend/app/schemas/auth.py`
- Create: `backend/app/repositories/users.py`
- Create: `backend/app/services/auth.py`
- Create: `backend/app/dependencies/auth.py`
- Create: `backend/app/routers/auth.py`
- Create: `backend/tests/test_auth_api.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/config.py`
- Modify: `backend/tests/conftest.py`

**Interfaces:**
- Produces API endpoints in spec section 5.1.
- Produces: `get_optional_user`, `get_current_user`, `require_admin`
- Produces: `AuthService.register`, `login`, `get_recovery_question`, `reset_password`, `change_password`

- [ ] **Step 1: 写认证接口失败测试**

```python
def test_register_login_and_me(client):
    registered = client.post("/api/v1/auth/register", json={
        "username": "00123456",
        "password": "Password1",
        "recovery_question": "我的验证问题",
        "recovery_answer": "答案",
    })
    assert registered.status_code == 201

    logged_in = client.post("/api/v1/auth/login", json={
        "username": "00123456",
        "password": "Password1",
    })
    token = logged_in.json()["data"]["access_token"]
    me = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me.json()["data"]["username"] == "00123456"
```

另测：

- 用户名 `1234567`、`1234567890123456789`、`12a45678`、`-12345678` 均 422。
- 用户名 `01234567` 成功。
- 重复用户名 409。
- 密码 7 位和 19 位均 422。
- 无 Token 请求 `/auth/me` 返回 401 `AUTH_REQUIRED`。
- 令牌被篡改返回 401 `AUTH_INVALID`。
- 禁用账号无法登录。
- 找回答案错误返回统一失败文案。
- 找回成功提升 `session_version`，旧 Token 失效。
- 改密成功返回新 Token，旧 Token 失效。

- [ ] **Step 2: 运行失败测试**

Run: `uv run pytest tests/test_auth_api.py -q`

Expected: FAIL，认证接口不存在。

- [ ] **Step 3: 实现 schemas、repository 和 service**

用户名 schema 使用：

```python
username: str = Field(pattern=r"^[0-9]{8,18}$")
password: str = Field(min_length=8, max_length=18)
recovery_question: str = Field(min_length=2, max_length=200)
recovery_answer: str = Field(min_length=1, max_length=200)
```

所有 SQL 通过 SQLAlchemy 条件表达式和参数绑定完成。认证失败不区分用户名不存在、密码错误和账号禁用。

- [ ] **Step 4: 实现 JWT 依赖与认证路由**

Bearer 解析严格匹配：

```python
scheme, _, token = authorization.partition(" ")
if scheme.lower() != "bearer" or not token:
    raise AppError("AUTH_REQUIRED", "此功能仅登录用户可用", status_code=401)
```

`get_current_user` 校验 `is_active`、数据库 `session_version` 与 Token `sv`。

- [ ] **Step 5: 增加认证专用限流**

登录、找回问题、找回密码分别使用独立限流键，默认：

- 登录：每 IP 每分钟 10 次。
- 找回问题：每 IP 每分钟 5 次。
- 找回密码：每 IP 每 15 分钟 5 次。

- [ ] **Step 6: 验证**

Run:

```powershell
uv run ruff check .
uv run pytest tests/test_security.py tests/test_auth_api.py -q
uv run pytest
```

Expected: 全部通过。

- [ ] **Step 7: 提交**

```powershell
git add backend/app/schemas/auth.py backend/app/repositories/users.py backend/app/services/auth.py backend/app/dependencies/auth.py backend/app/routers/auth.py backend/app/main.py backend/app/config.py backend/tests/test_auth_api.py backend/tests/conftest.py
git commit -m "feat: 实现账号注册登录与找回密码"
```

---

### Task 3: 管理员账号管理与初始化命令

**Files:**
- Create: `backend/app/schemas/admin.py`
- Create: `backend/app/services/admin.py`
- Create: `backend/app/routers/admin.py`
- Create: `backend/app/cli.py`
- Create: `backend/tests/test_admin_api.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/dependencies/auth.py`
- Modify: `backend/app/repositories/users.py`

**Interfaces:**
- Produces spec section 5.3.
- Produces: `AdminService.set_status`, `set_role`, `force_logout`, `reset_password`
- Produces CLI: `python -m app.cli create-admin`

- [ ] **Step 1: 写管理员失败测试**

```python
def test_last_admin_cannot_be_disabled(admin_client, admin_user):
    response = admin_client.patch(
        f"/api/v1/admin/users/{admin_user.id}/status",
        json={"is_active": False},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "LAST_ADMIN_REQUIRED"
```

另测：

- 普通用户访问管理员接口返回 403。
- 无 Token 返回 401。
- 禁用普通用户立即使其 Token 失效。
- 角色变更提升会话版本。
- 强制退出提升会话版本。
- 重置密码返回仅一次可见的 8-18 位临时密码。
- 临时密码登录后 `must_change_password=True`，只能访问 me/change-password/logout。
- 创建第二个管理员后可以禁用第一个。
- 管理员不能查看密码哈希和找回答案。

- [ ] **Step 2: 运行失败测试**

Run: `uv run pytest tests/test_admin_api.py -q`

Expected: FAIL，管理员服务不存在。

- [ ] **Step 3: 实现管理员服务和路由**

所有管理员操作在一个事务内锁定目标用户，并在状态/角色变更前统计启用管理员数量。最后一个管理员保护返回 409。

- [ ] **Step 4: 实现交互式初始化管理员 CLI**

命令交互读取用户名、密码、找回问题和答案，使用 `getpass` 隐藏密码输入。禁止通过命令行参数传密码。

- [ ] **Step 5: 验证**

Run:

```powershell
uv run ruff check .
uv run pytest tests/test_admin_api.py -q
uv run pytest
```

Expected: 全部通过。

- [ ] **Step 6: 提交**

```powershell
git add backend/app/schemas/admin.py backend/app/services/admin.py backend/app/routers/admin.py backend/app/cli.py backend/tests/test_admin_api.py backend/app/main.py backend/app/dependencies/auth.py backend/app/repositories/users.py
git commit -m "feat: 增加管理员账号管理"
```

---

### Task 4: 审计日志

**Files:**
- Create: `backend/app/repositories/audit.py`
- Create: `backend/app/services/audit.py`
- Create: `backend/app/schemas/logs.py`
- Create: `backend/app/routers/audit_logs.py`
- Create: `backend/tests/test_audit_logs.py`
- Modify: `backend/app/services/auth.py`
- Modify: `backend/app/services/admin.py`
- Modify: `backend/app/main.py`

**Interfaces:**
- Produces: `AuditService.record(event, outcome, request_id, actor_user_id, target_user_id, ip, details)`
- Produces: `AuditService.list_logs(date, filters, page, page_size)`
- Produces: `AuditService.purge_expired(now)`

- [ ] **Step 1: 写审计失败测试**

```python
def test_password_is_never_stored_in_audit_details(admin_client):
    admin_client.post("/api/v1/auth/login", json={
        "username": "00123456",
        "password": "Secret-Pass-1",
    })
    rows = admin_client.get("/api/v1/admin/audit-logs").json()["data"]["items"]
    serialized = json.dumps(rows, ensure_ascii=False)
    assert "Secret-Pass-1" not in serialized
```

另测登录失败、管理员禁用、角色变更、强制退出、临时密码重置、日志查看都写入审计；30 天前记录被清理。

- [ ] **Step 2: 运行失败测试**

Run: `uv run pytest tests/test_audit_logs.py -q`

Expected: FAIL，审计服务不存在。

- [ ] **Step 3: 实现审计写入和查询**

`details` 只接受显式白名单字段。禁止把 Pydantic 请求对象或异常对象直接序列化进审计详情。

- [ ] **Step 4: 接入认证与管理员事件**

认证失败时 actor 可为空，target 仅记录已存在用户 ID；公开响应不暴露该 ID。

- [ ] **Step 5: 验证**

Run:

```powershell
uv run ruff check .
uv run pytest tests/test_audit_logs.py -q
uv run pytest
```

Expected: 全部通过。

- [ ] **Step 6: 提交**

```powershell
git add backend/app/repositories/audit.py backend/app/services/audit.py backend/app/schemas/logs.py backend/app/routers/audit_logs.py backend/tests/test_audit_logs.py backend/app/services/auth.py backend/app/services/admin.py backend/app/main.py
git commit -m "feat: 增加账号审计日志"
```

---

### Task 5: 个人历史存储、配额与生命周期

**Files:**
- Create: `backend/app/repositories/history.py`
- Create: `backend/app/repositories/history_storage.py`
- Create: `backend/app/services/history.py`
- Create: `backend/app/schemas/history.py`
- Create: `backend/app/routers/history.py`
- Create: `backend/tests/test_history.py`
- Modify: `backend/app/config.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/repositories/temp_storage.py`

**Interfaces:**
- Produces: `HistoryService.capture_result(user, tool, operation, result) -> HistoryCapture`
- Produces: `HistoryService.list_for_user(user_id) -> list[HistoryItem]`
- Produces: `HistoryService.resolve_download(user_id, history_id) -> Path`
- Produces: `HistoryService.cleanup(now) -> CleanupSummary`

- [ ] **Step 1: 写历史失败测试**

```python
def test_eleventh_history_file_evicts_oldest(history_service, user):
    for index in range(10):
        history_service.capture_result(
            user=user,
            tool="qrcode",
            operation="generate",
            result=make_result(index, size_bytes=10),
            now=BASE_TIME + timedelta(seconds=index),
        )
    capture = history_service.capture_result(
        user=user,
        tool="qrcode",
        operation="generate",
        result=make_result(10, size_bytes=10),
        now=BASE_TIME + timedelta(seconds=20),
    )
    assert capture.saved is True
    assert capture.evicted_count == 1
```

另测：

- 每用户 200MB 上限。
- 并发保存后活跃数量不超过 10。
- 单结果 200MB+ 不保存，但返回可下载当前结果。
- 完成 30 分钟后文件删除、状态 expired、`purge_after=expired_at+3h`。
- 过期占位不占配额。
- 用户不能下载他人历史。
- 过期下载返回 410。
- 物理删除失败会在下一轮重试。

- [ ] **Step 2: 运行失败测试**

Run: `uv run pytest tests/test_history.py -q`

Expected: FAIL，历史服务不存在。

- [ ] **Step 3: 实现历史存储和配额**

历史根目录默认：

```python
history_root: Path = Path("./history")
history_max_items: int = 10
history_max_bytes: int = 200 * 1024 * 1024
history_retention_minutes: int = 30
history_placeholder_hours: int = 3
```

用户级锁使用进程内 `threading.Lock`，数据库事务中查询并更新该用户历史。单实例上限说明保留 `ponytail:` 注释，多实例时升级数据库锁或队列。

- [ ] **Step 4: 实现文件复制和所有权下载**

优先对同一文件系统上的结果创建硬链接，失败时复制。历史路径固定为：

```text
{history_root}/{user_id}/{history_id}/{safe_filename}
```

下载前验证记录 owner、状态和路径父目录。

- [ ] **Step 5: 清理循环**

每分钟：

- 标记到期活跃记录。
- 删除文件。
- 删除 `purge_after <= now` 的占位。

每日清理审计日志并重新计算运行日志总量。

- [ ] **Step 6: 验证**

Run:

```powershell
uv run ruff check .
uv run pytest tests/test_history.py -q
uv run pytest
```

Expected: 全部通过。

- [ ] **Step 7: 提交**

```powershell
git add backend/app/repositories/history.py backend/app/repositories/history_storage.py backend/app/services/history.py backend/app/schemas/history.py backend/app/routers/history.py backend/tests/test_history.py backend/app/config.py backend/app/main.py backend/app/repositories/temp_storage.py
git commit -m "feat: 增加个人历史配额与生命周期"
```

---

### Task 6: 接入 Excel、二维码和 MAC 处理结果

**Files:**
- Modify: `backend/app/routers/excel.py`
- Modify: `backend/app/routers/qrcode.py`
- Modify: `backend/app/services/qrcode_service.py`
- Modify: `backend/tests/test_api.py`
- Modify: `backend/tests/test_qrcode.py`
- Modify: `frontend/lib/types.ts`
- Modify: `frontend/lib/api.ts`
- Modify: `frontend/app/excel/excel-workspace.tsx`
- Modify: `frontend/app/qrcode/qrcode-tools.tsx`
- Modify: `frontend/app/qrcode/mac-address-tool.tsx`

**Interfaces:**
- Produces Excel `data.history`：

```typescript
type HistoryCapture = {
  saved: boolean;
  history_id?: string;
  notice?: string;
  evicted_count?: number;
};
```

- Produces QR response headers:
  - `X-History-Status: saved|not_saved`
  - `X-History-Id`
  - `X-History-Notice`

- [ ] **Step 1: 写结果接入失败测试**

```python
def test_logged_in_excel_result_is_added_to_history(authenticated_client, upload):
    response = authenticated_client.post("/api/v1/excel/split", json=payload)
    assert response.json()["data"]["history"]["saved"] is True
```

```python
def test_logged_in_qrcode_result_returns_history_headers(authenticated_client):
    response = authenticated_client.post("/api/v1/qrcode/generate", json={
        "content": "hello",
        "size": 128,
        "mode": "text",
    })
    assert response.headers["X-History-Status"] == "saved"
```

另测匿名请求不创建历史、历史保存失败不改变原业务成功、二维码解析不保存文本。

- [ ] **Step 2: 运行失败测试**

Run:

```powershell
uv run pytest tests/test_api.py tests/test_qrcode.py -q -k history
```

Expected: FAIL，响应没有历史信息。

- [ ] **Step 3: 接入可选登录用户**

Excel 和 QR 路由使用 `get_optional_user`。Token 缺失或失效时继续匿名处理，不阻断工具。

- [ ] **Step 4: 返回历史提示**

Excel 保留 JSON 响应并附加 `history`。QR 保持二进制 PNG，通过响应头传递保存状态。敏感提示只使用固定中文文案。

- [ ] **Step 5: 前端展示状态横幅**

Excel 结果区展示保存成功、自动清理数量、“结果过大未保存”或“保存失败”。QR/MAC 读取响应头并展示同样提示。

- [ ] **Step 6: 验证**

Run:

```powershell
cd backend
uv run ruff check .
uv run pytest tests/test_api.py tests/test_qrcode.py -q
cd ../frontend
pnpm lint
pnpm typecheck
pnpm build
```

Expected: 全部通过。

- [ ] **Step 7: 提交**

```powershell
git add backend/app/routers/excel.py backend/app/routers/qrcode.py backend/app/services/qrcode_service.py backend/tests/test_api.py backend/tests/test_qrcode.py frontend/lib/types.ts frontend/lib/api.ts frontend/app/excel/excel-workspace.tsx frontend/app/qrcode/qrcode-tools.tsx frontend/app/qrcode/mac-address-tool.tsx
git commit -m "feat: 接入登录用户处理历史"
```

---

### Task 7: 受限运行错误日志与管理员日志下载

**Files:**
- Modify: `backend/app/common/logging.py`
- Modify: `backend/app/config.py`
- Create: `backend/app/repositories/runtime_logs.py`
- Create: `backend/app/services/runtime_logs.py`
- Modify: `backend/app/routers/audit_logs.py`
- Create: `backend/tests/test_runtime_logs.py`
- Modify: `compose.yaml`

**Interfaces:**
- Produces: `DailyCappedFileHandler`
- Produces: `RuntimeLogService.list_errors(date, page)`
- Produces: `RuntimeLogService.resolve_download(date)`

- [ ] **Step 1: 写日志上限失败测试**

```python
def test_runtime_error_file_stops_at_daily_cap(tmp_path, settings):
    handler = DailyCappedFileHandler(tmp_path, max_bytes=1024)
    logger = make_logger(handler)
    for index in range(100):
        logger.error("failure-%s-%s", index, "x" * 100)
    files = list(tmp_path.glob("runtime-errors-*.jsonl"))
    assert sum(path.stat().st_size for path in files) <= 1024
```

另测只写 WARNING/ERROR，14 天前文件删除，总目录不超过 64MB，日期参数不能路径穿越，按日期下载正确文件。

- [ ] **Step 2: 运行失败测试**

Run: `uv run pytest tests/test_runtime_logs.py -q`

Expected: FAIL，按日日志 Handler 不存在。

- [ ] **Step 3: 实现按日文件日志**

文件格式：

```text
{log_root}/runtime-errors-YYYY-MM-DD.jsonl
```

日期按 `Asia/Shanghai`。普通 INFO 只使用 stdout；文件 Handler 阈值设为 WARNING。达到 5MB 后停止写文件并向 stderr 输出一次容量提示。

- [ ] **Step 4: 实现管理员查询和下载**

日期严格解析 `YYYY-MM-DD`，文件路径通过日期生成，不接受用户路径。列表按 JSON Lines 逐行读取并限制每页 100 条。下载使用 `FileResponse`。

- [ ] **Step 5: 调整 Docker 日志**

三服务 `max-size: 5m`、`max-file: "3"`。

- [ ] **Step 6: 验证**

Run:

```powershell
uv run ruff check .
uv run pytest tests/test_runtime_logs.py tests/test_audit_logs.py -q
docker compose config --quiet
```

Expected: 全部通过。

- [ ] **Step 7: 提交**

```powershell
git add backend/app/common/logging.py backend/app/config.py backend/app/repositories/runtime_logs.py backend/app/services/runtime_logs.py backend/app/routers/audit_logs.py backend/tests/test_runtime_logs.py compose.yaml
git commit -m "feat: 增加受限运行错误日志与下载"
```

---

### Task 8: 前端认证基础与账号页面

**Files:**
- Create: `frontend/lib/auth-storage.ts`
- Create: `frontend/lib/auth-api.ts`
- Create: `frontend/components/auth-provider.tsx`
- Create: `frontend/components/account-nav.tsx`
- Create: `frontend/components/auth-guard.tsx`
- Create: `frontend/app/login/page.tsx`
- Create: `frontend/app/register/page.tsx`
- Create: `frontend/app/recover/page.tsx`
- Create: `frontend/app/change-password/page.tsx`
- Modify: `frontend/app/layout.tsx`
- Modify: `frontend/components/site-header.tsx`
- Create: `frontend/tests/e2e/accounts.spec.ts`
- Modify: `frontend/lib/types.ts`

**Interfaces:**
- Produces: `getToken()`, `setToken(token)`, `clearToken()`
- Produces: `useAuth()` with `user`, `loading`, `login`, `logout`, `refresh`
- Produces: `authenticatedFetch(path, init)` that adds Bearer header.

- [ ] **Step 1: 写认证 E2E 失败测试**

```typescript
test("用户可以注册、登录、刷新后保持会话并退出", async ({ page }) => {
  await page.goto("/register");
  await page.getByLabel("用户名").fill("00123456");
  await page.getByLabel("密码", { exact: true }).fill("Password1");
  await page.getByLabel("找回问题").fill("我的问题");
  await page.getByLabel("找回答案").fill("我的答案");
  await page.getByRole("button", { name: "注册账号" }).click();
  await expect(page.getByText("个人历史")).toBeVisible();
  await page.reload();
  await expect(page.getByText("00123456")).toBeVisible();
  await page.getByRole("button", { name: "退出登录" }).click();
  await expect(page.getByRole("link", { name: "登录" })).toBeVisible();
});
```

另测找回密码、临时密码强制改密、无 Token 打开 `/history` 跳转登录、用户名和密码长度校验。

- [ ] **Step 2: 运行失败测试**

Run: `pnpm exec playwright test tests/e2e/accounts.spec.ts`

Expected: FAIL，认证页面不存在。

- [ ] **Step 3: 实现 Token 存储与 Auth Provider**

只在浏览器使用 `sessionStorage`；SSR 时返回空 Token。`authenticatedFetch` 遇 401 清除 Token 并触发登录跳转。

- [ ] **Step 4: 实现注册、登录、找回和改密页面**

输入字段使用正确 `autoComplete`、label 和中文校验提示。密码不写日志、不显示明文。

- [ ] **Step 5: 修改导航**

匿名显示“登录”；登录显示用户名、个人历史、退出；admin 额外显示账号管理和日志中心。

- [ ] **Step 6: 验证**

Run:

```powershell
pnpm lint
pnpm typecheck
pnpm build
pnpm exec playwright test tests/e2e/accounts.spec.ts
```

Expected: 全部通过。

- [ ] **Step 7: 提交**

```powershell
git add frontend/lib/auth-storage.ts frontend/lib/auth-api.ts frontend/components/auth-provider.tsx frontend/components/account-nav.tsx frontend/components/auth-guard.tsx frontend/app/login frontend/app/register frontend/app/recover frontend/app/change-password frontend/app/layout.tsx frontend/components/site-header.tsx frontend/tests/e2e/accounts.spec.ts frontend/lib/types.ts
git commit -m "feat: 增加前端账号认证"
```

---

### Task 9: 个人历史页面

**Files:**
- Create: `frontend/app/history/page.tsx`
- Create: `frontend/components/history-list.tsx`
- Create: `frontend/tests/e2e/history.spec.ts`
- Modify: `frontend/lib/auth-api.ts`
- Modify: `frontend/lib/types.ts`

**Interfaces:**
- Consumes `GET /api/v1/history`.
- Consumes owner-only download endpoint.
- Produces active/expired rows with download or disabled state.

- [ ] **Step 1: 写历史页面失败测试**

```typescript
test("历史列表区分可下载和已过期文件", async ({ page }) => {
  await mockHistory(page, [
    { id: "active-1", status: "active", result_filename: "结果.zip" },
    { id: "expired-1", status: "expired", result_filename: "旧结果.zip", expire_reason: "timeout" },
  ]);
  await page.goto("/history");
  await expect(page.getByRole("link", { name: "下载结果" })).toBeVisible();
  await expect(page.getByText("已过期", { exact: true })).toBeVisible();
  await expect(page.getByText("30 分钟已到期")).toBeVisible();
});
```

- [ ] **Step 2: 运行失败测试**

Run: `pnpm exec playwright test tests/e2e/history.spec.ts`

Expected: FAIL，页面不存在。

- [ ] **Step 3: 实现历史列表**

展示工具、操作、文件名、大小、完成时间、状态、过期原因和清除时间。过期项无下载按钮。

- [ ] **Step 4: 实现鉴权下载**

下载通过 `authenticatedFetch` 携带 Bearer；401 跳登录，410 显示“文件已过期”，403 显示无权限。

- [ ] **Step 5: 验证**

Run:

```powershell
pnpm lint
pnpm typecheck
pnpm build
pnpm exec playwright test tests/e2e/history.spec.ts
```

Expected: 全部通过。

- [ ] **Step 6: 提交**

```powershell
git add frontend/app/history frontend/components/history-list.tsx frontend/tests/e2e/history.spec.ts frontend/lib/auth-api.ts frontend/lib/types.ts
git commit -m "feat: 增加个人历史页面"
```

---

### Task 10: 管理员账号与日志页面

**Files:**
- Create: `frontend/app/admin/users/page.tsx`
- Create: `frontend/app/admin/logs/page.tsx`
- Create: `frontend/components/admin-user-table.tsx`
- Create: `frontend/components/audit-log-table.tsx`
- Create: `frontend/components/runtime-error-table.tsx`
- Create: `frontend/tests/e2e/admin.spec.ts`
- Modify: `frontend/lib/auth-api.ts`
- Modify: `frontend/lib/types.ts`
- Create: `frontend/tests/e2e-real/accounts-history.spec.ts`

**Interfaces:**
- Consumes spec admin APIs.
- Produces user actions: enable, disable, promote, demote, force logout, reset password.
- Produces log tabs, date filters, pagination and downloads.

- [ ] **Step 1: 写管理员页面失败测试**

```typescript
test("管理员可禁用用户但看不到密码", async ({ page }) => {
  await mockAdmin(page);
  await page.goto("/admin/users");
  await expect(page.getByText("00123456")).toBeVisible();
  await expect(page.getByText(/password|密码哈希/i)).toHaveCount(0);
  await page.getByRole("button", { name: "禁用账号" }).click();
  await expect(page.getByText("账号已禁用")).toBeVisible();
});
```

另测日志页切换、日期筛选、CSV/JSON 下载、错误文件下载和普通用户无法进入。

- [ ] **Step 2: 运行失败测试**

Run: `pnpm exec playwright test tests/e2e/admin.spec.ts`

Expected: FAIL，页面不存在。

- [ ] **Step 3: 实现管理员账号页面**

重置密码响应中的临时密码只显示一次，关闭对话框后不可再次获取。最后一个管理员操作失败时显示后端中文错误。

- [ ] **Step 4: 实现日志中心**

操作审计和运行错误分页。日期输入限制为最近 30 天。下载按钮携带 Bearer Token。

- [ ] **Step 5: 增加真实流程测试**

真实 Playwright 覆盖：

- 创建普通用户和管理员。
- 普通用户保存 Excel 历史并下载。
- 普通用户越权下载另一用户历史失败。
- 管理员查看和下载日志。
- 管理员禁用用户后旧 Token 失效。

- [ ] **Step 6: 验证**

Run:

```powershell
pnpm lint
pnpm typecheck
pnpm build
pnpm exec playwright test tests/e2e/admin.spec.ts
pnpm test:e2e:real
```

Expected: 全部通过。

- [ ] **Step 7: 提交**

```powershell
git add frontend/app/admin frontend/components/admin-user-table.tsx frontend/components/audit-log-table.tsx frontend/components/runtime-error-table.tsx frontend/tests/e2e/admin.spec.ts frontend/tests/e2e-real/accounts-history.spec.ts frontend/lib/auth-api.ts frontend/lib/types.ts
git commit -m "feat: 增加管理员账号与日志页面"
```

---

### Task 11: CSP、部署迁移与全量验收

**Files:**
- Create: `frontend/proxy.ts`
- Modify: `frontend/app/layout.tsx`
- Modify: `frontend/app/qrcode/qrcode-tools.tsx`
- Modify: `frontend/app/qrcode/mac-address-tool.tsx`
- Modify: `compose.yaml`
- Modify: `backend/Dockerfile`
- Modify: `README.md`
- Modify: `docs/ENGINEERING_GUIDE.md`
- Modify: `docs/PRODUCT_DESIGN.md`

**Interfaces:**
- Produces nonce CSP for all rendered pages.
- Produces one-command migrations and initial admin instructions.

- [ ] **Step 1: 写 CSP 失败测试**

Playwright 监听 `console` 和 `pageerror`，访问首页、工作台、登录、历史和管理员页面，断言无 CSP violation。

- [ ] **Step 2: 实现 Next.js nonce CSP**

按 Next.js 16 Proxy 文档创建 `frontend/proxy.ts`，设置：

```text
default-src 'self'
script-src 'self' 'nonce-...' 'strict-dynamic'
style-src 'self' 'nonce-...'
img-src 'self' blob: data:
connect-src 'self'
object-src 'none'
base-uri 'self'
form-action 'self'
frame-ancestors 'none'
```

开发环境额外允许 `unsafe-eval`；生产开启 `upgrade-insecure-requests`。

- [ ] **Step 3: 移除不兼容的内联样式**

把二维码页面的 `style={{ animationDelay: ... }}` 改为 Tailwind 任意属性类，例如 `[animation-delay:70ms]`。

- [ ] **Step 4: 部署和文档**

README 增加：

- MySQL 首次启动和迁移。
- 初始化管理员命令。
- Bearer Token 与 sessionStorage 说明。
- 个人历史配额和过期规则。
- 管理员账号管理和日志下载。
- 日志磁盘上限和清理。

- [ ] **Step 5: 全量验证**

Run:

```powershell
cd backend
uv run ruff check .
uv run pytest
cd ../frontend
pnpm lint
pnpm typecheck
pnpm build
pnpm exec playwright test
pnpm test:e2e:real
cd ..
docker compose config --quiet
docker compose up -d --build
docker compose exec backend alembic current
```

Expected:

- 全部测试通过。
- Compose 三服务加 MySQL 全部健康。
- 空库迁移成功。
- 管理员可登录。
- 8080 页面和 API 正常。
- 请求日志有 `request_id`。
- 个人历史文件可下载。
- 过期占位和日志下载可用。

- [ ] **Step 6: 提交**

```powershell
git add frontend/proxy.ts frontend/app/layout.tsx frontend/app/qrcode/qrcode-tools.tsx frontend/app/qrcode/mac-address-tool.tsx compose.yaml backend/Dockerfile README.md docs/ENGINEERING_GUIDE.md docs/PRODUCT_DESIGN.md
git commit -m "chore: 完成三期部署与安全验收"
```

---

## 完成标准

- 所有匿名工具回归通过。
- 普通用户和管理员权限隔离通过。
- 个人历史配额、过期和占位规则通过。
- 管理员不能看到密码、找回答案或用户文件。
- 审计日志和运行错误日志按日期下载通过。
- 日志磁盘硬上限通过。
- MySQL 迁移和 Compose 实际启动通过。
- 工作区干净，每个独立功能都有可回滚提交。
