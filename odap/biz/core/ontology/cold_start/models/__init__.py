"""领域模型 + 模板加载器"""
from .models import Industry, ColdStartReport
from .template_loader import list_industries, load_template

__all__ = ["Industry", "ColdStartReport", "list_industries", "load_template"]
