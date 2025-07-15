import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv, find_dotenv
from contextlib import asynccontextmanager

# 加载环境变量
load_dotenv(find_dotenv())

# 本地模块
from routes.paper_routes import router as paper_router
from routes.user_routes import router as user_router
from models.db import engine, Base


# ======================== lifespan 生命周期 ========================
@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    Base.metadata.create_all(bind=engine)
    print("[DB] 数据库初始化完成")
    yield
    # shutdown
    print("[DB] 数据库应用已关闭")


# ======================== 创建 FastAPI 实例 ========================
app = FastAPI(
    title="Essay",
    version="1.0",
    description="Your Paper Reading Assistant",
    lifespan=lifespan
)


# ======================== 中间件 & 路由 ========================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(paper_router,prefix="/api")
app.include_router(user_router,prefix="/api")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)

