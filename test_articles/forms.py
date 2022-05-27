from django import forms

from test_articles import models


class ArticleContentForm(forms.ModelForm):

    class Meta:
        model = models.ArticleContent
        fields = (
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

    def create_grouper(self, obj):
        '''
        If a grouper doesn't yet exist for the instance we may need to create one.
        :param obj: a article content instance
        :returns obj: a article content instance that may have a grouper attached.
        '''
        # Check whether the form used has the grouper attribute, as overrides do not.
        if isinstance(obj, self._meta.model) and not getattr(obj, 'article'):
            obj.article = models.Article.objects.create()
        return obj

    def save(self, **kwargs):
        obj = super().save(commit=False)
        commit = kwargs.get('commit', True)
        # Create the grouper if it doesn't exist
        obj = self.create_grouper(obj)

        if commit:
            obj.save()
        return obj
