import string
import random
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse, FileResponse
from pydantic import BaseModel, HttpUrl
from sqlalchemy.orm import Session
from typing import Annotated

from app.database import engine, get_db, Base
from app.models import URL

# ---------------------------------------------------------------------------
# Create all tables on startup
# ---------------------------------------------------------------------------
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="URL Shortener",
    description="A production-ready URL shortening service",
    version="1.0.0",
)

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


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/", response_class=FileResponse)
def read_root():
    """Serve the frontend UI."""
    return FileResponse("app/static/index.html")


@app.post("/shorten", response_model=ShortenResponse, status_code=201, responses={500: {"description": "Could not generate a unique short code"}})
def shorten_url(payload: ShortenRequest, request: Request, db: Annotated[Session, Depends(get_db)]):
    """Shorten a URL — generates a unique short code and stores it."""

    # Generate a unique short code (retry on collision)
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
def redirect_to_url(short_code: str, db: Annotated[Session, Depends(get_db)]):
    """Redirect to the original URL and increment the click counter."""

    url_entry = db.query(URL).filter(URL.short_code == short_code).first()
    if not url_entry:
        raise HTTPException(status_code=404, detail="Short URL not found")

    url_entry.clicks += 1
    db.commit()

    return RedirectResponse(url=url_entry.original_url, status_code=307)
