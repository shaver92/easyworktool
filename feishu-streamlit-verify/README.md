# 飞书工作台物资管理系统（MVP）

本项目已从可行性验证页升级为 `Streamlit + SQLite` 的物资管理系统 MVP，支持：

- 飞书用户身份识别（支持 query 参数模拟与飞书接口读取）
- 管理员/普通用户权限控制（管理员白名单来自配置文件）
- 物资台账、借用归还、上下架、库存调整
- 审计日志、通知日志
- 到期/逾期飞书提醒（可开关）

## 1) 安装依赖

```bash
conda create -n feishu-streamlit python=3.12 -y
conda activate feishu-streamlit
pip install -r requirements.txt
```

## 2) 配置方式（推荐使用 `.env`）

项目根目录已提供 `.env`，建议直接修改该文件：

- `APP_REQUIRE_BORROW_APPROVAL`: 是否启用借用审批流
- `RBAC_ADMIN_OPEN_IDS`: 管理员 `open_id` 白名单
- `NOTIFY_ENABLE`: 是否启用飞书发消息（默认关闭）
- `FEISHU_TENANT_ACCESS_TOKEN`: 启用通知时必填
- `APP_HOME_URL`: 卡片消息中的“打开系统”跳转地址
- `NOTIFY_ADMIN_CC_OPEN_IDS`: 逾期时抄送管理员
- `NOTIFY_USE_TEMPLATE_CARD`: 是否启用飞书模板卡片（默认 false，使用内置交互卡片）

说明：`.env` 的配置会覆盖 `config/app_config.toml` 中的同名项。

提醒消息中的按钮会自动携带 `page` 与 `order_id` 参数，支持进入系统后自动定位到对应借用单。
当前默认直达 `借用单详情` 页面，展示该单的状态、审计轨迹、通知轨迹，并支持在详情页执行归还。
系统已支持“部分归还”，借用单状态会在 `borrowed` / `partially_returned` / `returned` 之间流转。
管理员可在借用单详情页执行“催还一次”，触发手动催还消息。
启用审批流后，借用单状态还会包含 `pending_approval` / `rejected`。

## 3) 启动 Streamlit

```bash
streamlit run app.py --server.address 0.0.0.0 --server.port 8501
```

本地验证地址：

- http://localhost:8501

## 4) 暴露公网地址（任选）

### Cloudflare Tunnel

```bash
cloudflared tunnel --url http://localhost:8501
```

### ngrok

```bash
ngrok http 8501
```

复制生成的 HTTPS 地址（例如 `https://xxxx.trycloudflare.com` / `https://xxxx.ngrok-free.app`）。

## 5) 飞书开放平台配置

在飞书应用能力中添加「网页应用」（应用名建议：`物资管理系统`），填写：

- 桌面端主页：`<你的 HTTPS 地址>`
- 移动端主页：`<你的 HTTPS 地址>`

在安全设置中添加 H5 可信域名：

- `<你的域名:端口>`（例如 `https://xxxx.trycloudflare.com`）

参考文档：

- https://open.feishu.cn/document/integrating-web-apps-in-5-minutes/step-4-configure-the-home-page-address

## 6) 固定域名（Cloudflare Named Tunnel）

如果你不想每次都换 URL，请改用 Named Tunnel：

```bash
cloudflared tunnel login
cloudflared tunnel create material-management
cloudflared tunnel route dns material-management wzgl.<your-domain>
```

然后在 `~/.cloudflared/config.yml` 将 ingress 指向 `http://localhost:8501`，并运行：

```bash
cloudflared tunnel run material-management
```

## 7) 本地快速体验（无需真实飞书登录）

通过 query 参数模拟用户身份：

- 普通用户：
  - `http://localhost:8501/?open_id=ou_user_demo&name=普通用户`
- 管理员（需与 `admin_open_ids` 一致）：
  - `http://localhost:8501/?open_id=ou_admin_demo&name=管理员`

## 8) 目录结构

```text
app.py
config/app_config.toml
src/
  auth/            # 飞书身份与 RBAC
  db/              # SQLite schema 与 repository
  services/        # 物资、借还、通知、审计、调度
  pages/           # Streamlit 页面
```

## 9) 上线前核对

- 生产发布请先逐项核对：`PRODUCTION_CHECKLIST.md`
