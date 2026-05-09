import os
import logging
from datetime import datetime
from fastapi import FastAPI, Request
from mcp.server.fastmcp import FastMCP

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

latest_health_data = {"timestamp": None, "data": {}}
app = FastAPI()
mcp = FastMCP("heartbeat-mcp")

# ---------- MCP 工具 ----------
@mcp.tool()
def heartbeat() -> str:
    """返回心跳信号"""
    return "alive"

@mcp.tool()
def get_latest_health_data() -> dict:
    """获取最新上传的健康数据"""
    if latest_health_data["timestamp"] is None:
        return {"message": "暂无数据"}
    return latest_health_data

# ---------- 健康数据接收接口 ----------
@app.post("/health-data")
async def receive_health_data(request: Request):
    body = await request.json()
    latest_health_data["timestamp"] = datetime.now().isoformat()
    latest_health_data["data"] = body
    logging.info(f"收到健康数据: {body}")
    return {"status": "ok"}

# ---------- 健康检查 / 调试路由 ----------
@app.get("/")
async def root():
    return {"status": "ok"}

@app.get("/debug-routes")
async def list_routes():
    routes = []
    for r in app.routes:
        info = {"path": r.path}
        if hasattr(r, "methods"):
            info["methods"] = r.methods
        else:
            info["type"] = "mount"
        routes.append(info)
    return {"routes": routes}

# ---------- 挂载 MCP 传输（注意尾部斜杠） ----------
try:
    stream_app = mcp.streamable_http_app()
    app.mount("/mcp/stream/", stream_app)
    logging.info("✅ Streamable HTTP mounted at /mcp/stream/")
except Exception as e:
    logging.error(f"❌ Failed to mount Streamable HTTP: {e}")
    raise

try:
    sse_app = mcp.sse_app()
    app.mount("/mcp/sse/", sse_app)
    logging.info("✅ SSE mounted at /mcp/sse/")
except Exception as e:
    logging.error(f"❌ Failed to mount SSE: {e}")
    raise

# ---------- 启动服务 ----------
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    logging.info(f"Starting server on 0.0.0.0:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
