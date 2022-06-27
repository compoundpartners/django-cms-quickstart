from cms.app_base import CMSAppConfig
from cms.utils.i18n import get_language_tuple

from djangocms_versioning.datastructures import VersionableItem, default_copy
from djangocms_versioning.admin import ExtendedVersionAdminMixin

from test_articles.models import ArticleContent
from test_articles.rendering import render_article_content



class ArticleConfig(CMSAppConfig):
    cms_enabled = True
    djangocms_versioning_enabled = True
    cms_toolbar_enabled_models = [(ArticleContent, render_article_content)]
    versioning = [
        VersionableItem(
            content_model=ArticleContent,
            grouper_field_name='article',
            copy_function=lambda content: content.copy(),
            extra_grouping_fields=['language'],
            version_list_filter_lookups={'language': get_language_tuple},
            content_admin_mixin=ExtendedVersionAdminMixin,
        ),
    ]
