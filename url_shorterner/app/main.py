import secrets
import sqlite3
import string
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, HttpUrl

DB_PATH = "urls.db"
BASE62 = string.ascii_letters + string.digits
CODE_LEN = 6

app = FastAPI(title="URL Shortener")


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


with get_db() as _conn:
    _conn.execute("""
        CREATE TABLE IF NOT EXISTS urls (
            short_code      TEXT PRIMARY KEY,
            long_url        TEXT NOT NULL,
            expiration_time TEXT,
            creation_time   TEXT NOT NULL
        )
        """)


class ShortenRequest(BaseModel):
    originalURL: HttpUrl
    alias: Optional[str] = None
    expirationTime: Optional[datetime] = None


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def random_code() -> str:
    return "".join(secrets.choice(BASE62) for _ in range(CODE_LEN))


@app.post("/urls", status_code=201)
def shorten(body: ShortenRequest, request: Request):
    expiration = body.expirationTime
    if expiration is not None:
        if expiration.tzinfo is None:
            expiration = expiration.replace(tzinfo=timezone.utc)
        if expiration <= utcnow():
            raise HTTPException(400, "expirationTime must be in the future")

    if body.alias is not None and not body.alias.isalnum():
        raise HTTPException(400, "alias must be alphanumeric")

    row = (
        body.alias,
        str(body.originalURL),
        expiration.isoformat() if expiration else None,
        utcnow().isoformat(),
    )
    sql = "INSERT INTO urls VALUES (?, ?, ?, ?)"

    with get_db() as conn:
        if body.alias:
            try:
                conn.execute(sql, row)
            except sqlite3.IntegrityError:
                raise HTTPException(409, "alias already taken")
            code = body.alias
        else:
            # Retry on the rare random-code collision.
            for _ in range(5):
                code = random_code()
                try:
                    conn.execute(sql, (code, *row[1:]))
                    break
                except sqlite3.IntegrityError:
                    continue
            else:
                raise HTTPException(500, "could not generate unique code")

    return {"shortUrl": f"{str(request.base_url)}{code}"}


@app.get("/{short_code}")
def redirect(short_code: str):
    with get_db() as conn:
        row = conn.execute(
            "SELECT long_url, expiration_time FROM urls WHERE short_code = ?",
            (short_code,),
        ).fetchone()

    if row is None:
        raise HTTPException(404, "short url not found")
    if (
        row["expiration_time"]
        and datetime.fromisoformat(row["expiration_time"]) <= utcnow()
    ):
        raise HTTPException(410, "short url expired")

    # 302 (temporary) so every hit reaches the server for analytics/logs.
    return RedirectResponse(row["long_url"], status_code=302)
