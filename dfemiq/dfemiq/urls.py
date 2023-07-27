"""
URL configuration for dfemiq project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from core import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path('auth/', include('django.contrib.auth.urls')),
    path("", views.home.as_view(), name='home'),
    path("dashboard", views.dashboard.as_view(), name='dashboard'),
    path("sales/<int:page>", views.sales.as_view(), name='sales'),
    path("products/<int:page>", views.products.as_view(), name='products'),
    path("invoices/<int:page>", views.invoices.as_view(), name='invoices'),
    path("delete_int_sale/<str:id>", views.delete_int_sale.as_view(), name='delete_int_sale'),
    path("print_invoice/<int:pk>", views.print_invoice.as_view(), name='print_invoice'),
    path("debt_invoices/<int:page>", views.debt_invoices.as_view(), name='debt_invoices'),
    path("pay_toggle/<str:id>", views.pay_toggle.as_view(), name='pay_toggle'),
    path("undo_sale/<str:id>", views.undo_sale.as_view(), name='undo_sale'),
    path("bulk_sale/<int:page>", views.bulk_sale.as_view(), name='bulk_sale'),

]
