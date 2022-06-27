from __future__ import unicode_literals
from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404, HttpResponsePermanentRedirect
from django.views import generic
from django.urls import Resolver404, resolve
from django.utils.translation import get_language_from_request, override, ugettext

from cms.apphook_pool import apphook_pool
from cms.utils.i18n import get_fallback_languages#, get_redirect_on_fallback

from parler.utils.context import switch_language

from test_articles import models


class LanguageAndSectionMixin():
    language_field = 'language'
    namespace_field = 'article__section__namespace'
    config_model = models.Section
    model = models.ArticleContent

    def dispatch(self, request, *args, **kwargs):
        app = None
        if getattr(request, 'current_page', None) and request.current_page.application_urls:
            app = apphook_pool.get_apphook(request.current_page.application_urls)
        if app and app.app_config:
            try:
                with override(self.get_language()):
                    self.namespace = request.article_namespace = resolve(request.path_info).namespace
                    self.config = request.article_config = app.get_config(self.namespace)
            except Resolver404:
                self.namespace = ''
                self.config = None
        return super().dispatch(request, *args, **kwargs)

    def get_language_field(self):
        return self.language_field

    def get_namespace_field(self):
        return self.namespace_field

    def get_language(self):
        return get_language_from_request(self.request, check_path=True)

    def get_namespace(self):
        return self.namespace

    def get_queryset(self, language=None):
        qs = super().get_queryset()
        filters = {
            self.get_language_field(): language or self.get_language(),
        }
        if self.namespace != self.config_model.default_namespace:
            filters[self.get_namespace_field]: self.get_namespace()
        return qs.filter(**filters)

class TranslatableSlugMixin(LanguageAndSectionMixin):

    def get_queryset(self, slug, language):
        qs = super().get_queryset(language=language)
        return qs.filter(**{self.get_slug_field(): slug})

    def get_language_choices(self):
        """
        Define the language choices for the view, defaults to the defined settings.
        """
        language = self.get_language()
        return [language] + get_fallback_languages(language)

    def dispatch(self, request, *args, **kwargs):
        try:
            return super(TranslatableSlugMixin, self).dispatch(request, *args, **kwargs)
        except FallbackLanguageResolved as e:
            # Handle the fallback language redirect for get_object()
            with switch_language(e.object, e.correct_language):
                return HttpResponsePermanentRedirect(e.object.get_absolute_url())

    def get_object(self, queryset=None):
        """
        Fetch the object using a translated slug.
        """
        slug = self.kwargs[self.slug_url_kwarg]
        choices = self.get_language_choices()

        obj = None
        using_fallback = False
        prev_choices = []
        for lang_choice in choices:
            try:
                # Get the single item from the filtered queryset
                # NOTE. Explicitly set language to the state the object was fetched in.
                if queryset is None:
                    queryset = self.get_queryset(slug, lang_choice)
                obj = queryset.get()
            except ObjectDoesNotExist:
                # Translated object not found, next object is marked as fallback.
                using_fallback = True
                prev_choices.append(lang_choice)
            else:
                break

        if obj is None:
            tried_msg = ", tried languages: {0}".format(", ".join(choices))
            error_message = ugettext("No %(verbose_name)s found matching the query") % {'verbose_name': queryset.model._meta.verbose_name}
            raise Http404(error_message + tried_msg)

        # Object found!
        if using_fallback:
            # It could happen that objects are resolved using their fallback language,
            # but the actual translation also exists. Either that means this URL should
            # raise a 404, or a redirect could be made as service to the users.
            # It's possible that the old URL was active before in the language domain/subpath
            # when there was no translation yet.
            for prev_choice in prev_choices:
                if obj.has_translation(prev_choice):
                    # Only dispatch() and render_to_response() can return a valid response,
                    # By breaking out here, this functionality can't be broken by users overriding render_to_response()
                    raise FallbackLanguageResolved(obj, prev_choice)

        return obj


class FallbackLanguageResolved(Exception):
    """
    An object was resolved in the fallback language, while it could be in the normal language.
    This exception is used internally to control code flow.
    """

    def __init__(self, object, correct_language):
        self.object = object
        self.correct_language = correct_language


class ArticleDetailView(TranslatableSlugMixin, generic.DetailView):

    def get_template_names(self):
        return [self.object.get_template()] + super().get_template_names()

    def render_to_response(self, context, **response_kwargs):
        if hasattr(self.request, 'toolbar'):
            self.request.toolbar.set_object(self.object)
        return super().render_to_response(context, **response_kwargs)



class ArticleListView(LanguageAndSectionMixin, generic.ListView):
    template_name = 'test_articles/article_list.html'

    def dispatch(self, request, *args, **kwargs):
        if hasattr(request, 'toolbar') and hasattr(request, 'current_page'):
            request.toolbar.set_object(request.current_page)
        return super().dispatch(request, *args, **kwargs)
