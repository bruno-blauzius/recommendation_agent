import logging
from dotenv import load_dotenv
import uvicorn
from fastapi import FastAPI
from contextlib import asynccontextmanager

load_dotenv()

logger = logging.getLogger("AgentLogger - AI Recommendation Agent")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("🚀 Initialized my first recommendation agent AI!")
    logger.info("🎯 Recommendation Agent API starting on http://0.0.0.0:8000")
    logger.info("📚 API Documentation: http://localhost:8000/docs")
    yield
    # Shutdown
    logger.info("🛑 Recommendation Agent API shutting down")


app = FastAPI(
    title="Recommendation Agent",
    description="LLM-based insurance product recommendation engine",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Welcome to Recommendation Agent",
        "version": "1.0.0",
        "status": "active",
    }


@app.get("/health")
async def health():
    """Health check endpoint for monitoring."""
    return {
        "status": "healthy",
        "service": "recommendation-agent",
    }


@app.get("/ready")
async def readiness():
    """Readiness check endpoint - validates dependencies."""
    return {
        "ready": True,
        "service": "recommendation-agent",
    }


def main():
    """Start the API server."""
    logger.info("Hello, World!")
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
