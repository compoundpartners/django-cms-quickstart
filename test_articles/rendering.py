from django.template.response import TemplateResponse


from test_articles.cache import set_article_cache
from test_articles import models


def render_article_content(request, article_content):
    language = article_content.language
    article = article_content.article
    article.translation_cache[language] = article_content
    context = {}
    context['lang'] = language
    context['article'] = article
    request.article_config = article.section or models.Section.get_default()

    response = TemplateResponse(request, article_content.get_template(), context)
    response.add_post_render_callback(set_article_cache)
    return response
