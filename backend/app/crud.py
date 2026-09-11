from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from . import models, schemas


DEFAULT_COLUMNS = [
    ("Backlog", "#94a3b8", 0),
    ("Todo", "#38bdf8", 1),
    ("In Progress", "#34d399", 2),
    ("Blocked", "#fb7185", 3),
    ("Done", "#a3e635", 4),
]


def normalize_project_path(path: str | None) -> str:
    trimmed = (path or "").strip()
    if not trimmed:
        return ""
    if trimmed.startswith("~/"):
        return trimmed
    return trimmed.rstrip("/") or trimmed


def seed_board(db: Session) -> None:
    count = db.scalar(select(func.count()).select_from(models.Column)) or 0
    if count > 0:
        return

    columns = [
        models.Column(name=name, color=color, position=position)
        for name, color, position in DEFAULT_COLUMNS
    ]
    db.add_all(columns)
    db.commit()


def list_hidden_projects(db: Session) -> list[str]:
    rows = db.scalars(select(models.HiddenProject).order_by(models.HiddenProject.path)).all()
    return [row.path for row in rows]


def hide_project(db: Session, path: str) -> list[str]:
    key = normalize_project_path(path)
    existing = db.get(models.HiddenProject, key)
    if existing is None:
        db.add(models.HiddenProject(path=key))
        db.commit()
    return list_hidden_projects(db)


def unhide_project(db: Session, path: str) -> list[str]:
    key = normalize_project_path(path)
    existing = db.get(models.HiddenProject, key)
    if existing is not None:
        db.delete(existing)
        db.commit()
    return list_hidden_projects(db)


def get_board(db: Session) -> schemas.BoardOut:
    columns = db.scalars(
        select(models.Column)
        .options(selectinload(models.Column.tasks))
        .order_by(models.Column.position)
    ).all()
    hidden = list_hidden_projects(db)
    hidden_set = set(hidden)

    filtered_columns: list[schemas.ColumnOut] = []
    for column in columns:
        visible_tasks = [
            task
            for task in column.tasks
            if normalize_project_path(task.project_path) not in hidden_set
        ]
        filtered_columns.append(
            schemas.ColumnOut(
                id=column.id,
                name=column.name,
                position=column.position,
                color=column.color,
                created_at=column.created_at,
                tasks=visible_tasks,
            )
        )
    return schemas.BoardOut(columns=filtered_columns, hidden_projects=hidden)


def _next_position(db: Session, column_id: int) -> int:
    current = db.scalar(
        select(func.max(models.Task.position)).where(models.Task.column_id == column_id)
    )
    return 0 if current is None else current + 1


def create_task(db: Session, payload: schemas.TaskCreate) -> models.Task:
    column = db.get(models.Column, payload.column_id)
    if column is None:
        raise ValueError("Column not found")

    position = payload.position if payload.position is not None else _next_position(db, payload.column_id)
    task = models.Task(
        title=payload.title.strip(),
        description=payload.description or "",
        agent=payload.agent,
        priority=payload.priority,
        project_path=payload.project_path or "",
        column_id=payload.column_id,
        position=position,
        source="manual",
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def update_task(db: Session, task_id: int, payload: schemas.TaskUpdate) -> models.Task | None:
    task = db.get(models.Task, task_id)
    if task is None:
        return None

    data = payload.model_dump(exclude_unset=True)
    if "title" in data and data["title"] is not None:
        data["title"] = data["title"].strip()

    for key, value in data.items():
        setattr(task, key, value)

    db.commit()
    db.refresh(task)
    return task


def delete_task(db: Session, task_id: int) -> bool:
    task = db.get(models.Task, task_id)
    if task is None:
        return False
    db.delete(task)
    db.commit()
    return True


def move_task(db: Session, task_id: int, payload: schemas.TaskMove) -> models.Task | None:
    task = db.get(models.Task, task_id)
    if task is None:
        return None

    target_column = db.get(models.Column, payload.column_id)
    if target_column is None:
        raise ValueError("Column not found")

    source_column_id = task.column_id
    target_column_id = payload.column_id
    target_position = max(0, payload.position)

    if source_column_id == target_column_id:
        siblings = db.scalars(
            select(models.Task)
            .where(models.Task.column_id == source_column_id, models.Task.id != task_id)
            .order_by(models.Task.position)
        ).all()
        siblings.insert(min(target_position, len(siblings)), task)
        for index, item in enumerate(siblings):
            item.position = index
            item.column_id = source_column_id
    else:
        source_tasks = db.scalars(
            select(models.Task)
            .where(models.Task.column_id == source_column_id, models.Task.id != task_id)
            .order_by(models.Task.position)
        ).all()
        for index, item in enumerate(source_tasks):
            item.position = index

        target_tasks = db.scalars(
            select(models.Task)
            .where(models.Task.column_id == target_column_id, models.Task.id != task_id)
            .order_by(models.Task.position)
        ).all()
        target_tasks.insert(min(target_position, len(target_tasks)), task)
        for index, item in enumerate(target_tasks):
            item.position = index
            item.column_id = target_column_id

    db.commit()
    db.refresh(task)
    return task


def create_column(db: Session, payload: schemas.ColumnCreate) -> models.Column:
    position = payload.position
    if position is None:
        current = db.scalar(select(func.max(models.Column.position)))
        position = 0 if current is None else current + 1

    column = models.Column(name=payload.name.strip(), color=payload.color, position=position)
    db.add(column)
    db.commit()
    db.refresh(column)
    return column


def update_column(db: Session, column_id: int, payload: schemas.ColumnUpdate) -> models.Column | None:
    column = db.get(models.Column, column_id)
    if column is None:
        return None

    data = payload.model_dump(exclude_unset=True)
    if "name" in data and data["name"] is not None:
        data["name"] = data["name"].strip()

    for key, value in data.items():
        setattr(column, key, value)

    db.commit()
    db.refresh(column)
    return column


def delete_column(db: Session, column_id: int) -> bool:
    column = db.get(models.Column, column_id)
    if column is None:
        return False
    db.delete(column)
    db.commit()
    return True
