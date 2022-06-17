import uuid

from cms.signals import pre_obj_operation, post_obj_operation
from test_articles.models import Article


def send_pre_operation(request, operation, sender=Article, **kwargs):
    token = str(uuid.uuid4())
    pre_obj_operation.send(
        sender=sender,
        operation=operation,
        request=request,
        token=token,
        **kwargs
    )
    return token


def send_post_operation(request, operation, token, sender=Article, **kwargs):
    post_obj_operation.send(
        sender=sender,
        operation=operation,
        request=request,
        token=token,
        **kwargs
    )
