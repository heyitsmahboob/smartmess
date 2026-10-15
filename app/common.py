from pathlib import Path
from fastapi.templating import Jinja2Templates
from fastapi import Request

templates_dir = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

def render_template(request: Request, name: str, context: dict = None, status_code: int = 200):
    if context is None:
        context = {}
    return templates.TemplateResponse(
        request=request,
        name=name,
        context=context,
        status_code=status_code
    )
