import os
import logging
from datetime import datetime
from fastapi import FastAPI, Request
from mcp.server.fastmcp import FastMCP

logging.basicConfig(level=logging.INFO)

# 存储最新健康数据的容器
latest_health_data = {
    "timestamp": None,
    "data": {}
}

app = FastAPI()
mcp = FastMCP("heartbeat-mcp")

# ---------- 原有的心跳工具 ----------
@mcp.tool()
def heartbeat() -> str:
    """返回心跳信号"""
    return "alive"

# ---------- 健康数据工具（给 Kelivo 调用） ----------
@mcp.tool()
def get_latest_health_data() -> dict:
    """获取最新上传的健康数据"""
    if latest_health_data["timestamp"] is None:
        return {"message": "暂无数据"}
    return latest_health_data

# ---------- MCP 传输挂载 ----------
try:
    app.mount("/mcp/stream", mcp.streamable_http_app())
    logging.info("Streamable HTTP transport mounted at /mcp/stream")
except Exception as e:
    logging.error(f"Failed to mount Streamable HTTP: {e}")

try:
    app.mount("/mcp/sse", mcp.sse_app())
    logging.info("SSE transport mounted at /mcp/sse")
except Exception as e:
    logging.error(f"Failed to mount SSE: {e}")

# ---------- 健康数据接收接口（供快捷指令 POST） ----------
@app.post("/health-data")
async def receive_health_data(request: Request):
    body = await request.json()
    latest_health_data["timestamp"] = datetime.now().isoformat()
    latest_health_data["data"] = body
    logging.info(f"收到健康数据: {body}")
    return {"status": "ok"}

# 健康检查路由
@app.get("/")
async def root():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
