from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .user import User # noqa F401
    # from .order import OrderItem # If you have OrderItem model relating to Product


// Shared properties
class ProductBase(SQLModel):
    name: str = Field(index=True)
    description: str  # Non-optional
    price: float = Field(gt=0) # Price must be greater than 0
    category: str = Field(index=True)
    in_stock: int = Field(default=0, ge=0) # Stock cannot be negative
    # images: Optional[List[str]] = Field(default_factory=list) # For multiple image URLs/paths


// ... existing code ...
# Properties to return to client
class ProductRead(ProductBase):
    id: int
    created_at: datetime
    images: List[str] = [] # Ensure images is always a list, non-optional
    created_by_id: Optional[int] = None # Optionally expose who created it 


# Properties to receive via API on creation
class ProductCreate(ProductBase):
    pass


# Properties to receive via API on update
class ProductUpdate(SQLModel):
    name: Optional[str] = None
    description: Optional[str] = None # Description can be optional for updates
    price: Optional[float] = None
    category: Optional[str] = None
    in_stock: Optional[int] = None
    images: Optional[List[str]] = None


# Database model
class Product(ProductBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    images: List[str] = Field(default_factory=list) # Non-optional, defaults to empty list
    created_at: datetime = Field(default_factory=datetime.now)

    created_by_id: Optional[int] = Field(default=None, foreign_key="user.id", index=True)
    created_by: Optional["User"] = Relationship(back_populates="products")

    # If products can be part of order items
    # order_items: List["OrderItem"] = Relationship(back_populates="product")


# Properties to return to client
class ProductRead(ProductBase): # Inherits non-optional description from ProductBase
    id: int
    created_at: datetime
    images: List[str] # Non-optional, will be at least an empty list from Product model
    created_by_id: Optional[int] = None


# ... existing code ... 