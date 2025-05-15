from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from pydantic import EmailStr, Field as PydanticField, validator
from sqlmodel import Field, SQLModel, Relationship

if TYPE_CHECKING:
    from .product import Product # noqa F401
    from .order import Order # noqa F401

# Shared properties
class UserBase(SQLModel):
    email: EmailStr = Field(unique=True, index=True, sa_column_kwargs={"unique": True})
    name: str = Field(index=True)
    is_active: bool = Field(default=True)
    role: str = Field(default="user", index=True) # e.g., "user", "admin"

# Properties to receive via API on creation
class UserCreate(UserBase):
    password: str = PydanticField(min_length=6)

# Properties to receive via API on update (by user themselves)
class UserUpdateProfile(SQLModel):
    email: Optional[EmailStr] = None
    name: Optional[str] = None

# Properties to receive via API on update (by admin)
class UserUpdateByAdmin(SQLModel):
    email: Optional[EmailStr] = None
    name: Optional[str] = None
    is_active: Optional[bool] = None
    role: Optional[str] = None

    @validator('role')
    def role_must_be_user_or_admin(cls, v):
        if v is not None and v not in ['user', 'admin']:
            raise ValueError('Role must be user or admin')
        return v

class UserChangePassword(SQLModel):
    current_password: str
    new_password: str = PydanticField(min_length=6)

# Database model
class User(UserBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    hashed_password: str
    created_at: datetime = Field(default_factory=datetime.now)

    # Relationships
    products: List["Product"] = Relationship(back_populates="created_by")
    orders: List["Order"] = Relationship(back_populates="customer")

# Properties to return to client
class UserRead(UserBase):
    id: int
    created_at: datetime

# Schema for login form (though OAuth2PasswordRequestForm is typically used)
class UserLogin(SQLModel):
    email: EmailStr
    password: str 