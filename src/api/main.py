from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from src.api import auth
from src.api import ui
from src.api import inventory_ui
from src.api import master_data_ui  # اضافه شدن ماژول مدیریت داده‌های پایه

from src.infrastructure.database import engine, SessionLocal
from src.domain_model import inventory_models

inventory_models.Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    db = SessionLocal()
    try:
        if not db.query(inventory_models.Warehouse).first():
            db.add_all([
                inventory_models.Warehouse(name="انبار شماره یک"),
                inventory_models.Warehouse(name="انبار شماره دو")
            ])
            
        if not db.query(inventory_models.Product).first():
            db.add_all([
                inventory_models.Product(name="شمش آهن", uom="تن"),
                inventory_models.Product(name="اوره گرانول", uom="تن")
            ])
        db.commit()
    finally:
        db.close()
    yield

app = FastAPI(
    title="Storage ERP API",
    description="سیستم مدیریت انبار و احراز هویت",
    version="1.0.0",
    lifespan=lifespan
)

app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(auth.router)
app.include_router(ui.router)
app.include_router(inventory_ui.router)
app.include_router(master_data_ui.router) # اتصال ماژول به هسته

@app.get("/", tags=["General"])
def read_root():
    return {"message": "Enterprise ERP API is running"}