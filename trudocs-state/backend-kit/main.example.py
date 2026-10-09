"""
backend/main.py for a state repo — this is the whole file.

Replace the BBMP tool with the state's own tools: one `make_router(...)` per tool, each
registered with the HealthBoard under its own service name.
"""
import os
from pathlib import Path

from backend.kit.app_factory import create_app
from backend.kit.pdf_cover import load_registry
from backend.kit.rate_limit import make_limiter
from backend.kit.service_health import HealthBoard
from backend.tools.bbmp_receipt.routes import SERVICE as BBMP, make_router as bbmp_router

ROOT = Path(__file__).resolve().parent.parent

limiter = make_limiter()                      # TRUST_PROXY_HOPS / RATE_LIMIT_STORAGE from env
board = HealthBoard()
board.register(BBMP, portal_name="BBMP tax portal", ping_url="https://bbmptax.karnataka.gov.in")

cover_cfg = ROOT / "covers" / "covers.json"   # the user supplies the PDFs + positions (SKILL.md §0)
covers = load_registry(cover_cfg) if cover_cfg.exists() else None

bbmp = bbmp_router(limiter, board, covers)

app = create_app(
    "TruDocs <State>",
    limiter=limiter,
    board=board,
    gates=[bbmp.gate],
    routers=[bbmp],
    frontend_dist=os.getenv("FRONTEND_DIST", str(ROOT / "frontend-v2" / "dist")),
)
