from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from database.models import ApprovalQueue, CollectionLog, DeliveryLog, Opportunity
from database.session import get_db_session


router = APIRouter(prefix="/admin", tags=["admin"])
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


@router.get("/", response_class=HTMLResponse)
def dashboard(
    request: Request,
    session: Session = Depends(get_db_session),
) -> HTMLResponse:
    approval_service = request.app.state.approval_service
    digest_service = request.app.state.digest_service

    pending_count = session.query(func.count(Opportunity.id)).filter(Opportunity.status == "pending").scalar() or 0
    approved_count = session.query(func.count(Opportunity.id)).filter(Opportunity.status == "approved").scalar() or 0
    sent_count = session.query(func.count(Opportunity.id)).filter(Opportunity.status == "sent").scalar() or 0
    rejected_count = session.query(func.count(Opportunity.id)).filter(Opportunity.status == "rejected").scalar() or 0

    review_items = approval_service.get_pending_items(session)
    digest_preview = digest_service.build_digest(session)
    collection_logs = session.query(CollectionLog).order_by(CollectionLog.created_at.desc()).limit(10).all()
    delivery_logs = session.query(DeliveryLog).order_by(DeliveryLog.delivered_at.desc()).limit(10).all()

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "counts": {
                "pending": pending_count,
                "approved": approved_count,
                "sent": sent_count,
                "rejected": rejected_count,
            },
            "review_items": review_items,
            "digest_preview": digest_preview,
            "collection_logs": collection_logs,
            "delivery_logs": delivery_logs,
            "operator_name": request.app.state.settings.admin_operator_name,
        },
    )


@router.post("/collect")
def run_collection(request: Request) -> RedirectResponse:
    with request.app.state.db.session_scope() as session:
        request.app.state.collection_service.collect_all(session)
    return RedirectResponse(url="/admin/", status_code=303)


@router.post("/opportunities/{opportunity_id}/approve")
def approve_item(
    request: Request,
    opportunity_id: int,
    note: str = Form(default=""),
) -> RedirectResponse:
    with request.app.state.db.session_scope() as session:
        request.app.state.approval_service.update_status(
            session,
            opportunity_id=opportunity_id,
            status="approved",
            reviewed_by=request.app.state.settings.admin_operator_name,
            note=note or None,
        )
    return RedirectResponse(url="/admin/", status_code=303)


@router.post("/opportunities/{opportunity_id}/reject")
def reject_item(
    request: Request,
    opportunity_id: int,
    note: str = Form(default=""),
) -> RedirectResponse:
    with request.app.state.db.session_scope() as session:
        request.app.state.approval_service.update_status(
            session,
            opportunity_id=opportunity_id,
            status="rejected",
            reviewed_by=request.app.state.settings.admin_operator_name,
            note=note or None,
        )
    return RedirectResponse(url="/admin/", status_code=303)


@router.get("/digest", response_class=HTMLResponse)
def digest_preview_page(
    request: Request,
    session: Session = Depends(get_db_session),
) -> HTMLResponse:
    payload = request.app.state.digest_service.build_digest(session)
    return templates.TemplateResponse(
        request,
        "digest_preview.html",
        {
            "payload": payload,
        },
    )


@router.post("/digest/send")
def send_digest(request: Request) -> RedirectResponse:
    with request.app.state.db.session_scope() as session:
        request.app.state.digest_service.send_digest(session)
    return RedirectResponse(url="/admin/", status_code=303)
