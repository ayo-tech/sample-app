from django.contrib import admin

# Register your models here.
from . import models



admin.site.register(models.product)
admin.site.register(models.product_stock)
admin.site.register(models.invoice)
admin.site.register(models.invoice_item)