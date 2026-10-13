"""应用入口：创建 FastAPI 实例，注册路由。"""

from fastapi import FastAPI

from app.api.documents import router as documents_router

app = FastAPI(title="Personal AI KB", version="0.1.0")

app.include_router(documents_router)


@app.get("/health")
def health_check():
    """健康检查：确认服务活着。"""
    return {"status": "ok", "app": "personal-ai-kb"}