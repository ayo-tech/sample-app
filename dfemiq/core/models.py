from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
# Create your models here.


class product(models.Model):
    name = models.CharField(max_length=100, default="name here")
    image = models.ImageField(upload_to="uploads", default=None, null=True)
    price = models.PositiveIntegerField(default=0)
    date = models.DateTimeField(auto_now=True)
    submit = models.CharField(max_length=100, default="submit", null=True)


class product_stock(models.Model):
    product = models.ForeignKey(product, on_delete=models.CASCADE, default=None, null=True)
    sell_state = models.CharField(max_length=100, default="not sold")
    pay_state = models.CharField(max_length=100, default="not paid")
    date = models.DateTimeField(auto_now=True)


class invoice(models.Model):
    customer_name = models.CharField(max_length=100, default="customer name here")
    date = models.DateTimeField(auto_now=True)
    pay_state = models.CharField(max_length=100, default="not paid")


class invoice_item(models.Model):
    invoice = models.ForeignKey(invoice, on_delete=models.CASCADE, default=None, null=True)
    product = models.ForeignKey(product, on_delete=models.CASCADE, default=None, null=True)
    number = models.PositiveIntegerField(default=0)
    transaction_type = models.CharField(max_length=100, default="sold")
    date = models.DateTimeField(auto_now=True)
