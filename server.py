from fastapi import FastAPI, Request
import uvicorn
import os
from mcp.server.fastmcp import FastMCP

# 支持的健康数据类型
HEALTH_TYPES = [
    "heartRate", "restingHeartRate", "stepCount",
    "distanceWalkingRunning", "activeEnergyBurned",
    "oxygenSaturation", "bodyMass", "bodyFatPercentage",
    "respiratoryRate", "bloodPressureSystolic", "bloodPressureDiastolic",
]

latest_data = {t: {"value": None, "timestamp": None} for t in HEALTH_TYPES}

# 创建 FastAPI 应用（负责接收手机上传的健康数据）
app = FastAPI()

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

# 创建 MCP 服务（负责把数据交给 kelivo）
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

# 把 MCP 的 Streamable HTTP 应用挂载到 FastAPI 的 /mcp 路径
app.mount("/mcp", mcp.http_app())

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
