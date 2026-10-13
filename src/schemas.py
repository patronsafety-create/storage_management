from pydantic import BaseModel, Field, constr
from typing import Dict, Any, Optional
from datetime import datetime

# --- Warehouse Schemas ---
class WarehouseBase(BaseModel):
    code: str = Field(..., max_length=50, description="کد یکتای انبار")
    name: str = Field(..., max_length=100, description="نام انبار")
    is_active: bool = True

class WarehouseCreate(WarehouseBase):
    pass

class WarehouseResponse(WarehouseBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# --- Category Schemas ---
class ProductCategoryBase(BaseModel):
    name: str = Field(..., max_length=100, description="نام دسته‌بندی کالا")
    code: Optional[str] = Field(None, max_length=50, description="کد رده کالا")
    description: Optional[str] = None
    parent_id: Optional[int] = None

class ProductCategoryCreate(ProductCategoryBase):
    pass

class ProductCategoryResponse(ProductCategoryBase):
    id: int

    class Config:
        from_attributes = True

# --- Product Schemas ---
class ProductBase(BaseModel):
    name: str = Field(..., max_length=200, description="نام کالا")
    uom: str = Field("عدد", max_length=50, description="واحد سنجش")
    sku: Optional[str] = Field(None, max_length=50, description="کدینگ خودکار یا بارکد یکتا")
    category_id: Optional[int] = None
    brand: Optional[str] = None
    size: Optional[str] = None
    length: Optional[float] = None
    thickness: Optional[float] = None
    grade: Optional[str] = None
    standard: Optional[str] = None
    min_stock: Optional[float] = 0.0
    max_stock: Optional[float] = 0.0
    reorder_point: Optional[float] = 0.0
    description: Optional[str] = None
    is_active: bool = True

class ProductCreate(ProductBase):
    pass

class ProductResponse(ProductBase):
    id: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# --- PriceList Schemas ---
class PriceListBase(BaseModel):
    product_id: int
    currency: str = Field(..., min_length=3, max_length=3, description="کد سه حرفی ارز")
    price: float = Field(..., gt=0, description="قیمت پایه کالا")
    is_active: bool = True

class PriceListCreate(PriceListBase):
    pass

class PriceListResponse(PriceListBase):
    id: int
    valid_from: datetime

    class Config:
        from_attributes = True