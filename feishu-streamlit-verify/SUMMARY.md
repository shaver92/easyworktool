# 飞书网页应用（物资管理系统）+ Streamlit 可行性验证总结

本文档把上一次“在飞书里添加网页应用（Streamlit）并验证可行性”的操作做成可复用记录，方便你后续复跑。

---

## 1. 新建验证工程

在仓库内新建目录：

- `feishu-streamlit-verify/`

包含文件：

- `app.py`：最小 Streamlit 页面（标题 + 文本输入 + 按钮 + 简单交互）
- `requirements.txt`：`streamlit` 依赖
- `README.md`：从 0 到 1 的部署/配置说明
- `FEISHU_SETUP.md`：飞书后台配置项（本次使用的 URL 与 H5 域名）
- `TROUBLESHOOT.md`：常见失败原因排查

---

## 2. 本地启动 Streamlit（验证页面可用）

进入验证目录并创建 conda 环境：

```bash
cd feishu-streamlit-verify
conda create -n feishu-streamlit python=3.12 -y
conda activate feishu-streamlit
pip install -r requirements.txt
```

启动时使用可被转发的绑定地址：

```bash
streamlit run app.py --server.address 0.0.0.0 --server.port 8501
```

本机可访问地址：

- `http://localhost:8501`

（本次使用 `nohup` 方式后台启动，并写入日志 `/tmp/feishu-streamlit.log`，以免终端关闭导致中断）

---

## 3. 将本地服务暴露为飞书可访问的 HTTPS URL

由于飞书用户需要能访问到“网页应用主页地址”，因此需要把 `8501` 对外暴露。

### 3.1 安装 Cloudflare Tunnel

```bash
brew install cloudflared
```

### 3.2 启动 Tunnel

```bash
nohup cloudflared tunnel --url http://localhost:8501 > /tmp/feishu-cloudflared.log 2>&1 &
```

Tunnel 启动后从日志中获取可访问 URL（本次生成）：

- `https://hawaii-freely-damages-respected.trycloudflare.com`

### 3.3 可达性验证

使用 curl 验证公网可访问：

```bash
curl -I https://hawaii-freely-damages-respected.trycloudflare.com
```

返回 `HTTP/2 200` 说明地址可达。

---

## 4. 飞书开放平台后台配置（网页应用：物资管理系统）

按飞书文档添加“网页应用”能力，并将应用命名为“物资管理系统”，然后在「网页配置」里填写：

- 桌面端主页：`https://hawaii-freely-damages-respected.trycloudflare.com`
- 移动端主页：`https://hawaii-freely-damages-respected.trycloudflare.com`

同时在「安全设置」里添加：

- H5 可信域名：`https://hawaii-freely-damages-respected.trycloudflare.com`

本次写好的填表内容见：

- `feishu-streamlit-verify/FEISHU_SETUP.md`

关键提醒：

- TryCloudflare 的地址通常是临时的，重启 tunnel 后可能变化。
- 如果 URL 变化，需要同步更新飞书后台的主页地址与 H5 可信域名。

---

## 5. 验收步骤（给飞书用户看效果）

1. 让飞书用户用“飞书里打开该网页应用”的方式访问页面
2. 检查：
   - 页面是否能加载（无 404/重定向异常）
   - 按钮/交互是否正常响应
   - 浏览器控制台是否出现 HTTPS/混合内容或跨域错误

如果验收失败，排查思路见：

- `feishu-streamlit-verify/TROUBLESHOOT.md`

---

## 6. 相关文档

- 飞书网页应用主页地址配置：https://open.feishu.cn/document/integrating-web-apps-in-5-minutes/step-4-configure-the-home-page-address

---

## 7. 固定地址命名建议（Cloudflare Named Tunnel）

如果你后续改为固定域名，建议统一使用以下命名（对应“物资管理系统”）：

- Tunnel 名称：`material-management`
- 子域名建议：`wzgl.<your-domain>`
- 完整访问地址示例：`https://wzgl.<your-domain>`

对应命令示例：

```bash
cloudflared tunnel create material-management
cloudflared tunnel route dns material-management wzgl.<your-domain>
cloudflared tunnel run material-management
```

