"""图表工具：在沙箱里用 matplotlib 生成 PNG 图表。

研究员做「买哪个好」的对比分析时，把关键数据（如各供应商价格/评分）交给
make_chart，由它在沙箱里跑 Python 画图，PNG 保存到 /workspace/reports/charts/，
报告里用相对路径引用。
"""
from __future__ import annotations

import base64
import json

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from ..backends.sandbox_manager import SandboxManager

CHART_DIR = "/workspace/reports/charts"
_SCRIPT_PATH = f"{CHART_DIR}/_gen_chart.py"

# 固定脚本：读 base64 编码的 JSON 数据，画图存 PNG。
# 脚本本身不含任何动态插值，数据一律走 argv 的 base64，避免引号/编码问题。
_CHART_SCRIPT = r'''import sys, base64, json, os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# 中文字体（沙箱已装 Noto Sans CJK），否则中文标签会渲染成方块
plt.rcParams["font.sans-serif"] = ["Noto Sans CJK SC", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

d = json.loads(base64.b64decode(sys.argv[1]).decode())
labels, values, kind = d["labels"], d["values"], d["chart_type"]
plt.figure(figsize=(7, 4))
if kind == "bar":
    plt.bar(labels, values)
elif kind == "line":
    plt.plot(labels, values, marker="o")
elif kind == "pie":
    plt.pie(values, labels=labels, autopct="%1.1f%%")
else:
    raise ValueError("unsupported chart_type: " + kind)
if d.get("title"):
    plt.title(d["title"])
if d.get("xlabel"):
    plt.xlabel(d["xlabel"])
if d.get("ylabel"):
    plt.ylabel(d["ylabel"])
plt.tight_layout()
os.makedirs("/workspace/reports/charts", exist_ok=True)
plt.savefig(os.path.join("/workspace/reports/charts", d["filename"]))
print("saved: " + d["filename"])
'''


class _ChartArgs(BaseModel):
    chart_type: str = Field(description="图表类型：bar（柱状图）/ line（折线图）/ pie（饼图）")
    labels: list[str] = Field(description="每个数据点的名称，如供应商名或物料名")
    values: list[float] = Field(description="与 labels 一一对应的数值，如价格或评分")
    filename: str = Field(description="输出的 PNG 文件名，如 price_compare.png")
    title: str = Field(default="", description="图表标题（可选）")
    xlabel: str = Field(default="", description="X 轴标签（可选）")
    ylabel: str = Field(default="", description="Y 轴标签（可选）")


def build_make_chart_tool(
    sandbox_manager: SandboxManager, user_id: str
) -> StructuredTool:
    """构造 make_chart 工具（闭包捕获 sandbox_manager）。"""

    def _make_chart(
        chart_type: str,
        labels: list[str],
        values: list[float],
        filename: str,
        title: str = "",
        xlabel: str = "",
        ylabel: str = "",
    ) -> str:
        if not filename.endswith(".png"):
            filename += ".png"
        sandbox = sandbox_manager.get_sandbox(user_id)
        # 幂等上传固定脚本
        sandbox.upload_files([(_SCRIPT_PATH, _CHART_SCRIPT.encode("utf-8"))])
        payload = json.dumps(
            {
                "chart_type": chart_type,
                "labels": labels,
                "values": values,
                "filename": filename,
                "title": title,
                "xlabel": xlabel,
                "ylabel": ylabel,
            },
            ensure_ascii=False,
        )
        data = base64.b64encode(payload.encode("utf-8")).decode()
        resp = sandbox.execute(f"python {_SCRIPT_PATH} {data}")
        if resp.exit_code != 0:
            return f"[画图失败] {resp.output}"
        ref = f"![{title or filename}](charts/{filename})"
        return f"图表已保存到 {CHART_DIR}/{filename}。在报告里用这一行引用：{ref}"

    return StructuredTool.from_function(
        name="make_chart",
        description=(
            "用 matplotlib 在沙箱里生成一张 PNG 图表（柱状图/折线图/饼图）。"
            "做价格、评分等对比分析时，把数据交给它画图，再用返回的引用行插入报告。"
        ),
        func=_make_chart,
        args_schema=_ChartArgs,
        infer_schema=False,
    )
