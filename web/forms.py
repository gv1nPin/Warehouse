"""Формы приложения."""

from django import forms

from .mocks import PRODUCTS


class ProductForm(forms.Form):
    name = forms.CharField(label='Название', max_length=100)
    price = forms.IntegerField(label='Цена, ₽', min_value=1)

    def clean_name(self):
        name = self.cleaned_data['name'].strip()

        if not name:
            raise forms.ValidationError('Название не может состоять из одних пробелов.')

        # проверка на дубликат по моку (самодельная замена unique в БД)
        if any(p['name'].lower() == name.lower() for p in PRODUCTS):
            raise forms.ValidationError('Такой товар уже есть в списке.')

        return name
