"""模板和静态资源模块"""

from templates.html_templates import TemplateManager
from templates.static_assets import CSSAssets, JSAssets

__all__ = ['TemplateManager', 'CSSAssets', 'JSAssets']