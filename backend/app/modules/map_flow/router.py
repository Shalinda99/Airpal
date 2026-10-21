import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.common.audit import audit
from app.core.deps import get_airport_or_404, require_airport_admin
from app.db.models import MapNode, User
from app.db.session import get_db
from app.modules.onboarding.map_defaults import DEFAULT_MAPS

public = APIRouter(prefix="/airports/{airport_id}", tags=["map_flow"])
portal = APIRouter(prefix="/portal/airports/{airport_id}", tags=["portal"])

Flow = Literal["departure", "arrival", "transit"]
Scope = Literal["domestic", "international"]


def _ser(nodes: list[MapNode]) -> list[dict]:
    out = []
    for n in nodes:
        out.append({"id": str(n.id), "order": n.order, "type": n.type, "label": n.label,
                    "walking_minutes": n.walking_minutes, "notes": n.notes})
    return out


@public.get("/map-flow")
def get_map(airport_id: uuid.UUID, flow: Flow = "departure", scope: Scope = "international",
            db: Session = Depends(get_db)):
    airport = get_airport_or_404(db, airport_id)
    version = airport.current_published_version
    nodes = [] if version == 0 else list(db.scalars(
        select(MapNode).where(MapNode.airport_id == airport_id, MapNode.version_no == version,
                              MapNode.flow == flow, MapNode.scope == scope).order_by(MapNode.order)))
    return {"flow": flow, "scope": scope, "version": version, "basic": version == 0,
            "total_walking_minutes": sum(n.walking_minutes for n in nodes), "nodes": _ser(nodes)}


class NodeIn(BaseModel):
    type: str = Field(min_length=1, max_length=32)
    label: str = Field(min_length=1, max_length=100)
    walking_minutes: int = Field(0, ge=0, le=120)
    notes: str | None = None


class MapIn(BaseModel):
    flow: Flow
    scope: Scope
    nodes: list[NodeIn] = Field(min_length=2, max_length=30)


@portal.get("/map-flow")
def get_draft(airport_id: uuid.UUID, flow: Flow, scope: Scope, user: User = Depends(require_airport_admin),
              db: Session = Depends(get_db)):
    nodes = list(db.scalars(select(MapNode).where(MapNode.airport_id == airport_id, MapNode.version_no == 0,
                                                  MapNode.flow == flow, MapNode.scope == scope)
                            .order_by(MapNode.order)))
    if nodes:
        return {"flow": flow, "scope": scope, "is_default": False, "nodes": _ser(nodes)}
    defaults = DEFAULT_MAPS.get((flow, scope))
    if not defaults:
        raise HTTPException(404, "No default for this flow")
    return {"flow": flow, "scope": scope, "is_default": True,
            "nodes": [{"id": None, "order": i, "type": t, "label": lbl, "walking_minutes": m, "notes": n}
                      for i, (t, lbl, m, n) in enumerate(defaults)]}


@portal.put("/map-flow")
def put_draft(airport_id: uuid.UUID, body: MapIn, request: Request, user: User = Depends(require_airport_admin),
              db: Session = Depends(get_db)):
    """Replaces the draft map for a flow/scope. Passengers see it after the next publish."""
    db.execute(delete(MapNode).where(MapNode.airport_id == airport_id, MapNode.version_no == 0,
                                     MapNode.flow == body.flow, MapNode.scope == body.scope))
    for i, n in enumerate(body.nodes):
        db.add(MapNode(airport_id=airport_id, version_no=0, flow=body.flow, scope=body.scope, order=i,
                       **n.model_dump()))
    audit(db, user.id, "map_flow.update", "map_flow", f"{body.flow}/{body.scope}", airport_id,
          after=body.model_dump(mode="json"), ip=request.client.host if request.client else None)
    db.commit()
    return {"saved": len(body.nodes)}
