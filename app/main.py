import os
import string
import random
import redis
from fastapi import FastAPI, Depends, HTTPException, Request, BackgroundTasks
from fastapi.responses import RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, HttpUrl
from sqlalchemy.orm import Session
from typing import Annotated

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.database import engine, get_db, SessionLocal, Base
from app.models import URL

# ---------------------------------------------------------------------------
# Redis & Rate Limiting Init
# ---------------------------------------------------------------------------
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
redis_client = redis.from_url(REDIS_URL, decode_responses=True)

limiter = Limiter(key_func=get_remote_address, storage_uri=REDIS_URL)

# ---------------------------------------------------------------------------
# Create all tables on startup
# ---------------------------------------------------------------------------
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="URL Shortener",
    description="A production-ready URL shortening service",
    version="1.0.0",
)

# Add Limiter handlers
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class ShortenRequest(BaseModel):
    url: HttpUrl

class ShortenResponse(BaseModel):
    short_url: str
    short_code: str
    original_url: str

class StatsResponse(BaseModel):
    original_url: str
    short_code: str
    clicks: int
    created_at: str

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _generate_short_code(length: int = 6) -> str:
    """Generate a random alphanumeric short code."""
    chars = string.ascii_letters + string.digits
    return "".join(random.choices(chars, k=length))

def increment_clicks_in_db(short_code: str):
    """Background task to increment clicks safely without holding request."""
    db = SessionLocal()
    try:
        url_entry = db.query(URL).filter(URL.short_code == short_code).first()
        if url_entry:
            url_entry.clicks += 1
            db.commit()
    finally:
        db.close()

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
def health_check():
    """Health check endpoint."""
    try:
        redis_status = redis_client.ping()
    except Exception:
        redis_status = False
    return {"status": "ok", "redis": redis_status}

@app.get("/", response_class=FileResponse)
def read_root():
    """Serve the frontend UI."""
    return FileResponse("app/static/index.html")

@app.post("/shorten", response_model=ShortenResponse, status_code=201, responses={500: {"description": "Could not generate a unique short code"}})
@limiter.limit("10/minute")
def shorten_url(request: Request, payload: ShortenRequest, db: Annotated[Session, Depends(get_db)]):
    """Shorten a URL — generates a unique short code and stores it."""
    for _ in range(10):
        code = _generate_short_code()
        if not db.query(URL).filter(URL.short_code == code).first():
            break
    else:
        raise HTTPException(status_code=500, detail="Could not generate a unique short code")

    url_entry = URL(original_url=str(payload.url), short_code=code)
    db.add(url_entry)
    db.commit()
    db.refresh(url_entry)

    base_url = str(request.base_url).rstrip("/")
    return ShortenResponse(
        short_url=f"{base_url}/{code}",
        short_code=code,
        original_url=url_entry.original_url,
    )

@app.get("/stats/{short_code}", response_model=StatsResponse, responses={404: {"description": "Short URL not found"}})
def get_stats(short_code: str, db: Annotated[Session, Depends(get_db)]):
    """Return click statistics for a given short code."""
    url_entry = db.query(URL).filter(URL.short_code == short_code).first()
    if not url_entry:
        raise HTTPException(status_code=404, detail="Short URL not found")

    return StatsResponse(
        original_url=url_entry.original_url,
        short_code=url_entry.short_code,
        clicks=url_entry.clicks,
        created_at=url_entry.created_at.isoformat(),
    )

@app.get("/{short_code}", responses={404: {"description": "Short URL not found"}})
def redirect_to_url(short_code: str, request: Request, background_tasks: BackgroundTasks, db: Annotated[Session, Depends(get_db)]):
    """Redirect to the original URL and use Redis caching + background click counting."""
    
    # 1. Try to get from Redis cache
    cache_key = f"url:{short_code}"
    try:
        cached_url = redis_client.get(cache_key)
    except Exception:
        # Fallback to DB if redis is down
        cached_url = None
    
    if cached_url:
        background_tasks.add_task(increment_clicks_in_db, short_code)
        return RedirectResponse(url=cached_url, status_code=307)

    # 2. Cache miss -> Query DB
    url_entry = db.query(URL).filter(URL.short_code == short_code).first()
    if not url_entry:
        raise HTTPException(status_code=404, detail="Short URL not found")

    # 3. Store in cache (expire after 24 hours = 86400 seconds)
    try:
        redis_client.setex(cache_key, 86400, url_entry.original_url)
    except Exception:
        pass # Ignore redis errors if it goes down

    url_entry.clicks += 1
    db.commit()

    return RedirectResponse(url=url_entry.original_url, status_code=307)
