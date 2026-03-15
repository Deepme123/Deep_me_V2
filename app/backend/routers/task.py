from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.backend.db.session import get_session
from app.backend.dependencies.auth import get_current_user
from app.backend.models.task import Task
from app.backend.models.user import User
from app.backend.schemas.task import TaskRecommendBySessionRequest
from app.backend.services.task_llm_service import (
    recommend_task_drafts_from_prompt,
    recommend_task_drafts_from_session_context,
)
from app.backend.services.task_recommend import (
    load_task_recommendation_context,
    persist_task_drafts,
)

router = APIRouter(prefix="/tasks", tags=["Tasks"])


@router.post("/", response_model=Task)
def create_task(
    task: Task,
    db: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    task.user_id = user.user_id
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.get("/", response_model=list[Task])
def get_all_tasks(
    db: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    stmt = select(Task).where(Task.user_id == user.user_id)
    return db.exec(stmt).all()


@router.get("/{task_id}", response_model=Task)
def get_task(
    task_id: UUID,
    db: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    task = db.get(Task, task_id)
    if not task or task.user_id != user.user_id:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.patch("/{task_id}", response_model=Task)
def update_task(
    task_id: UUID,
    updated: Task,
    db: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    task = db.get(Task, task_id)
    if not task or task.user_id != user.user_id:
        raise HTTPException(status_code=404, detail="Task not found")

    task.title = updated.title or task.title
    task.description = updated.description or task.description
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.patch("/{task_id}/complete", response_model=Task)
def complete_task(
    task_id: UUID,
    db: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    task = db.get(Task, task_id)
    if not task or task.user_id != user.user_id:
        raise HTTPException(status_code=404, detail="Task not found")

    task.is_completed = True
    task.completed_at = datetime.utcnow()
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.delete("/{task_id}")
def delete_task(
    task_id: UUID,
    db: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    task = db.get(Task, task_id)
    if not task or task.user_id != user.user_id:
        raise HTTPException(status_code=404, detail="Task not found")
    db.delete(task)
    db.commit()
    return {"ok": True}


@router.post("/gpt", response_model=list[Task])
def recommend_tasks_from_gpt(
    db: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    try:
        drafts = recommend_task_drafts_from_prompt()
        return persist_task_drafts(db, user_id=user.user_id, drafts=drafts)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/gpt/by-session", response_model=list[Task], summary="세션 기반 GPT 과제 추천")
def recommend_tasks_from_session(
    payload: TaskRecommendBySessionRequest,
    db: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    try:
        context = load_task_recommendation_context(
            db,
            user_id=user.user_id,
            session_id=payload.session_id,
            recent_steps_limit=payload.recent_steps_limit,
            max_history_chars=payload.max_history_chars,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Emotion session not found") from exc

    try:
        drafts = recommend_task_drafts_from_session_context(
            context=context,
            n=payload.n,
        )
        return persist_task_drafts(db, user_id=user.user_id, drafts=drafts)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
