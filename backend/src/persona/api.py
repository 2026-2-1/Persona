import re
from collections.abc import Callable
from pathlib import Path
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DatabaseSession
from sqlalchemy.orm import selectinload

from persona.config import Settings, get_settings
from persona.db import get_db
from persona.models import Session, utc_now
from persona.schemas import CreateSession, SessionDetail, SessionSummary

FIXTURE_HTML = """<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><title>Persona 시험 상품</title>
<style>body{font:18px system-ui;max-width:720px;margin:80px auto;padding:24px;
background:#f4f6fa;color:#243049}button{font:inherit;padding:14px 22px;
background:#2458cc;color:white;border:0;border-radius:8px;cursor:pointer}
article{background:white;padding:32px;border-radius:16px}small{color:#5b6475}
#product-info{padding:20px;background:#eef4ff;margin-top:20px}</style></head>
<body><article><small>Persona · 개발용 가상 상품</small><h1>데일리 러닝화</h1>
<p>가벼운 러닝을 위한 시험 상품입니다.</p><p>가격: 59,000원</p>
<button id="show-info" aria-expanded="false" aria-controls="product-info"
onclick="document.getElementById('product-info').hidden=false;
this.setAttribute('aria-expanded','true')">상품 상세 정보 보기</button>
<div id="product-info" hidden><h2>상품 상세 정보</h2><p>가격: 59,000원</p>
<p>사이즈: 230~280mm (5mm 단위)</p><p>용도: 도심 조깅과 일상 러닝</p>
<p>소재: 통기성 메시 · 색상: 네이비</p><p>젖은 천으로 닦아 주세요.</p>
</div></article><p><small>실제 상품·판매·결제 기능이 없는 로컬 시험 페이지입니다.</small>
</p></body></html>"""


def get_publisher() -> Callable[[str], None]:
    from persona.worker import publish_session

    return publish_session


def detail(record: Session) -> SessionDetail:
    return SessionDetail.model_validate(record).model_copy(
        update={"steps_count": len(record.steps)}
    )


def find_session(db: DatabaseSession, session_id: UUID) -> Session:
    record = db.scalar(
        select(Session).options(selectinload(Session.steps)).where(Session.id == str(session_id))
    )
    if record is None:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
    return record


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or get_settings()
    app = FastAPI(title="Persona local development API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.allowed_cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Idempotency-Key"],
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "persona-api", "model_provider": config.model_provider}

    @app.get("/fixtures/shop", response_class=HTMLResponse)
    def shop() -> str:
        return FIXTURE_HTML

    @app.get("/sessions", response_model=list[SessionSummary])
    def list_sessions(db: DatabaseSession = Depends(get_db)) -> list[SessionSummary]:
        records = db.scalars(
            select(Session)
            .options(selectinload(Session.steps))
            .order_by(Session.created_at.desc(), Session.id.desc())
            .limit(100)
        )
        return [SessionSummary.model_validate(detail(record)) for record in records]

    @app.post("/sessions", response_model=SessionDetail, status_code=202)
    def create_session(
        payload: CreateSession,
        idempotency_key: str | None = Header(default=None),
        db: DatabaseSession = Depends(get_db),
        publish: Callable[[str], None] = Depends(get_publisher),
    ) -> SessionDetail:
        if idempotency_key is not None and not 1 <= len(idempotency_key) <= 128:
            raise HTTPException(status_code=422, detail="Idempotency-Key 길이는 1~128자입니다.")

        def reuse(record: Session) -> SessionDetail:
            if record.persona_name != payload.persona_name or record.task_id != payload.task_id:
                raise HTTPException(
                    status_code=409, detail="같은 키로 다른 요청을 보낼 수 없습니다."
                )
            return detail(record)

        if idempotency_key is not None:
            existing = db.scalar(select(Session).where(Session.idempotency_key == idempotency_key))
            if existing:
                return reuse(existing)
        record = Session(**payload.model_dump(), idempotency_key=idempotency_key)
        db.add(record)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            existing = (
                db.scalar(select(Session).where(Session.idempotency_key == idempotency_key))
                if idempotency_key is not None
                else None
            )
            if existing is None:
                raise
            return reuse(existing)
        db.refresh(record)
        try:
            publish(record.id)
        except Exception as exc:
            db.execute(
                update(Session)
                .where(Session.id == record.id, Session.status == "queued")
                .values(
                    status="technical_error",
                    error="작업 큐 연결 실패. Redis와 워커 상태를 확인해 주세요.",
                    finished_at=utc_now(),
                )
            )
            db.commit()
            raise HTTPException(
                status_code=503,
                detail={"message": "작업 큐에 전송하지 못했습니다.", "session_id": record.id},
            ) from exc
        return detail(record)

    @app.get("/sessions/{session_id}", response_model=SessionDetail)
    def get_session(session_id: UUID, db: DatabaseSession = Depends(get_db)) -> SessionDetail:
        return detail(find_session(db, session_id))

    @app.post("/sessions/{session_id}/cancel", response_model=SessionDetail)
    def cancel_session(session_id: UUID, db: DatabaseSession = Depends(get_db)) -> SessionDetail:
        find_session(db, session_id)
        db.execute(
            update(Session)
            .where(Session.id == str(session_id), Session.status.in_(["queued", "running"]))
            .values(status="cancelled", finished_at=utc_now())
        )
        db.commit()
        db.expire_all()
        return detail(find_session(db, session_id))

    @app.get("/artifacts/{session_id}/{filename}")
    def artifact(session_id: UUID, filename: str) -> FileResponse:
        if not re.fullmatch(r"[1-9][0-9]*-(before|after)\.png", filename):
            raise HTTPException(status_code=404, detail="화면 기록을 찾을 수 없습니다.")
        root = config.artifact_dir.resolve()
        path: Path = (root / str(session_id) / filename).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise HTTPException(status_code=404, detail="화면 기록을 찾을 수 없습니다.")
        return FileResponse(path, media_type="image/png")

    return app


app = create_app()
