from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Optional, List

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from database import Base, engine, get_db, wait_for_db
from models import (
    User,
    Camper,
    ParentCamper,
    CampYear,
    Enrollment,
    Group,
    GroupMembership,
    GroupEvent,
)
from schemas import (
    RegisterParentRequest,
    LoginRequest,
    TokenResponse,
    UserOut,
    ParentCreate,
    CamperCreate,
    CamperOut,
    EnrollmentCreate,
    EnrollmentUpdate,
    EnrollmentOut,
    GroupCreate,
    GroupOut,
    GroupMembershipCreate,
    GroupEventCreate,
    GroupEventOut,
    ParentCamperLinkOut,
    ParentScheduleItem,
)
from auth import (
    hash_password,
    verify_password,
    create_token,
    require_auth,
    require_role,
)

APP_SEED_ADMIN_EMAIL = os.getenv("APP_SEED_ADMIN_EMAIL", "admin@camp.local")
APP_SEED_ADMIN_PASSWORD = os.getenv("APP_SEED_ADMIN_PASSWORD", "admin1234")
APP_SEED_CAMP_YEAR = int(os.getenv("APP_SEED_CAMP_YEAR", "2026"))

app = FastAPI(title="Camp Management API (Sprint 1 Prototype)", openapi_url="/api/openapi.json", docs_url="/api/docs")

# CORS isn't needed when using nginx proxy on same origin, but kept friendly for dev tooling.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup():
    # Ensure DB is reachable, create tables, seed admin + camp year.
    wait_for_db(60)
    Base.metadata.create_all(bind=engine)
    with next(get_db()) as db:
        seed_admin_and_year(db)

def seed_admin_and_year(db: Session) -> None:
    # Seed camp year
    year = db.query(CampYear).filter(CampYear.year == APP_SEED_CAMP_YEAR).first()
    if not year:
        year = CampYear(year=APP_SEED_CAMP_YEAR, is_active=True)
        db.add(year)
        db.commit()

    # Seed admin
    admin = db.query(User).filter(User.email == APP_SEED_ADMIN_EMAIL).first()
    if not admin:
        admin = User(
            email=APP_SEED_ADMIN_EMAIL,
            full_name="Default Admin",
            password_hash=hash_password(APP_SEED_ADMIN_PASSWORD),
            role="admin",
            is_active=True,
        )
        db.add(admin)
        db.commit()

# ------------------- Utilities -------------------

def get_or_create_camp_year(db: Session, year_value: int) -> CampYear:
    cy = db.query(CampYear).filter(CampYear.year == year_value).first()
    if not cy:
        cy = CampYear(year=year_value, is_active=False)
        db.add(cy)
        db.commit()
        db.refresh(cy)
    return cy

def ensure_parent_owns_camper(db: Session, parent_user_id: int, camper_id: int) -> None:
    link = db.query(ParentCamper).filter(
        ParentCamper.parent_user_id == parent_user_id,
        ParentCamper.camper_id == camper_id
    ).first()
    if not link:
        raise HTTPException(status_code=403, detail="Parent does not own this camper")

# ------------------- Auth -------------------

