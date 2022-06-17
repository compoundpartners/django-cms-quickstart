from django.contrib import admin

from cms.toolbar.utils import get_object_preview_url
from cms.utils.i18n import get_site_language_from_request

from test_articles import models, forms
from test_articles.cms_config import ArticleConfig


# # Use the version mixin if djangocms-versioning is installed and enabled
# url_admin_classes = [admin.ModelAdmin]

# #try:
# from djangocms_versioning.admin import ExtendedVersionAdminMixin

# url_admin_classes.insert(0, ExtendedVersionAdminMixin)
# print(url_admin_classes)
# #except ImportError:
# #    pass


def is_versioning_enabled():
    return True

@admin.register(models.ArticleContent)
class ArticleContentAdmin(admin.ModelAdmin):
    form = forms.ArticleContentForm
    search_fields = ['title', 'slug']
    prepopulated_fields = {'slug': ('title',)}

    def get_changeform_initial_data(self, request):
        return {'language': get_site_language_from_request(request)}

    def view_on_site(self, obj):
        return get_object_preview_url(obj, obj.language)

    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        # Provide additional context to the changeform
        extra_context['is_versioning_enabled'] = is_versioning_enabled()
        return super().change_view(
            request, object_id, form_url, extra_context=extra_context,
        )

admin.register(models.Article)
