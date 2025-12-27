"""
Main FastAPI application.

Enterprise Search & RAG API with:
- User authentication
- Two-factor authentication
- Password reset
- Session management
- External service connectors (Slack, Google Drive, etc.)
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.auth_api import router as auth_router
from api.connector_api import router as connector_router

# Create FastAPI app
app = FastAPI(
    title="Enterprise Search & RAG API",
    description="Authentication and connector system for enterprise search with RAG",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production: specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router)
app.include_router(connector_router)


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "authentication-api"}


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Enterprise Search & RAG API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "features": [
            "Authentication (JWT, 2FA, OAuth)",
            "Connectors (Slack, Google Drive, Notion, etc.)",
            "RAG Search (Coming soon)"
        ]
    }


# Exception handlers
@app.exception_handler(Exception)
async def generic_exception_handler(request, exc):
    """Handle unexpected exceptions."""
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "message": "An unexpected error occurred",
            "detail": str(exc) if app.debug else None
        }
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
