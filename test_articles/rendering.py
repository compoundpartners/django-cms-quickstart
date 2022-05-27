from django.conf import settings
from django.http import Http404
from django.template.response import TemplateResponse
from django.urls import Resolver404, resolve, reverse

from test_articles.cache import set_article_cache


def render_article(request, article, current_language, slug, template):
    """
    Renders a article
    """
    context = {}
    context['lang'] = current_language
    context['article'] = article

    response = TemplateResponse(request, template, context)
    response.add_post_render_callback(set_article_cache)

    return response

def _handle_no_article(request):
    try:
        #add a $ to the end of the url (does not match on the cms anymore)
        resolve('%s$' % request.path)
    except Resolver404 as e:
        # raise a django http 404 article
        exc = Http404(dict(path=request.path, tried=e.args[0]['tried']))
        raise exc
    raise Http404('CMS Page not found: %s' % request.path)

def render_article_content(request, article_content):
    language = article_content.language
    request.current_article = article = article_content.article
    article.translation_cache[language] = article_content
    return render_article(request, article, language, article.get_slug(language), article.get_template(language))
