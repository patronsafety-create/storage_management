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

# --- Product Schemas ---
class ProductBase(BaseModel):
    sku: str = Field(..., max_length=50, description="کدینگ خودکار یا دستی کالا")
    name: str = Field(..., max_length=200, description="نام کالا")
    attributes: Dict[str, Any] = Field(default_factory=dict, description="ویژگی‌های داینامیک کالا")
    reorder_point: int = Field(default=0, ge=0, description="نقطه سفارش")
    is_active: bool = True

class ProductCreate(ProductBase):
    pass

class ProductResponse(ProductBase):
    id: int
    created_at: datetime
    updated_at: datetime

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