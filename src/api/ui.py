from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["UI"])
templates = Jinja2Templates(directory="templates")

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, msg: str = None):
    # استفاده از سینتکس استاندارد برای رندر HTML
    return templates.TemplateResponse(
        request=request, 
        name="dashboard.html", 
        context={"request": request, "msg": msg}
    )