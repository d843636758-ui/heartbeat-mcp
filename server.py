import os
import logging
from datetime import datetime
from fastapi import FastAPI, Request
from mcp.server.fastmcp import FastMCP

logging.basicConfig(level=logging.INFO)

latest_health_data = {
    "timestamp": None,
    "data": {}
}

app = FastAPI()
mcp = FastMCP("heartbeat-mcp")

@mcp.tool()
def heartbeat() -> str:
    return "alive"

@mcp.tool()
def get_latest_health_data() -> dict:
    if latest_health_data["timestamp"] is None:
        return {"message": "暂无数据"}
    return latest_health_data

# 看这里：路径都加了 /
try:
    app.mount("/mcp/stream/", mcp.streamable_http_app())
    logging.info("Streamable HTTP mounted at /mcp/stream/")
except Exception as e:
    logging.error(f"Failed to mount Streamable HTTP: {e}")

try:
    app.mount("/mcp/sse/", mcp.sse_app())
    logging.info("SSE mounted at /mcp/sse/")
except Exception as e:
    logging.error(f"Failed to mount SSE: {e}")

@app.post("/health-data")
async def receive_health_data(request: Request):
    body = await request.json()
    latest_health_data["timestamp"] = datetime.now().isoformat()
    latest_health_data["data"] = body
    logging.info(f"收到健康数据: {body}")
    return {"status": "ok"}

@app.get("/")
async def root():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
