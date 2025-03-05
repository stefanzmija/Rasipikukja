from django import forms

CATEGORIES = [
    ('plumber', 'Plumber'),
    ('electrician', 'Electrician'),
    ('gardener', 'Gardener'),
]

class RegistrationForm(forms.Form):
    email = forms.EmailField(label="Email")
    password = forms.CharField(widget=forms.PasswordInput, label="Password")
    user_type = forms.ChoiceField(
        choices=[('client', 'Client'), ('repairman', 'Repairman')],
        widget=forms.RadioSelect,
        label="I am a:"
    )
    repair_category = forms.ChoiceField(
        choices=CATEGORIES,
        required=False,
        label="Repair Category (if repairman)"
    )
