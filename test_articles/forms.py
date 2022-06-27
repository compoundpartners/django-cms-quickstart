from django import forms

from test_articles import models


class ArticleContentForm(forms.ModelForm):
    section = forms.ModelChoiceField(queryset=models.Section.objects.exclude(namespace=models.Section.default_namespace))

    class Meta:
        model = models.ArticleContent
        fields = (
            'section',
            'article',
            'language',
            'title',
            'slug',
            'meta_description',
            'template',
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.fields.get('article'):
            self.fields['article'].widget = forms.HiddenInput()
            self.fields['article'].required = False
        if self.fields.get('language'):
            self.fields['language'].widget = forms.HiddenInput()
        if self.instance.article and self.instance.article.section:
            self.fields['section'].initial = 1#self.instance.article.section

    def create_or_update_grouper(self, obj, **kwargs):
        '''
        If a grouper doesn't yet exist for the instance we may need to create one.
        :param obj: a article content instance
        :returns obj: a article content instance that may have a grouper attached.
        '''
        # Check whether the form used has the grouper attribute, as overrides do not.
        if isinstance(obj, self._meta.model) and not getattr(obj, 'article'):
            obj.article = models.Article.objects.create(**kwargs)
        else:
            obj.article.update(**kwargs)
        return obj

    def save(self, **kwargs):
        obj = super().save(commit=False)
        commit = kwargs.get('commit', True)
        # Create the grouper if it doesn't exist
        obj = self.create_or_update_grouper(obj, section=self.cleaned_data['section'])

        if commit:
            obj.save()
            obj.article.save()
        return obj
