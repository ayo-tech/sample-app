from django import forms


class submitForm(forms.Form):
    submit = forms.CharField(initial="submit")


class productForm(forms.Form):
    name = forms.CharField(initial="product name")
    image = forms.ImageField()
    price = forms.IntegerField(initial=0)