# Feishu + Streamlit 验证排查

## 1. 飞书里打不开页面

检查项：

1. 飞书网页应用主页地址是否为最新 URL（TryCloudflare 每次重启会变化）
2. H5 可信域名是否与主页域名一致
3. tunnel 进程是否仍在运行
4. 本地 Streamlit 是否仍监听 `8501`

命令：

```bash
lsof -i:8501
curl -I https://hawaii-freely-damages-respected.trycloudflare.com
```

## 2. 页面能开但交互异常

Streamlit 依赖 websocket 连接，若反向代理不支持或中间层拦截，可能出现按钮无响应、重复刷新等问题。

建议：

- 优先使用 Cloudflare Tunnel / ngrok 的 HTTPS 地址
- 确认代理未禁用 websocket
- 更换网络环境再测（公司网可能拦截）

## 3. 混合内容或安全策略报错

飞书里建议统一使用 HTTPS 主页地址。避免在页面中加载 HTTP 资源。

## 4. URL 过期

TryCloudflare 链接是临时的。若 cloudflared 重启，URL 会变化，需要同步更新飞书后台：

- 网页配置 -> 桌面端主页 / 移动端主页
- 安全设置 -> H5 可信域名
