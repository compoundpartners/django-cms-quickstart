# -*- coding: utf-8 -*-

from __future__ import unicode_literals

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.urls import reverse, NoReverseMatch
from django.utils.translation import (
    ugettext as _, get_language_from_request, override)

from cms.toolbar_base import CMSToolbar
from cms.toolbar_pool import toolbar_pool
from cms.utils.i18n import get_language_tuple, get_language_dict
from cms.utils.urlutils import admin_reverse, add_url_parameters
from menus.utils import DefaultLanguageChanger


from test_articles import models

from cms.cms_toolbars import (
    ADMIN_MENU_IDENTIFIER,
    LANGUAGE_MENU_IDENTIFIER,
)

ADD_ARTICLE_LANGUAGE_BREAK = "Add article language Break"


@toolbar_pool.register
class ArticleToolbar(CMSToolbar):
    watch_models = [models.ArticleContent,]
    supported_apps = ('test_articles',)

    # def get_on_delete_redirect_url(self, article, language):
        # if article.section:
            # try:
                # reverse('{0}:list'.format(namespace))
            # except:
                # namespace = NewsBlogConfig.default_namespace
        # else:
            # namespace = models.Section.default_namespace
        # with override(language):
            # url = reverse(
                # '{0}:list'.format(namespace))
        # return url

    def _get_config(self):
        return getattr(self.request, 'article_config', None)

    def populate(self):
        self.page = self.request.current_page
        config = self._get_config()
        if not config:
            # Do nothing if there is no NewsBlog section to work with
            return

        user = getattr(self.request, 'user', None)
        try:
            view_name = self.request.resolver_match.view_name
        except AttributeError:
            view_name = None

        if user and view_name:
            language = get_language_from_request(self.request, check_path=True)


            # get existing admin menu
            admin_menu = self.toolbar.get_or_create_menu(ADMIN_MENU_IDENTIFIER)

            # add new Articles item
            admin_menu.add_sideframe_item(_('Articles'), url='/admin/test_articles/articlecontent/', position=0)

            # If we're on an Article detail page, then get the article
            if view_name == '{0}:detail'.format(config.namespace):
                kwargs = self.request.resolver_match.kwargs
                if 'pk' in kwargs:
                    article = Article.all_objects.filter(pk=kwargs['pk']).first()
                elif 'slug' in kwargs:
                    filter_kwargs = {'slug': kwargs['slug'], 'language': language}
                    article = models.ArticleContent.objects.filter(**filter_kwargs).first()
            else:
                article = None
            menu = self.toolbar.get_or_create_menu('test_articles_app', config.app_title)

            change_config_perm = user.has_perm(
                'test_articles.change_section')
            add_config_perm = user.has_perm(
                'test_articles.add_section')
            config_perms = [change_config_perm, add_config_perm]

            change_article_perm = user.has_perm(
                'test_articles.change_articlecontent')
            delete_article_perm = user.has_perm(
                'test_articles.delete_articlecontent')
            add_article_perm = user.has_perm('test_articles.add_articlecontent')
            article_perms = [change_article_perm, add_article_perm,
                             delete_article_perm, ]

            if change_config_perm:
                url_args = {}
                if language:
                    url_args = {'language': language, }
                url = add_url_parameters(
                    admin_reverse('test_articles_section_change',
                                  args=[config.pk, ]),
                    **url_args)

                menu.add_modal_item(_('Edit section'), url=url)

            if any(config_perms) and any(article_perms):
                menu.add_break()

            if change_article_perm:
                url_args = {}
                if config and config.namespace != models.Section.default_namespace:
                    url_args = {'section__id__exact': config.pk}
                url = add_url_parameters(
                    admin_reverse('test_articles_articlecontent_changelist'),
                    **url_args)
                menu.add_sideframe_item(_('Article list'), url=url)

            if add_article_perm:
                url_args = {'section': config.pk}
                if language:
                    url_args.update({'language': language, })
                url = add_url_parameters(
                    admin_reverse('test_articles_articlecontent_add'),
                    **url_args)
                menu.add_modal_item(_('Add new article'), url=url)

            if change_article_perm and article:
                url_args = {}
                if language:
                    url_args = {'language': language, }
                url = add_url_parameters(
                    admin_reverse('test_articles_articlecontent_change',
                                  args=[article.pk, ]),
                    **url_args)
                menu.add_modal_item(_('Edit this article'), url=url,
                                    active=True)

            # if delete_article_perm and article:
                # redirect_url = self.get_on_delete_redirect_url(
                    # article, language=language)
                # url = add_url_parameters(
                    # admin_reverse('test_articles_articlecontent_delete',
                                  # args=[article.pk, ]),
                    # **url_args)
                # menu.add_modal_item(_('Delete this article'), url=url,
                                    # on_close=redirect_url)

