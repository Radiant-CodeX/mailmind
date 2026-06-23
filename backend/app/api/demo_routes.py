"""
Demo login endpoint — one click logs in as the pre-seeded demo account.

GET /api/demo/login  → HTML landing page with "Enter Demo" button
POST /api/demo/login → sets mm_session cookie + redirects to frontend dashboard
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from app.api.deps import _set_session_cookie
from app.config.settings import settings
from app.db.base import get_session
from app.db.models import OAuthAccount
from app.services.session_service import DBSessionBackend, SessionService

router = APIRouter(prefix="/api/demo", tags=["demo"])

DEMO_ACCOUNT_EMAIL = "demo@mailmind.app"


@router.get("/login", response_class=HTMLResponse)
async def demo_login_page():
    """Landing page — clicking the button POSTs to /api/demo/login."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>MailMind Demo</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            }
            .card {
                background: white;
                border-radius: 12px;
                padding: 48px;
                text-align: center;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                max-width: 400px;
                width: 90%;
            }
            h1 { font-size: 28px; margin-bottom: 12px; color: #1a1a1a; }
            p  { color: #666; margin-bottom: 28px; line-height: 1.6; }
            form { margin: 0; }
            button {
                background: #667eea;
                color: white;
                border: none;
                padding: 14px 32px;
                border-radius: 8px;
                font-size: 16px;
                font-weight: 600;
                cursor: pointer;
                width: 100%;
                transition: background 0.2s;
            }
            button:hover { background: #5568d3; }
            .chips {
                display: flex;
                flex-wrap: wrap;
                gap: 8px;
                justify-content: center;
                margin-top: 24px;
            }
            .chip {
                background: #f0f4ff;
                color: #4f46e5;
                font-size: 12px;
                padding: 4px 10px;
                border-radius: 99px;
            }
        </style>
    </head>
    <body>
        <div class="card">
            <h1>&#128231; MailMind Demo</h1>
            <p>Pre-loaded with 10 realistic emails, five-axis triage scores, Tone DNA, and draft generation ready to explore.</p>
            <form method="POST" action="/api/demo/login">
                <button type="submit">Enter Demo</button>
            </form>
            <div class="chips">
                <span class="chip">&#10003; Triage scoring</span>
                <span class="chip">&#10003; Tone DNA drafts</span>
                <span class="chip">&#10003; Commitments</span>
                <span class="chip">&#10003; Calendar detection</span>
            </div>
        </div>
    </body>
    </html>
    """


@router.post("/login")
async def demo_login():
    """Create session, set HttpOnly cookie, redirect to frontend dashboard."""

    frontend = settings.frontend_origin or "http://localhost:3000"

    with get_session() as session:
        if session is None:
            raise HTTPException(status_code=503, detail="Database not configured.")

        try:
            oauth = session.query(OAuthAccount).filter(
                OAuthAccount.account_email == DEMO_ACCOUNT_EMAIL
            ).first()

            if not oauth:
                raise HTTPException(
                    status_code=404,
                    detail=f"Demo account '{DEMO_ACCOUNT_EMAIL}' not found. "
                           "Run: python scripts/seed_demo_account.py --db <DATABASE_URL>",
                )

            session_svc = SessionService(DBSessionBackend(session))
            token = session_svc.create_session(str(oauth.user_id))
            session.commit()

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    response = RedirectResponse(url=f"{frontend}/dashboard", status_code=303)
    # Clear any existing auth cookies first so the real account doesn't
    # override the demo session via mm_quick auto-renewal.
    response.delete_cookie("mm_session", path="/")
    response.delete_cookie("mm_quick", path="/")
    _set_session_cookie(response, token, max_age=settings.session_ttl_seconds)
    return response
