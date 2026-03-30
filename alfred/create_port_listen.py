# -*- coding: utf-8 -*-
"""
生成可双击导入 Alfred 的 .alfredworkflow 包。

问题：纯 Keyword「port」输入后 Alfred 仍出谷歌，列表里像没有 port 工作流。
原因：默认网页搜索优先级更高，Keyword 不会先占住搜索框。

做法：
1. Script Filter + 关键字 port → 输入 port 空格 后，列表只显示脚本结果，不再被谷歌抢占。
2. Script Filter 只负责展示一条「可回车执行」的项，并把 arg 设为端口/别名。
3. Run Script 接在 Script Filter 后面 → 只有选中该项按回车才执行一次 nc（不会在每敲一键就跑）。
"""
import os
import shutil
import tempfile
import uuid
import zipfile
import plistlib


def _uid():
    return str(uuid.uuid4()).upper()


def create_alfred_workflow(output_name="Check-Port.alfredworkflow"):
    sf_uid = _uid()
    script_uid = _uid()

    # Script Filter：只输出 JSON，不做 nc（避免每键都检测）
    filter_script = r'''#!/bin/zsh
export PATH="/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
Q="$1"
Q="${Q// /}"

/usr/bin/python3 -c "
import json, sys
q = sys.argv[1] if len(sys.argv) > 1 else ''
if not q:
    out = {
        'skipknowledge': True,
        'items': [{
            'title': '端口检测（port）',
            'subtitle': '继续输入 8848 或 mysql，再回车执行检测',
            'arg': '',
            'valid': False,
        }]
    }
else:
    out = {
        'skipknowledge': True,
        'items': [{
            'title': '回车检测: ' + q,
            'subtitle': '仅执行一次 nc + 通知',
            'arg': q,
            'valid': True,
        }]
    }
print(json.dumps(out, ensure_ascii=False))
" "$Q"
'''

    # Run Script：仅在被选中并回车时运行；$1 为 Script Filter 传入的 arg
    run_script = r'''#!/bin/zsh
export PATH="/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

typeset -A PORT_MAP
PORT_MAP=(
  nacos 8848 mysql 3306 redis 6379 mongodb 27017 elasticsearch 9200
  kafka 9092 rabbitmq 5672 postgresql 5432 nginx 80 http 80 https 443
  tomcat 8080 jenkins 8080 zookeeper 2181
)

INPUT="$1"
INPUT="${INPUT#port}"
INPUT="${INPUT#Port}"
INPUT="${INPUT#PORT}"
INPUT="${INPUT// /}"

if [[ -z "$INPUT" ]]; then
  osascript -e 'display notification "请先输入端口或别名再回车" with title "端口检测"'
  exit 0
fi

if [[ "$INPUT" =~ '^[0-9]+$' ]]; then
  PORT="$INPUT"
  SERVICE_NAME="Port $PORT"
elif [[ -n "${PORT_MAP[$INPUT]}" ]]; then
  PORT="${PORT_MAP[$INPUT]}"
  SERVICE_NAME="${(U)INPUT}"
else
  osascript -e "display notification \"未知: $INPUT\" with title \"端口检测\""
  exit 0
fi

HOST="localhost"
if nc -z "$HOST" "$PORT" 2>/dev/null; then
  STATUS="运行中"
else
  STATUS="未运行"
fi

osascript -e "display notification \"$SERVICE_NAME ($PORT) - $STATUS\" with title \"端口检测\" sound name \"default\""
'''

    # Script Filter 选中项回车 → Run Script；Run Script 使用上一节点传入的 arg
    connections = {
        sf_uid: [
            {
                "destinationuid": script_uid,
                "modifiers": 0,
                "modifiersubtext": "",
                "vitoclose": False,
            }
        ]
    }

    objects = [
        {
            "config": {
                "concurrently": False,
                "escaping": 102,
                "script": run_script,
                "scriptargtype": 1,
                "scriptfile": "",
                "type": 11,
            },
            "type": "alfred.workflow.action.script",
            "uid": script_uid,
            "version": 2,
        },
        {
            "config": {
                "alfredfiltersresults": False,
                "alfredfiltersresultsmatchmode": 0,
                "argumenttreatemptyqueryasnil": True,
                "argumenttrimmode": 0,
                "argumenttype": 1,
                "escaping": 102,
                "keyword": "port",
                "queuedelaycustom": 5,
                "queuedelayimmediatelyinitially": False,
                "queuedelaymode": 0,
                "queuemode": 2,
                "runningsubtext": "…",
                "script": filter_script,
                "scriptargtype": 1,
                "scriptfile": "",
                "skipuniversalaction": True,
                "subtext": "输入 port 空格 后，列表会固定在本工作流",
                "title": "端口检测",
                "type": 11,
                "withspace": True,
            },
            "type": "alfred.workflow.input.scriptfilter",
            "uid": sf_uid,
            "version": 3,
        },
    ]

    uidata = {
        sf_uid: {"xpos": 30.0, "ypos": 75.0},
        script_uid: {"xpos": 455.0, "ypos": 75.0},
    }

    info_plist = {
        "bundleid": "com.example.checkport",
        "category": "Tools",
        "connections": connections,
        "createdby": "shaver",
        "description": "port 空格 后列表不再出谷歌；选结果回车才 nc 检测",
        "disabled": False,
        "name": "Check Port",
        "objects": objects,
        "readme": "1) 输入 port 再空格，下面会变成工作流结果而不是谷歌。\n"
        "2) 输入 8848 或 mysql，出现「回车检测」那条后按回车，才执行一次检测。\n"
        "3) 若仍先出谷歌，请删除旧工作流后重新导入本包。",
        "uidata": uidata,
        "userconfigurationconfig": [],
        "webaddress": "",
    }

    staging = tempfile.mkdtemp(prefix="alfred_workflow_")
    try:
        plist_path = os.path.join(staging, "info.plist")
        with open(plist_path, "wb") as f:
            plistlib.dump(info_plist, f, fmt=plistlib.FMT_XML)

        out_dir = os.path.dirname(os.path.abspath(__file__))
        out_path = os.path.join(out_dir, output_name)
        if os.path.isdir(out_path):
            shutil.rmtree(out_path)
        if os.path.isfile(out_path):
            os.remove(out_path)

        with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, _dirs, files in os.walk(staging):
                for name in files:
                    fp = os.path.join(root, name)
                    arcname = os.path.relpath(fp, staging)
                    zf.write(fp, arcname)

        print(f"✅ 已生成: {out_path}")
        print("📥 删掉旧 Check Port 后重新导入。")
        print("⌨️  port 空格 → 列表会留在本工作流；输入 8848 后回车才检测。")
    finally:
        shutil.rmtree(staging, ignore_errors=True)


if __name__ == "__main__":
    create_alfred_workflow()