@app.post("/api/auth/register-parent", response_model=UserOut)
def register_parent(payload: RegisterParentRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    parent = User(
        email=payload.email,
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
        role="parent",
        is_active=True,
    )
    db.add(parent)
    db.commit()
    db.refresh(parent)
    return parent

@app.post("/api/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email, User.is_active == True).first()  # noqa: E712
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    tok = create_token(db, user)
    return TokenResponse(access_token=tok.token, expires_at=tok.expires_at)

@app.get("/api/auth/me", response_model=UserOut)
def me(user: User = Depends(require_auth)):
    return user

# ------------------- Admin: Parents -------------------

@app.post("/api/admin/parents", response_model=UserOut, dependencies=[Depends(require_role("admin"))])
def admin_create_parent(payload: ParentCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already exists")
    parent = User(
        email=payload.email,
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
        role="parent",
        is_active=True,
    )
    db.add(parent)
    db.commit()
    db.refresh(parent)
    return parent

# ------------------- Admin: Campers -------------------

@app.post("/api/admin/campers", response_model=CamperOut, dependencies=[Depends(require_role("admin"))])
def admin_create_camper(payload: CamperCreate, db: Session = Depends(get_db)):
    camper = Camper(
        first_name=payload.first_name,
        last_name=payload.last_name,
        date_of_birth=payload.date_of_birth,
        emergency_info=payload.emergency_info,
    )
    db.add(camper)
    db.commit()
    db.refresh(camper)
    return camper

@app.get("/api/admin/campers", response_model=List[CamperOut], dependencies=[Depends(require_role("admin"))])
def admin_list_campers(db: Session = Depends(get_db)):
    return db.query(Camper).order_by(Camper.id.desc()).all()

# ------------------- Parent: Campers (children) -------------------

@app.post("/api/parent/campers", response_model=ParentCamperLinkOut, dependencies=[Depends(require_role("parent"))])
def parent_add_child(payload: CamperCreate, user: User = Depends(require_auth), db: Session = Depends(get_db)):
    camper = Camper(
        first_name=payload.first_name,
        last_name=payload.last_name,
        date_of_birth=payload.date_of_birth,
        emergency_info=payload.emergency_info,
    )
    db.add(camper)
    db.commit()
    db.refresh(camper)

    link = ParentCamper(parent_user_id=user.id, camper_id=camper.id)
    db.add(link)
    db.commit()
    db.refresh(link)
    return link

@app.get("/api/parent/campers", response_model=List[ParentCamperLinkOut], dependencies=[Depends(require_role("parent"))])
def parent_list_children(user: User = Depends(require_auth), db: Session = Depends(get_db)):
    links = db.query(ParentCamper).filter(ParentCamper.parent_user_id == user.id).order_by(ParentCamper.id.desc()).all()
    return links

# ------------------- Parent: Enrollment -------------------

@app.post("/api/parent/enrollments", response_model=EnrollmentOut, dependencies=[Depends(require_role("parent"))])
def parent_enroll(payload: EnrollmentCreate, user: User = Depends(require_auth), db: Session = Depends(get_db)):
    ensure_parent_owns_camper(db, user.id, payload.camper_id)
    cy = get_or_create_camp_year(db, payload.camp_year)

    existing = db.query(Enrollment).filter(Enrollment.camp_year_id == cy.id, Enrollment.camper_id == payload.camper_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Already enrolled for this camp year")

    enr = Enrollment(camp_year_id=cy.id, camper_id=payload.camper_id, status="pending", notes=None)
    db.add(enr)
    db.commit()
    db.refresh(enr)
    return enr

@app.get("/api/parent/enrollments", response_model=List[EnrollmentOut], dependencies=[Depends(require_role("parent"))])
def parent_list_enrollments(
    user: User = Depends(require_auth),
    camp_year: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
):
    q = db.query(Enrollment).join(Camper).join(ParentCamper, ParentCamper.camper_id == Camper.id)
    q = q.filter(ParentCamper.parent_user_id == user.id)

    if camp_year is not None:
        cy = db.query(CampYear).filter(CampYear.year == camp_year).first()
        if not cy:
            return []
        q = q.filter(Enrollment.camp_year_id == cy.id)

    return q.order_by(Enrollment.id.desc()).all()

@app.put("/api/parent/enrollments/{enrollment_id}", response_model=EnrollmentOut, dependencies=[Depends(require_role("parent"))])
def parent_update_enrollment(
    enrollment_id: int,
    payload: EnrollmentUpdate,
    user: User = Depends(require_auth),
    db: Session = Depends(get_db),
):
    enr = db.query(Enrollment).filter(Enrollment.id == enrollment_id).first()
    if not enr:
        raise HTTPException(status_code=404, detail="Enrollment not found")

    # ensure parent owns the camper
    ensure_parent_owns_camper(db, user.id, enr.camper_id)

    enr.status = payload.status
    enr.notes = payload.notes
    db.commit()
    db.refresh(enr)
    return enr

# ------------------- Admin: Groups -------------------

@app.post("/api/admin/groups", response_model=GroupOut, dependencies=[Depends(require_role("admin"))])
def admin_create_group(payload: GroupCreate, db: Session = Depends(get_db)):
    cy = get_or_create_camp_year(db, payload.camp_year)
    g = Group(camp_year_id=cy.id, name=payload.name, description=payload.description)
    db.add(g)
    db.commit()
    db.refresh(g)
    return g

@app.get("/api/admin/groups", response_model=List[GroupOut], dependencies=[Depends(require_role("admin"))])
def admin_list_groups(camp_year: Optional[int] = Query(default=None), db: Session = Depends(get_db)):
    q = db.query(Group).join(CampYear)
    if camp_year is not None:
        q = q.filter(CampYear.year == camp_year)
    return q.order_by(Group.id.desc()).all()

## CHANGED @app.post("/api/admin/groups/{group_id}/members", response_model=GroupMemberOut, dependencies=[Depends(require_role("admin"))])  


@app.post("/api/admin/groups/{group_id}/members", response_model=GroupMembershipCreate, dependencies=[Depends(require_role("admin"))])


def admin_add_group_member(group_id: int, payload: GroupMembershipCreate, db: Session = Depends(get_db)):
    g = db.query(Group).filter(Group.id == group_id).first()
    if not g:
        raise HTTPException(status_code=404, detail="Group not found")

    camper = db.query(Camper).filter(Camper.id == payload.camper_id).first()
    if not camper:
        raise HTTPException(status_code=404, detail="Camper not found")

    existing = db.query(GroupMembership).filter(GroupMembership.group_id == group_id, GroupMembership.camper_id == payload.camper_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Camper already in group")

    m = GroupMembership(group_id=group_id, camper_id=payload.camper_id)
    db.add(m)
    db.commit()
    db.refresh(m)
    return m

# ------------------- Admin: Events (Scheduling) -------------------

@app.post("/api/admin/events", response_model=GroupEventOut, dependencies=[Depends(require_role("admin"))])
def admin_create_event(payload: GroupEventCreate, db: Session = Depends(get_db)):
    g = db.query(Group).filter(Group.id == payload.group_id).first()
    if not g:
        raise HTTPException(status_code=404, detail="Group not found")

    if payload.end_time <= payload.start_time:
        raise HTTPException(status_code=400, detail="end_time must be after start_time")

    ev = GroupEvent(
        group_id=payload.group_id,
        title=payload.title,
        description=payload.description,
        location=payload.location,
        start_time=payload.start_time,
        end_time=payload.end_time,
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)
    return ev

@app.get("/api/admin/events", response_model=List[GroupEventOut], dependencies=[Depends(require_role("admin"))])
def admin_list_events(
    group_id: Optional[int] = Query(default=None),
    camp_year: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
):
    q = db.query(GroupEvent).join(Group).join(CampYear)
    if camp_year is not None:
        q = q.filter(CampYear.year == camp_year)
    if group_id is not None:
        q = q.filter(GroupEvent.group_id == group_id)
    return q.order_by(GroupEvent.start_time.asc()).all()

# ------------------- Parent: Schedule view -------------------

@app.get("/api/parent/schedule", response_model=List[ParentScheduleItem], dependencies=[Depends(require_role("parent"))])
def parent_view_schedule(
    camper_id: Optional[int] = Query(default=None),
    camp_year: Optional[int] = Query(default=None),
    user: User = Depends(require_auth),
    db: Session = Depends(get_db),
):
    # Determine which campers belong to this parent
    camper_ids = [pc.camper_id for pc in db.query(ParentCamper).filter(ParentCamper.parent_user_id == user.id).all()]
    if not camper_ids:
        return []

    if camper_id is not None:
        if camper_id not in camper_ids:
            raise HTTPException(status_code=403, detail="Parent does not own this camper")
        camper_ids = [camper_id]

    # Map campers -> groups (current memberships)
    memberships = db.query(GroupMembership).filter(GroupMembership.camper_id.in_(camper_ids)).all()
    if not memberships:
        return []

    group_ids = list({m.group_id for m in memberships})

    # Optionally filter by camp_year
    q = db.query(GroupEvent).join(Group).join(CampYear).filter(GroupEvent.group_id.in_(group_ids))
    if camp_year is not None:
        q = q.filter(CampYear.year == camp_year)

    events = q.order_by(GroupEvent.start_time.asc()).all()
    # Need group names and camper names
    groups = {g.id: g for g in db.query(Group).filter(Group.id.in_(group_ids)).all()}
    campers = {c.id: c for c in db.query(Camper).filter(Camper.id.in_(camper_ids)).all()}

    # Many-to-many: if multiple campers in same group, events appear for each camper.
    camper_groups = {}
    for m in memberships:
        camper_groups.setdefault(m.camper_id, set()).add(m.group_id)

    out: list[ParentScheduleItem] = []
    for ev in events:
        for cid, gids in camper_groups.items():
            if ev.group_id in gids:
                camper = campers.get(cid)
                grp = groups.get(ev.group_id)
                if not camper or not grp:
                    continue
                out.append(
                    ParentScheduleItem(
                        camper_id=cid,
                        camper_name=f"{camper.first_name} {camper.last_name}",
                        group_id=grp.id,
                        group_name=grp.name,
                        event_id=ev.id,
                        title=ev.title,
                        start_time=ev.start_time,
                        end_time=ev.end_time,
                        location=ev.location,
                    )
                )
    return out
