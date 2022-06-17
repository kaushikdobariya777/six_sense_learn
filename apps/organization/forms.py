from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.db import transaction, InternalError
from django_tenants.utils import schema_context


class OrgForm(forms.ModelForm):
    email = forms.EmailField(required=True)
    password = forms.CharField(min_length=8, max_length=36, widget=forms.PasswordInput, required=True)

    def save(self, commit=True):
        try:
            email = self.cleaned_data.pop("email") if "email" in self.cleaned_data else ""
            password = self.cleaned_data.pop("password") if "password" in self.cleaned_data else ""
            instance = super(OrgForm, self).save(commit=commit)
            instance.save()
            if email and password:
                with schema_context(self.cleaned_data.get("schema_name")):
                    user_model = get_user_model()
                    user = user_model.objects.create(email=email, is_superuser=True, is_staff=True)
                    user.password = make_password(password)
                    user.save()
            return instance

        except InternalError as e:
            transaction.rollback()

    class Meta:
        fields = "__all__"
