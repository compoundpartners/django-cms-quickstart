import copy
from logging import getLogger
from os.path import join

from django.contrib.auth import get_permission_codename
from django.db import models
from django.db.models.base import ModelState
from django.db.models.functions import Concat
from django.urls import reverse
from django.urls.exceptions import NoReverseMatch
from django.utils.encoding import force_str
from django.utils.functional import cached_property
from django.utils.timezone import now
from django.utils.translation import (
    get_language,
    override as force_language,
    gettext_lazy as _,
)

from cms import constants
from cms.exceptions import LanguageError
from cms.models.fields import PlaceholderRelationField
from cms.toolbar.utils import get_object_preview_url
from cms.utils import i18n
from cms.utils.conf import get_cms_setting
from cms.utils.page import get_clean_username
from cms.utils.i18n import get_current_language

from test_articles.managers import ArticleManager, ArticleContentManager

logger = getLogger(__name__)


class EmptyArticleContent():
    """
    Empty translation object, can be returned from Article.get_translation_obj() if required
    content object doesn't exists.
    """
    title = ""
    slug = ""
    meta_description = ""
    template = get_cms_setting('TEMPLATES')[0][0]

    def __init__(self, language):
        self.language = language

    def __nonzero__(self):
        # Python 2 compatibility
        return False

    def __bool__(self):
        # Python 3 compatibility
        return False

class Section(models.Model):
    default_namespace = 'all-articles'
    default_app_title = 'All articles'

    app_title = models.CharField(_('app title'), max_length=255)
    namespace = models.SlugField(_('namespace'), max_length=255)

    class Meta:
        default_permissions = ('add', 'change', 'delete')
        permissions = (
            ('view_section', 'Can view section'),
            ('publish_section', 'Can publish section'),
            ('edit_static_placeholder', 'Can edit static placeholders'),
        )
        verbose_name = _('section')
        verbose_name_plural = _('sections')
        app_label = 'test_articles'

    def __str__(self):
        return self.app_title


    @classmethod
    def get_default(cls):
        default, created = cls.objects.get_or_create(
            namespace=cls.default_namespace,
            defaults={'app_title':cls.default_app_title}
        )
        return default


