from django.urls import re_path

from test_articles import views


urlpatterns = [
    re_path(
        r'^(?P<slug>[A-Za-z0-9_\-]+)/$',
        views.ArticleDetailView.as_view(),
        name='detail',
    ),
    re_path(
        r"^$",
        views.ArticleListView.as_view(),
        name='list'
    ),
]
