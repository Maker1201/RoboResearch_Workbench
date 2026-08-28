from __future__ import annotations

from typing import Any, Type

from fastapi import HTTPException
from sqlalchemy.orm import Session


def list_items(db: Session, model: Type[Any], limit: int = 200):
    return db.query(model).order_by(model.id.desc()).limit(limit).all()


def get_item(db: Session, model: Type[Any], item_id: int):
    item = db.get(model, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


def create_item(db: Session, model: Type[Any], payload):
    item = model(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def update_item(db: Session, model: Type[Any], item_id: int, payload):
    item = get_item(db, model, item_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


def delete_item(db: Session, model: Type[Any], item_id: int) -> dict:
    item = get_item(db, model, item_id)
    db.delete(item)
    db.commit()
    return {"ok": True, "id": item_id}

