"""模板和静态资源模块"""

from templates.i18n_templates import I18nTemplateManager
from templates.static_assets import CSSAssets, JSAssets

__all__ = ['I18nTemplateManager', 'CSSAssets', 'JSAssets']