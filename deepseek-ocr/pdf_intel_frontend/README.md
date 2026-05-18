# pdf_intel_frontend

Vite + React：上传 PDF，调用后端 `POST /api/parse-pdf`，展示结构化结果与 Markdown。

开发服务器将 `/api`、`/health` 代理到 `http://127.0.0.1:8765`（见 `vite.config.ts`）。

## Conda 环境中使用（与仓库 `deepseek-ocr/environment.yml` 一致）

```bash
conda activate pdf-intel
cd deepseek-ocr/pdf_intel_frontend
npm install
npm run dev
```

浏览器打开 <http://localhost:5173>，需先在本机启动后端（见上级目录计划文档中的 Conda 启动步骤）。

## 生产构建

```bash
npm run build
npm run preview
```

生产环境请配置实际 API 地址（可自行改为 `import.meta.env.VITE_API_BASE` + 绝对 URL 请求，而非 dev 代理）。
