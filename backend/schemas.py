from __future__ import annotations

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field

# --------- Auth ---------

class RegisterParentRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    full_name: str = Field(min_length=1)

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime

class UserOut(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    role: str
    is_active: bool

    class Config:
        from_attributes = True

# --------- Admin / Parent core entities ---------

class ParentCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    full_name: str = Field(min_length=1)

class CamperCreate(BaseModel):
    first_name: str = Field(min_length=1)
    last_name: str = Field(min_length=1)
    date_of_birth: Optional[str] = None
    emergency_info: Optional[str] = None

class CamperOut(BaseModel):
    id: int
    first_name: str
    last_name: str
    date_of_birth: Optional[str] = None
    emergency_info: Optional[str] = None

    class Config:
        from_attributes = True

class CampYearOut(BaseModel):
    id: int
    year: int
    is_active: bool

    class Config:
        from_attributes = True

class EnrollmentCreate(BaseModel):
    camper_id: int
    camp_year: int

class EnrollmentUpdate(BaseModel):
    status: str = Field(pattern="^(pending|admitted|withdrawn)$")
    notes: Optional[str] = None

class EnrollmentOut(BaseModel):
    id: int
    status: str
    notes: Optional[str]
    camp_year: CampYearOut
    camper: CamperOut

    class Config:
        from_attributes = True

class GroupCreate(BaseModel):
    camp_year: int
    name: str = Field(min_length=1)
    description: Optional[str] = None

class GroupOut(BaseModel):
    id: int
    name: str
    description: Optional[str]
    camp_year: CampYearOut

    class Config:
        from_attributes = True

class GroupMembershipCreate(BaseModel):
    camper_id: int

class GroupMemberOut(BaseModel):
    id: int
    camper: CamperOut

    class Config:
        from_attributes = True

class GroupEventCreate(BaseModel):
    group_id: int
    title: str = Field(min_length=1)
    description: Optional[str] = None
    location: Optional[str] = None
    start_time: datetime
    end_time: datetime

class GroupEventOut(BaseModel):
    id: int
    group_id: int
    title: str
    description: Optional[str]
    location: Optional[str]
    start_time: datetime
    end_time: datetime

    class Config:
        from_attributes = True

class ParentCamperLinkOut(BaseModel):
    id: int
    camper: CamperOut

    class Config:
        from_attributes = True

class ParentScheduleItem(BaseModel):
    camper_id: int
    camper_name: str
    group_id: int
    group_name: str
    event_id: int
    title: str
    start_time: datetime
    end_time: datetime
    location: Optional[str] = None
