from django.contrib import admin, messages
from django.contrib.admin.options import IS_POPUP_VAR
from django.contrib.admin.utils import get_deleted_objects
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models.query import QuerySet
from django.http import HttpResponseRedirect
from django.utils.encoding import force_str
from django.utils.translation import gettext_lazy as _

from cms.cache.permissions import clear_permission_cache
from cms.models import CMSPlugin, Placeholder
from cms.toolbar.utils import get_object_preview_url
from cms.utils.i18n import get_site_language_from_request
from cms.utils.urlutils import admin_reverse

from test_articles import models, forms

def is_versioning_enabled():
    return True

@admin.register(models.Section)
class SectionAdmin(admin.ModelAdmin):
    pass


@admin.register(models.ArticleContent)
class ArticleContentAdmin(admin.ModelAdmin):
    form = forms.ArticleContentForm
    search_fields = ['title', 'slug']
    prepopulated_fields = {'slug': ('title',)}

    def get_changeform_initial_data(self, request):
        return {'language': get_site_language_from_request(request)}

    def view_on_site(self, obj):
        return obj.get_absolute_url()

    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        # Provide additional context to the changeform
        extra_context['is_versioning_enabled'] = is_versioning_enabled()
        return super().change_view(
            request, object_id, form_url, extra_context=extra_context,
        )

    @transaction.atomic
    def delete_view(self, request, object_id, extra_context=None):
        # This is an unfortunate copy/paste from django's delete view.
        # The reason is to add the descendant pages to the deleted objects list.
        opts = self.model._meta
        app_label = opts.app_label

        obj = self.get_object(request, object_id=object_id)

        if not self.has_delete_permission(request, obj):
            raise PermissionDenied

        if obj is None:
            raise self._get_404_exception(object_id)

        # Populate deleted_objects, a data structure of all related objects that
        # will also be deleted.
        objs = [obj]

        get_deleted_objects_additional_kwargs = {'request': request}
        (deleted_objects, model_count, perms_needed, protected) = get_deleted_objects(
            objs, admin_site=self.admin_site,
            **get_deleted_objects_additional_kwargs
        )

        # This is bad and I should feel bad.
        if 'placeholder' in perms_needed:
            perms_needed.remove('placeholder')

        if 'page content' in perms_needed:
            perms_needed.remove('page content')

        if request.POST and not protected:  # The user has confirmed the deletion.
            if perms_needed:
                raise PermissionDenied
            obj_display = force_str(obj)
            obj_id = obj.serializable_value(opts.pk.attname)
            self.log_deletion(request, obj, obj_display)
            self.delete_model(request, obj)

            if IS_POPUP_VAR in request.POST:
                popup_response_data = json.dumps({
                    'action': 'delete',
                    'value': str(obj_id),
                })
                return TemplateResponse(request, self.popup_response_template or [
                    'admin/%s/%s/popup_response.html' % (opts.app_label, opts.model_name),
                    'admin/%s/popup_response.html' % opts.app_label,
                    'admin/popup_response.html',
                ], {'popup_response_data': popup_response_data})

            self.message_user(
                request,
                _('The %(name)s "%(obj)s" was deleted successfully.') % {
                    'name': force_str(opts.verbose_name),
                    'obj': force_str(obj_display),
                },
                messages.SUCCESS,
            )
            query = self.get_preserved_filters(request)
            return HttpResponseRedirect(admin_reverse('test_articles_articlecontent_changelist') + '?' + query)

        object_name = force_str(opts.verbose_name)

        if perms_needed or protected:
            title = _("Cannot delete %(name)s") % {"name": object_name}
        else:
            title = _("Are you sure?")

        context = dict(
            self.admin_site.each_context(request),
            title=title,
            object_name=object_name,
            object=obj,
            deleted_objects=deleted_objects,
            model_count=dict(model_count).items(),
            perms_lacking=perms_needed,
            protected=protected,
            opts=opts,
            app_label=app_label,
            is_popup=(IS_POPUP_VAR in request.POST or
                      IS_POPUP_VAR in request.GET),
            to_field=None,
        )
        context.update(extra_context or {})
        return self.render_delete_form(request, context)

    def delete_model(self, request, obj):
        # Delete all plugins and placeholders
        obj._delete_placeholders()

        super().delete_model(request, obj)
        clear_permission_cache()