class Article(models.Model):
    """
    A simple article model
    """

    created_by = models.CharField(
        _("created by"), max_length=constants.PAGE_USERNAME_MAX_LENGTH,
        editable=False)
    changed_by = models.CharField(
        _("changed by"), max_length=constants.PAGE_USERNAME_MAX_LENGTH,
        editable=False)
    creation_date = models.DateTimeField(auto_now_add=True)
    changed_date = models.DateTimeField(auto_now=True)

    section = models.ForeignKey('test_articles.Section', models.SET_NULL, blank=True, null=True)

    # Managers
    objects = ArticleManager()

    class Meta:
        default_permissions = ('add', 'change', 'delete')
        permissions = (
            ('view_article', 'Can view article'),
            ('publish_article', 'Can publish article'),
            ('edit_static_placeholder', 'Can edit static placeholders'),
        )
        verbose_name = _('article')
        verbose_name_plural = _('articles')
        app_label = 'test_articles'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.translation_cache = {}

    def __str__(self):
        try:
            title = self.get_title(fallback=True)
        except LanguageError:
            try:
                title = self.articlecontent_set.all()[0]
            except IndexError:
                title = None
        if title is None:
            title = u""
        return force_str(title)

    def __repr__(self):
        display = '<{module}.{class_name} id={id} object at {location}>'.format(
            module=self.__module__,
            class_name=self.__class__.__name__,
            id=self.pk,
            location=hex(id(self)),
        )
        return display

    def _clear_internal_cache(self):
        self.translation_cache = {}

        if hasattr(self, '_prefetched_objects_cache'):
            del self._prefetched_objects_cache

    def delete_translations(self, language=None):
        filters = {}
        if language:
            filters['languages'] = language
        self.articlecontent_set.filter(**filters).delete()

    def save(self, **kwargs):
        created = not bool(self.pk)
        from cms.utils.permissions import get_current_user_name
        self.changed_by = get_current_user_name()
        if created:
            self.created_by = self.changed_by

        super().save(**kwargs)

    def reload(self):
        """
        Reload a article from the database
        """
        return self.__class__.objects.get(pk=self.pk)

    def update(self, refresh=False, **data):
        cls = self.__class__
        cls.objects.filter(pk=self.pk).update(**data)

        if refresh:
            return self.reload()
        else:
            for field, value in data.items():
                setattr(self, field, value)
        return

    def has_translation(self, language):
        return self.articlecontent_set.filter(language=language).exists()

    def clear_cache(self, language=None, menu=False, placeholder=False):
        from test_articles.cache import invalidate_article_cache

        if get_cms_setting('ARTICLE_CACHE'):
            # Clears all the article caches
            invalidate_article_cache()

        if placeholder and get_cms_setting('PLACEHOLDER_CACHE'):
            assert language, 'language is required when clearing placeholder cache'

            placeholders = self.get_placeholders(language)

            for placeholder in placeholders:
                placeholder.clear_cache(language)

    def set_translation_cache(self):
        for translation in self.articlecontent_set.all():
            self.translation_cache.setdefault(translation.language, translation)

    def get_fallbacks(self, language):
        return i18n.get_fallback_languages(language)

    # ## ArticleContent object access

    def get_translation_obj(self, language=None, fallback=True, force_reload=False):
        """Helper function for accessing wanted / current translation.
        If wanted translation doesn't exists, EmptyArticleContent instance will be returned.
        """
        language = self._get_translation_cache(language, fallback, force_reload)
        if language in self.translation_cache:
            return self.translation_cache[language]

        return EmptyArticleContent(language)

    def get_translation_obj_attribute(self, attrname, language=None, fallback=True, force_reload=False):
        """Helper function for getting attribute or None from wanted/current translation.
        """
        try:
            attribute = getattr(self.get_translation_obj(language, fallback, force_reload), attrname)
            return attribute
        except AttributeError:
            return None


    def get_title(self, language=None, fallback=True, force_reload=False):
        """
        get the title of the article depending on the given language
        """
        return self.get_translation_obj_attribute("title", language, fallback, force_reload)

    def get_slug(self, language, fallback=True, force_reload=False):
        return self.get_translation_obj_attribute("slug", language, fallback, force_reload)

    def get_placeholders(self, language):
        article_translation = ArticleContent.objects.get(language=language, article=self)
        return article_translation.get_placeholders()

    def get_changed_date(self, language=None, fallback=True, force_reload=False):
        """
        get when this article was last updated
        """
        return self.get_translation_obj_attribute("changed_date", language, fallback, force_reload)

    def get_changed_by(self, language=None, fallback=True, force_reload=False):
        """
        get user who last changed this article
        """
        return self.get_translation_obj_attribute("changed_by", language, fallback, force_reload)

    def get_meta_description(self, language=None, fallback=True, force_reload=False):
        """
        get translation for the description meta tag for the article depending on the given language
        """
        return self.get_translation_obj_attribute("meta_description", language, fallback, force_reload)

    def _get_translation_cache(self, language, fallback, force_reload):
        def get_fallback_language(article, language):
            fallback_langs = i18n.get_fallback_languages(language)
            for lang in fallback_langs:
                if article.translation_cache.get(lang):
                    return lang

        if not language:
            language = get_language()

        force_reload = (force_reload or language not in self.translation_cache)
        if force_reload:
            translations = ArticleContent.objects.filter(article=self)
            for translation in translations:
                self.translation_cache[translation.language] = translation

        if self.translation_cache.get(language):
            return language


        use_fallback = all([
            fallback,
            not self.translation_cache.get(language),
            get_fallback_language(self, language)
        ])
        if use_fallback:
            # language can be in the cache but might be an EmptyArticleContent instance
            return get_fallback_language(self, language)
        return language

    @property
    def template(self):
        return self.get_translation_obj_attribute("template")

    def get_template(self, language=None, fallback=True, force_reload=False):
        translation = self.get_translation_obj(language, fallback, force_reload)
        if translation:
            return translation.get_template()
        return get_cms_setting('TEMPLATES')[0][0]

    def get_template_name(self):
        """
        get the textual name (2nd parameter in get_cms_setting('TEMPLATES'))
        of the template of this article or of the nearest
        ancestor. failing to find that, return the name of the default template.
        """
        template = self.get_template()
        for t in get_cms_setting('TEMPLATES'):
            if t[0] == template:
                return t[1]
        return _("default")


