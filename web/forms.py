"""Формы сайта: только разбор полей, бизнес-проверки делают сервисы."""

from django import forms

from warehouse.common.dto import NewEmployee, RoleDTO, WarehouseDTO


class RegisterForm(forms.Form):
    last_name = forms.CharField(label='Фамилия', max_length=100)
    first_name = forms.CharField(label='Имя', max_length=100)
    login = forms.CharField(label='Логин', max_length=100)
    password = forms.CharField(label='Пароль', widget=forms.PasswordInput(render_value=False))
    password_repeat = forms.CharField(label='Повтор пароля', widget=forms.PasswordInput(render_value=False))
    warehouse_id = forms.TypedChoiceField(label='Склад', coerce=int)
    role_id = forms.TypedChoiceField(label='Роль', coerce=int)

    def __init__(self, *args, warehouses: list[WarehouseDTO], roles: list[RoleDTO], **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['warehouse_id'].choices = [(w.id, w.title) for w in warehouses]
        self.fields['role_id'].choices = [(r.id, r.name) for r in roles]
        self.fields['login'].widget.attrs['autocomplete'] = 'off'
        for name in ('password', 'password_repeat'):
            self.fields[name].widget.attrs['autocomplete'] = 'new-password'
        for field in self.fields.values():
            field.widget.attrs['class'] = 'input'

    def clean(self):
        data = super().clean()
        if data.get('password') and data.get('password') != data.get('password_repeat'):
            self.add_error('password_repeat', 'Пароли не совпадают')
        return data

    def to_new_employee(self) -> NewEmployee:
        data = self.cleaned_data
        return NewEmployee(
            first_name=data['first_name'],
            last_name=data['last_name'],
            login=data['login'],
            password=data['password'],
            warehouse_id=data['warehouse_id'],
            role_id=data['role_id'],
        )
