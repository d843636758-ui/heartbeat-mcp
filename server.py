from fastapi import FastAPI, Request
import uvicorn
import os
from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.routing import Mount

# 健康数据类型
HEALTH_TYPES = [
    "heartRate", "restingHeartRate", "stepCount",
    "distanceWalkingRunning", "activeEnergyBurned",
    "oxygenSaturation", "bodyMass", "bodyFatPercentage",
    "respiratoryRate", "bloodPressureSystolic", "bloodPressureDiastolic",
]

latest_data = {t: {"value": None, "timestamp": None} for t in HEALTH_TYPES}

# 创建 FastAPI 应用，负责 HTTP API
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

# 创建 MCP 服务
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

# ---- 关键：手动构建 ASGI 应用，兼容所有版本 ----
# 获取 MCP 内部的 SSE/Streamable HTTP 应用（不调用 http_app）
# 直接使用 mcp 对象底层的 Starlette 挂载
mcp_asgi = mcp._mcp_server  # 获取底层 Server 实例，然后创建传输
# 但由于底层方式复杂，更稳妥的是用 mcp.run() 但配置为 ASGI 模式
# 这里用最简单的方法：重启用 mcp.streamable_http_app() 如果存在，否则回退
try:
    # 新版 mcp 可能用 streamable_http_app
    mcp_http = mcp.streamable_http_app()
except AttributeError:
    try:
        # 旧版用 http_app
        mcp_http = mcp.http_app()
    except AttributeError:
        # 如果都没有，手动创建 SseServerTransport（仅需 Starlette）
        from mcp.server.transport.sse import SseServerTransport
        from starlette.requests import Request as StarletteRequest

        transport = SseServerTransport("/messages")
        async def handle_sse(request: StarletteRequest):
            return await transport.handle_sse(request)

        async def handle_messages(request: StarletteRequest):
            return await transport.handle_messages(request)

        # 构造一个简单的 Starlette 路由
        mcp_http = Starlette(routes=[
            Mount("/sse", handle_sse),
            Mount("/messages", handle_messages),
        ])

# 将 MCP 的 HTTP 服务挂载到 FastAPI 的 /mcp 路径
app.mount("/mcp", 
mcp.streamable_http_app())
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
