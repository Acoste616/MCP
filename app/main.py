from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status, Depends # Added status and Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware # Added for compression
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy.exc import IntegrityError # Added for DB integrity errors
from starlette.responses import JSONResponse # Added for custom JSON responses
from sqlalchemy.ext.asyncio import AsyncSession # For DB session in health check
from app.api.deps import get_session # For DB session in health check
from sqlmodel import select # For health check DB query
from starlette.staticfiles import StaticFiles # Added

from app.api import auth, products, users, orders
from app.routers import mcp_routes # Added for MCP
from app.core.config import settings
# from app.core.database import init_db # Keep init_db for potential initial data seeding
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.middleware.logging_middleware import LoggingMiddleware # Added

# Rate Limiter
limiter = Limiter(key_func=get_remote_address, default_limits=[settings.DEFAULT_RATE_LIMIT])

# Lifespan for startup and shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize database, etc.
    # print("Starting up...")
    # await init_db() # You might call this if you have initial data to seed or specific checks
    yield
    # Shutdown: Clean up resources, etc.
    # print("Shutting down...")

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    version="0.1.0",
    lifespan=lifespan,
)

# Apply Rate Limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Apply GZip compression middleware
app.add_middleware(GZipMiddleware, minimum_size=1000) # Compress responses > 1KB

# Apply Logging Middleware (must be among the first for full coverage)
app.add_middleware(LoggingMiddleware)

# Apply Security Headers Middleware
app.add_middleware(SecurityHeadersMiddleware)

# Set up CORS
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin).strip() for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Mount static files directory (for serving uploaded images)
# This should be defined *before* any conflicting broad routes if /static/ is also an API prefix
import os
if not os.path.exists(settings.UPLOAD_DIRECTORY):
    os.makedirs(settings.UPLOAD_DIRECTORY)
app.mount("/static", StaticFiles(directory=settings.UPLOAD_DIRECTORY), name="static")

# Exception handler for IntegrityError (e.g. unique constraint violations)
@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError):
    # Log the error for debugging purposes
    # import logging
    # logging.getLogger(__name__).error(f"IntegrityError: {exc.orig}", exc_info=True)
    
    detail_message = "A database integrity error occurred. This could be due to a duplicate value or a violation of a data constraint."
    # More specific check for PostgreSQL unique violation ( psycopg2.errors.UniqueViolation / asyncpg.exceptions.UniqueViolationError)
    # The original exception is wrapped, check its type or code
    if hasattr(exc.orig, 'sqlstate') and exc.orig.sqlstate == '23505': # For asyncpg/PostgreSQL
        # Could try to parse exc.detail to get constraint name for better message if needed
        detail_message = "The value for a unique field already exists. Please use a different value."

    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT, # 409 Conflict for duplicates
        content={"detail": detail_message},
    )

# API routes - Apply rate limiting to these routes if desired, or globally as above
app.include_router(auth.router, prefix=f"{settings.API_V1_STR}/auth", tags=["Authentication"])
app.include_router(users.router, prefix=f"{settings.API_V1_STR}/users", tags=["Users"])
app.include_router(products.router, prefix=f"{settings.API_V1_STR}/products", tags=["Products"])
app.include_router(orders.router, prefix=f"{settings.API_V1_STR}/orders", tags=["Orders"])
app.include_router(mcp_routes.router) # MCP routes are already prefixed with /mcp
# Add other routers here (e.g., orders) as they are created

@app.get(f"{settings.API_V1_STR}/health", tags=["Health Check"])
@limiter.exempt # Exempt health check from rate limiting if desired
async def health_check(dbsession: AsyncSession = Depends(get_session)):
    """
    Simple health check endpoint, including database connectivity.
    """
    db_status = "ok"
    db_error_detail = None # Renamed from db_error to avoid conflict with any general error var
    try:
        # Try a simple query to check DB connection
        await dbsession.execute(select(1)) # type: ignore
    except Exception as e:
        db_status = "error"
        db_error_detail = str(e)
        # Log the specific DB connection error
        # logger.error(f"Database health check failed: {e}", exc_info=True)
    
    if db_status == "error":
            return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"api_status": "error", "database_status": db_status, "database_error": db_error_detail}
        )
    return {"api_status": "ok", "database_status": db_status}

# If you want a root path for the API docs redirect or basic info:
@app.get("/", include_in_schema=False)
@limiter.exempt # Exempt root path from rate limiting
async def root():
    return {
        "message": f"Welcome to {settings.PROJECT_NAME}",
        "docs_url": "/docs",
        "redoc_url": "/redoc"
    } 