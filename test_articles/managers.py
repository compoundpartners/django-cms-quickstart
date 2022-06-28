import functools
import operator

from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site
from django.db import models
from django.db.models import Q
from django.db.models.query import QuerySet

from cms.utils.i18n import get_fallback_languages


class ArticleQuerySet(QuerySet):
    pass


class ArticleManager(models.Manager):

    def get_queryset(self):
        """Change standard model queryset to our own.
        """
        return ArticleQuerySet(self.model)

    def search(self, q, language=None, current_site_only=True):
        """Simple search function

        Plugins can define a 'search_fields' tuple similar to ModelAdmin classes
        """
        from cms.plugin_pool import plugin_pool

        qs = self.get_queryset()
        qs = qs.public()

        qt = Q(articlecontent_set__title__icontains=q)

        # find 'searchable' plugins and build query
        qp = Q()
        plugins = plugin_pool.registered_plugins
        for plugin in plugins:
            cmsplugin = plugin.model
            if not (
                hasattr(cmsplugin, 'search_fields') and
                hasattr(cmsplugin, 'cmsplugin_ptr')
            ):
                continue
            field = cmsplugin.cmsplugin_ptr.field
            related_query_name = field.related_query_name()
            if related_query_name and not related_query_name.startswith('+'):
                for field in cmsplugin.search_fields:
                    qp |= Q(**{
                        'placeholders__cmsplugin__{0}__{1}__icontains'.format(
                            related_query_name,
                            field,
                        ): q})
        if language:
            qt &= Q(articlecontent_set__language=language)
            qp &= Q(cmsplugin__language=language)

        qs = qs.filter(qt | qp)

        return qs.distinct()


class ArticleContentManager(models.Manager):
    def get_translation(self, article, language, language_fallback=False):
        """
        Gets the latest content for a particular article and language. Falls back
        to another language if wanted.
        """
        try:
            translation = self.get(language=language, article=article)
            return translation
        except self.model.DoesNotExist:
            if language_fallback:
                try:
                    translations = self.filter(article=article)
                    fallbacks = get_fallback_languages(language)
                    for lang in fallbacks:
                        for translation in translations:
                            if lang == translation.language:
                                return translation
                    return None
                except self.model.DoesNotExist:
                    pass
            else:
                raise
        return None
