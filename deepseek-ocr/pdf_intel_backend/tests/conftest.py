"""强制单元测试走 MOCK（环境变量优先于 .env，覆盖本机 SILICONFLOW_API_KEY）。"""
from __future__ import annotations

import os

os.environ["USE_MOCK"] = "true"
os.environ["SILICONFLOW_API_KEY"] = ""
os.environ["SILICONFLOW_SKIP_QWEN"] = "false"
