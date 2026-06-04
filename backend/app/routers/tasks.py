from fastapi import APIRouter, HTTPException
from typing import List
from datetime import datetime, timedelta
import uuid

from app.models import TaskCreate, TaskResponse
from app.services.db import db
from app.services.calendar_service import check_calendar_conflict

router = APIRouter()

@router.get("/tasks", response_model=List[TaskResponse])
async def get_tasks():
    return db.get_tasks()

@router.post("/tasks", response_model=TaskResponse)
async def create_task(task_in: TaskCreate):
    due_date = task_in.due_date
    if not due_date:
        # Default due date to tomorrow EOD
        tomorrow = datetime.now() + timedelta(days=1)
        due_date = tomorrow.replace(hour=17, minute=0, second=0, microsecond=0).isoformat()
        
    new_task = {
        "id": str(uuid.uuid4())[:8],
        "title": task_in.title,
        "status": "pending",
        "due_date": due_date,
        "email_ref": task_in.email_ref or "unknown@company.com"
    }
    
    db.add_task(new_task)
    return new_task

@router.post("/tasks/sync", response_model=List[TaskResponse])
async def sync_tasks():
    return db.sync_all_tasks()

@router.get("/calendar/check")
async def check_conflict(target_time: str):
    if not target_time:
        raise HTTPException(status_code=400, detail="target_time query parameter is required")
    return check_calendar_conflict(target_time)