class ArticleContent(models.Model):
    TEMPLATE_DEFAULT = get_cms_setting('TEMPLATES')[0][0]

    template_choices = [(x, _(y)) for x, y in get_cms_setting('TEMPLATES')]

    # These are the fields whose values are compared when saving
    # a ArticleContent object to know if it has changed.
    editable_fields = [
        'title',
        'slug',
        'meta_description',
    ]

    language = models.CharField(_("language"), max_length=15, db_index=True)
    title = models.CharField(_("title"), max_length=255)
    slug = models.SlugField(_("slug"), max_length=255, db_index=True)
    meta_description = models.TextField(_("description"), blank=True, null=True,
                                        help_text=_("The text displayed in search engines."))
    article = models.ForeignKey(Article, on_delete=models.CASCADE, verbose_name=_("article"), related_name="articlecontent_set", null=True)
    creation_date = models.DateTimeField(_("creation date"), editable=False, default=now)

    # Placeholders (plugins)
    placeholders = PlaceholderRelationField()

    created_by = models.CharField(
        _("created by"), max_length=constants.PAGE_USERNAME_MAX_LENGTH,
        editable=False)
    changed_by = models.CharField(
        _("changed by"), max_length=constants.PAGE_USERNAME_MAX_LENGTH,
        editable=False)
    changed_date = models.DateTimeField(auto_now=True)

    template = models.CharField(_("template"), max_length=100, choices=template_choices,
                                help_text=_('The template used to render the content.'),
                                default=TEMPLATE_DEFAULT)

    objects = ArticleContentManager()

    class Meta:
        #default_permissions = []
        #unique_together = (('language', 'article'),)
        app_label = 'test_articles'

    def __str__(self):
        return u"%s (%s)" % (self.title, self.language)

    def __repr__(self):
        display = '<{module}.{class_name} id={id} object at {location}>'.format(
            module=self.__module__,
            class_name=self.__class__.__name__,
            id=self.pk,
            location=hex(id(self)),
        )
        return display

    def update(self, **data):
        cls = self.__class__
        cls.objects.filter(pk=self.pk).update(**data)

        for field, value in data.items():
            setattr(self, field, value)
        return

    def has_placeholder_change_permission(self, user):
        opts = Article._meta
        codename = opts.app_label + '.' + get_permission_codename('change', opts)
        return user.has_perm(codename)

    def get_placeholders(self):
        if not hasattr(self, '_placeholder_cache'):
            self._placeholder_cache = self.placeholders.all()
        return self._placeholder_cache

    def _delete_placeholders(self):
        from cms.models import CMSPlugin

        placeholders = self.get_placeholders()
        placeholder_ids = (placeholder.pk for placeholder in placeholders)
        plugins = CMSPlugin.objects.filter(placeholder__in=placeholder_ids, language=language)
        models.query.QuerySet.delete(plugins)
        placeholders.delete()
        delattr(self, '_placeholder_cache')


    def get_template(self):
        return self.template or get_cms_setting('TEMPLATES')[0][0]

    def get_template_name(self):
        """
        get the textual name (2nd parameter in get_cms_setting('TEMPLATES'))
        of the template of this translation. failing to find that, return the
        name of the default template.
        """
        template = self.get_template()
        for t in get_cms_setting('TEMPLATES'):
            if t[0] == template:
                return t[1]
        return _("default")

    def get_absolute_url(self):
        try:
            return reverse('%s:detail' % (self.article.section or Section.default_namespace), kwargs={'slug': self.slug})
        except NoReverseMatch:
            try:
                return reverse('%s:detail' % Section.default_namespace, kwargs={'slug': self.slug})
            except NoReverseMatch:
                return get_object_preview_url(self, self.language)

    def copy(self):
        new = copy.copy(self)
        new.pk = None
        new.save()

        for placeholder in self.placeholders.all():
            # copy the placeholders (and plugins on those placeholders!)
            new_placeholder = new.placeholders.create(
                slot=placeholder.slot,
                default_width=placeholder.default_width,
            )
            placeholder.copy_plugins(new_placeholder, language=self.language)
        self.article.translation_cache[new.language] = new
        return new
