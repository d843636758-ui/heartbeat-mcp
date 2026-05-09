from fastapi import FastAPI, Request
import uvicorn
import os
from mcp.server.fastmcp import FastMCP
from starlette.routing import Route
from starlette.responses import StreamingResponse
import json

# 健康数据类型
HEALTH_TYPES = [
    "heartRate", "restingHeartRate", "stepCount",
    "distanceWalkingRunning", "activeEnergyBurned",
    "oxygenSaturation", "bodyMass", "bodyFatPercentage",
    "respiratoryRate", "bloodPressureSystolic", "bloodPressureDiastolic",
]

latest_data = {t: {"value": None, "timestamp": None} for t in HEALTH_TYPES}

# FastAPI HTTP 部分
app = FastAPI()

@app.get("/")
def health_check():
    return {"status": "ok"}

@app.post("/health")
async def receive_health(request: Request):
    global latest_data
    data = await request.json()
    for entry in data.get("samples", []):
        tp = entry.get("type")
        val = entry.get("value")
        ts = entry.get("timestamp")
        if tp in latest_data:
            latest_data[tp] = {"value": val, "timestamp": ts}
    return {"status": "ok"}

# MCP 服务
mcp = FastMCP("AppleHealth")

@mcp.resource("health://{data_type}")
def get_health_data(data_type: str) -> str:
    if data_type not in latest_data:
        return f"不支持的类型。支持：{', '.join(HEALTH_TYPES)}"
    rec = latest_data[data_type]
    if rec["value"] is None:
        return f"{data_type} 暂无数据"
    return f"{data_type}: {rec['value']}（时间 {rec['timestamp']}）"

@mcp.resource("health://summary")
def get_summary() -> str:
    lines = ["📊 最新健康数据："]
    for tp in HEALTH_TYPES:
        rec = latest_data[tp]
        if rec["value"] is not None:
            lines.append(f"- {tp}: {rec['value']}（{rec['timestamp']}）")
    if len(lines) == 1:
        lines.append("暂无任何数据上传。")
    return "\n".join(lines)

# ---- 显式创建 SSE 端点，直接让 Kelivo 连接 ----
# 使用 mcp 内部的 SSE 传输工具
from mcp.server.transport.sse import SseServerTransport
from starlette.requests import Request as StarletteRequest

# 创建一个 SSE 传输实例，messages 路径设为 /mcp/messages
sse = SseServerTransport("/mcp/messages")

async def handle_sse(request: StarletteRequest):
    return await sse.handle_sse(request)

async def handle_messages(request: StarletteRequest):
    return await sse.handle_messages(request)

# 将两个路由直接注册到 FastAPI 应用上（绕过 http_app）
app.add_route("/mcp/sse", handle_sse, methods=["GET", "POST"])
app.add_route("/mcp/messages", handle_messages, methods=["POST"])

# 可选保留原挂载（不影响）
# app.mount("/mcp", mcp.http_app())

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
