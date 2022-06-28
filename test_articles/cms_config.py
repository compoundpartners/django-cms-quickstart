from django.conf import settings

from cms.app_base import CMSAppConfig
from cms.utils.i18n import get_language_tuple

from djangocms_versioning.datastructures import VersionableItem, default_copy

from test_articles.admin import ChangeLinkesAdminMixin
from test_articles.models import ArticleContent
from test_articles.rendering import render_article_content


try:
    from djangocms_versioning.constants import DRAFT  # NOQA
    djangocms_versioning_installed = True
except ImportError:
    djangocms_versioning_installed = False


class ArticleConfig(CMSAppConfig):
    cms_enabled = True
    djangocms_versioning_enabled = True
    cms_toolbar_enabled_models = [(ArticleContent, render_article_content)]
    moderated_models = [ArticleContent]

    djangocms_versioning_enabled = getattr(
        settings, 'VERSIONING_CMS_MODELS_ENABLED', True)

    if djangocms_versioning_enabled and djangocms_versioning_installed:

        versioning = [
            VersionableItem(
                content_model=ArticleContent,
                grouper_field_name='article',
                copy_function=lambda content: content.copy(),
                extra_grouping_fields=['language'],
                version_list_filter_lookups={'language': get_language_tuple},
                content_admin_mixin=ChangeLinkesAdminMixin,
            ),
        ]
