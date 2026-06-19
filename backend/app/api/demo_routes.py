"""
Demo login endpoint — allows judges/stakeholders to instantly access demo account.

Usage:
  GET /api/demo/login → returns HTML with auto-login redirect
  POST /api/demo/login → returns session token

Enable only in non-production or with DEMO_MODE=true env var.
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from app.db.base import get_session
from app.db.models import OAuthAccount
from app.services.session_service import DBSessionBackend, SessionService

router = APIRouter(prefix="/api/demo", tags=["demo"])

DEMO_ACCOUNT_EMAIL = "demo@mailmind.app"


@router.get("/login", response_class=HTMLResponse)
async def demo_login_html():
    """Return HTML page with one-click demo login."""

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>MailMind Demo Login</title>
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            }}
            .container {{
                background: white;
                border-radius: 12px;
                padding: 48px;
                text-align: center;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                max-width: 400px;
            }}
            h1 {{
                font-size: 32px;
                margin-bottom: 16px;
                color: #1a1a1a;
            }}
            p {{
                color: #666;
                margin-bottom: 32px;
                line-height: 1.6;
            }}
            .button {{
                background: #667eea;
                color: white;
                border: none;
                padding: 14px 32px;
                border-radius: 8px;
                font-size: 16px;
                font-weight: 600;
                cursor: pointer;
                transition: background 0.3s;
                width: 100%;
            }}
            .button:hover {{
                background: #5568d3;
            }}
            .details {{
                background: #f5f5f5;
                padding: 16px;
                border-radius: 8px;
                margin-top: 32px;
                text-align: left;
                font-size: 13px;
                color: #666;
            }}
            .details p {{
                margin: 8px 0;
            }}
            code {{
                background: white;
                padding: 2px 6px;
                border-radius: 4px;
                font-family: monospace;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>📧 MailMind Demo</h1>
            <p>Click below to access the demo account with pre-loaded emails, triage scores, and all features ready to explore.</p>

            <button class="button" onclick="loginDemo()">Enter Demo</button>

            <div class="details">
                <p><strong>Demo Account:</strong></p>
                <p>Email: <code>{DEMO_ACCOUNT_EMAIL}</code></p>
                <p>Pre-loaded with 10 realistic emails across all priority levels</p>
                <p>✓ Five-axis triage scoring</p>
                <p>✓ Draft generation with Tone DNA</p>
                <p>✓ Commitment extraction</p>
                <p>✓ Calendar conflict detection</p>
            </div>
        </div>

        <script>
            async function loginDemo() {{
                try {{
                    const response = await fetch('/api/demo/login', {{ method: 'POST' }});
                    const data = await response.json();

                    if (data.session_token) {{
                        // Set session cookie
                        document.cookie = `mm_session=${{data.session_token}}; path=/; secure; samesite=strict`;
                        // Redirect to dashboard
                        window.location.href = '/dashboard';
                    }} else {{
                        alert('Login failed: ' + (data.detail || 'Unknown error'));
                    }}
                }} catch (e) {{
                    alert('Error: ' + e.message);
                }}
            }}
        </script>
    </body>
    </html>
    """


@router.post("/login")
async def demo_login():
    """Create and return demo session token."""

    with get_session() as session:
        if session is None:
            raise HTTPException(status_code=503, detail="Database not configured.")

        try:
            oauth = session.query(OAuthAccount).filter(
                OAuthAccount.email == DEMO_ACCOUNT_EMAIL
            ).first()

            if not oauth:
                raise HTTPException(
                    status_code=404,
                    detail=f"Demo account '{DEMO_ACCOUNT_EMAIL}' not found. Run: python scripts/seed_demo_account.py --db <DATABASE_URL>"
                )

            session_svc = SessionService(DBSessionBackend(session))
            token = session_svc.create_session(str(oauth.user_id))

            return {
                "session_token": token,
                "user_id": str(oauth.user_id),
                "email": DEMO_ACCOUNT_EMAIL,
                "message": "Demo login successful. Redirecting to dashboard...",
            }

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
