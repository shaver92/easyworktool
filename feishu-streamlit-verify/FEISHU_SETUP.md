# 飞书网页应用配置（物资管理系统）

应用名称建议：`物资管理系统`

## 可直接填写的地址

- 桌面端主页：
  - `https://hawaii-freely-damages-respected.trycloudflare.com`
- 移动端主页：
  - `https://hawaii-freely-damages-respected.trycloudflare.com`

## H5 可信域名

- `https://hawaii-freely-damages-respected.trycloudflare.com`

## 配置路径（飞书后台）

1. 进入应用能力 -> 网页应用
2. 在「网页配置」中填写桌面端主页和移动端主页
3. 进入「安全设置」-> H5 可信域名，添加上面的域名
4. 保存并发布当前版本

## 注意

- TryCloudflare 链接是临时的，进程重启后会变化。
- 如果 URL 变化，需要同步更新飞书后台的主页地址和 H5 可信域名。

## 固定地址（推荐）

如果使用 Cloudflare Named Tunnel，建议固定为：

- Tunnel 名称：`material-management`
- 固定域名示例：`https://wzgl.<your-domain>`

### 1) 一键创建（已内置脚本）

在项目根目录执行：

```bash
DOMAIN=<your-domain> ./scripts/setup_named_tunnel.sh
```

例如：

```bash
DOMAIN=corp.mms.com ./scripts/setup_named_tunnel.sh
```

执行后会自动完成：

1. `cloudflared tunnel login`
2. 创建（或复用）`material-management` tunnel
3. 绑定 DNS：`wzgl.<your-domain>`
4. 生成 `~/.cloudflared/config.yml`

### 2) 启动固定 tunnel

```bash
cloudflared tunnel run material-management
```

### 3) 更新 `.env`

将以下两项改为固定域名（保持一致）：

```env
APP_HOME_URL=https://wzgl.<your-domain>/
FEISHU_REDIRECT_URI=https://wzgl.<your-domain>/
```

### 4) 更新飞书后台

把飞书后台中的以下地址都更新为固定域名：

- 桌面端主页：`https://wzgl.<your-domain>/`
- 移动端主页：`https://wzgl.<your-domain>/`
- H5 可信域名：`https://wzgl.<your-domain>`
- OAuth 回调地址：`https://wzgl.<your-domain>/`

### 5) 配置模板（可选）

如需手动检查配置文件模板，可参考：`cloudflared/config.yml.example`

## OAuth 登录配置（推荐）

为了让系统根据飞书登录用户自动识别管理员/普通用户，请配置 OAuth 并让飞书回调带 `code` 参数。

### 1) 开放平台权限

- 在应用权限中开启获取用户基础信息能力（用于读取 `open_id/name/email`）。
- 发布应用并确保当前企业可见。

### 2) 配置回调地址

- 在飞书应用 OAuth 设置中，新增回调地址：
  - `https://<你的域名>/`
- 本项目会在 `app.py` 中读取 URL 上的 `code` 参数并换取用户信息。

### 3) 更新本地配置（推荐编辑 `.env`）

编辑项目根目录 `.env`：

- `FEISHU_APP_ID=cli_xxx`
- `FEISHU_APP_SECRET=xxx`
- `FEISHU_BASE_URL=https://open.feishu.cn/open-apis`
- `FEISHU_REDIRECT_URI=https://<你的域名>/`

### 4) 验证方式

- 方式 A（真实链路）：从飞书工作台打开应用，URL 应包含 `code`，页面顶部来源应显示 `feishu_oauth_code`。
- 方式 B（本地调试）：通过 URL 手动传参 `open_id`，例如：
  - `http://localhost:8501/?open_id=ou_admin_demo&name=管理员`

## 飞书提醒增强配置

- 在 `.env` 中设置：
  - `NOTIFY_ENABLE=true`
  - `FEISHU_TENANT_ACCESS_TOKEN=<tenant_token>`
  - `APP_HOME_URL=https://<你的域名>/`
  - `NOTIFY_ADMIN_CC_OPEN_IDS=ou_xxx`（逾期抄送管理员）
- 消息类型默认采用交互卡片，用户可直接点击“打开系统处理”。
- 按钮会携带借用单定位参数（`page` + `order_id`），打开后会直接高亮对应单据。
- 当前按钮默认跳转到 `借用单详情` 页面，可查看该单审计轨迹与通知轨迹。
- 借用单详情页支持管理员一键催还（手动提醒），通知类型为 `manual_remind`。

## 借用审批流配置

- 在 `.env` 中配置 `APP_REQUIRE_BORROW_APPROVAL=true` 可启用审批流。
- 启用后流程为：用户提交 -> `pending_approval` -> 管理员通过后 `borrowed` 出库；管理员可驳回为 `rejected`。
