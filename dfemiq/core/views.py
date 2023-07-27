from django.shortcuts import render
from django.views.generic import TemplateView, ListView, DetailView
from django.views.generic.edit import CreateView, UpdateView, FormView
from django.views.generic.base import RedirectView
from django.http import HttpResponseRedirect, HttpResponse
from django.urls import reverse_lazy
from django.conf import settings
from django.core.mail import send_mail, send_mass_mail, EmailMessage
from . import forms, models
from django.contrib.auth.models import User
import random
from datetime import datetime, timedelta, date
import pdfkit
import io
from django.core.paginator import Paginator



def update_stock(stocks, pay_state):
    for stock in stocks:
        stock.sell_state = 'sold'
        stock.pay_state = pay_state
        stock.save()

def update_pay(stocks):
    for stock in stocks:
        if stock.pay_state == 'paid':
            stock.pay_state = 'not paid'
        else:
            stock.pay_state = 'paid'
        stock.save()

def update_sale(stocks):
    for stock in stocks:
        if stock.sell_state == 'sold':
            stock.sell_state = 'not sold'
        else:
            stock.sell_state = 'sold'
        stock.save()


class home(TemplateView):
    template_name = 'home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['client'] = 'home'
        return context


class dashboard(TemplateView):
    template_name = 'dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['client'] = 'dashboard'
        context['products'] = len(models.product.objects.all())
        context['sales'] = sum([sum([invoice_item.number*invoice_item.product.price for invoice_item in models.invoice_item.objects.filter(invoice=invoice)]) for invoice in models.invoice.objects.all()])
        context['invoices'] = len(models.invoice.objects.all())
        context['available_stock'] = sum([ps.product.price for ps in models.product_stock.objects.filter(sell_state="not sold")])
        context['today_sales'] = sum([sum([invoice_item.number*invoice_item.product.price for invoice_item in models.invoice_item.objects.filter(invoice=invoice, date=date.today())]) for invoice in models.invoice.objects.filter(date=date.today())])
        context['today_invoices'] = len(models.invoice.objects.filter(date=date.today()))
        return context


class products(CreateView):
    model = models.product
    fields = ['image']
    template_name = 'products.html'

    def get_success_url(self, **kwargs):
        return reverse_lazy('products', kwargs={'page': 1})

    def form_valid(self, form, **kwargs):
        self.object = form.save(commit=False)
        if 'create' in self.request.POST:
            self.object.name = self.request.POST.get("name")
            self.object.price = self.request.POST.get("price")
            self.object.save()
        elif 'updateimage' in self.request.POST:
            product = models.product.objects.get(id=self.request.POST.get("product_id"))
            product.image = form.cleaned_data['image']
            product.save()
        return HttpResponseRedirect(self.get_success_url())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if 'update' in self.request.GET:
            product = models.product.objects.get(id=self.request.GET.get("product_id"))
            product.name = self.request.GET.get("name")
            product.price = int(self.request.GET.get("price"))
            product.save()
        elif 'updatestock' in self.request.GET:
            product = models.product.objects.get(id=self.request.GET.get("product_id"))
            stock = int(self.request.GET.get("stock"))
            models.product_stock.objects.filter(product=product).delete()
            list(map(lambda i: models.product_stock.objects.create(product=product), list(range(stock))))
        elif 'delete' in self.request.GET:
            product_id = self.request.GET.get("product_id")
            models.product.objects.filter(id=product_id).delete()

        query = self.request.GET.get("q")
        if query is not None:
            products = models.product.objects.filter(name__icontains=query)
        else:
            products = models.product.objects.all()
        object_list = [(product, len(models.product_stock.objects.filter(product=product, sell_state='not sold'))) for product in products]
        paginated_list = Paginator(object_list, 10)
        page_num = self.kwargs['page']
        context['page'] = paginated_list.page(page_num)
        context['client'] = 'products'
        return context


class sales(FormView):
    form_class = forms.submitForm
    template_name = 'sales.html'

    def get_success_url(self, **kwargs):
        if self.go == 'invoice':
            return reverse_lazy('print_invoice', kwargs={'pk': self.invoice_id})
        else:
            return reverse_lazy('sales', kwargs={'page': 1})

    def form_valid(self, form, **kwargs):
        if 'sale_number' in self.request.POST:
            product = models.product.objects.get(id=self.request.POST.get("product_id"))
            number = self.request.POST.get("number")
            sales = self.request.session.get('sales', None)
            self.go = 'sales'
            if sales is not None:
                self.request.session['sales'] = sales + f'{product.id}/{number}:'
            else:
                self.request.session['sales'] = f'{product.id}/{number}:'
        elif 'submit_sale' in self.request.POST:
            customer_name = self.request.POST.get("customer_name")
            pay_state = self.request.POST.get("pay_state")
            sales = self.request.session.get('sales', None)
            intended_sales = [{'product': models.product.objects.get(id=sl.split('/')[0]), 'number': int(sl.split('/')[1]), 'stock': len(models.product_stock.objects.filter(product=models.product.objects.get(id=sl.split('/')[0]), sell_state="not sold"))} for sl in sales.split(":") if sl.split('/')[0]]
            for pro_num in intended_sales:
                if pro_num['number'] > pro_num['stock']:
                    return HttpResponse(f"<h1>{pro_num['product'].name} available is less than {pro_num['number']}</h1>")
            list(map(lambda pro_num: update_stock(models.product_stock.objects.filter(product=pro_num['product'], sell_state="not sold")[0:pro_num['number']], pay_state), intended_sales))
            invoice = models.invoice.objects.create(customer_name=customer_name, pay_state=pay_state)
            for pro_num in intended_sales:
                models.invoice_item.objects.create(invoice=invoice, product=pro_num['product'], number=pro_num['number'])
            self.invoice_id = invoice.id
            self.go = 'invoice'
            self.request.session['sales'] = None

            receipt_link = f'https://dfemiq.pythonanywhere.com/print_invoice/{invoice.id}'
            subject = 'sales at dfemiq'
            message = f'view the invoice at {receipt_link}'
            total = sum([prn['product'].price*prn['number'] for prn in intended_sales])
            for pro_num in intended_sales:
                message += f"\n{pro_num['number']} {pro_num['product'].name} cost {pro_num['product'].price*pro_num['number']} \npay state {pay_state}"
            message = message + f"\n total payment: {total}"
            mail = EmailMessage(subject, message, settings.EMAIL_HOST_USER, ['modupeadegbola24@gmail.com'])
            mail.send(fail_silently=False)
        return HttpResponseRedirect(self.get_success_url())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        query = self.request.GET.get("q")
        if query is not None:
            products = models.product.objects.filter(name__icontains=query)
        else:
            products = models.product.objects.all()
        object_list = [{'product': product, 'number': len(models.product_stock.objects.filter(product=product, sell_state='sold')), 'stock': len(models.product_stock.objects.filter(product=product, sell_state="not sold"))} for product in products]
        paginated_list = Paginator(object_list, 10)
        page_num = self.kwargs['page']
        context['page'] = paginated_list.page(page_num)
        context['client'] = 'sales'
        sales = self.request.session.get('sales', None)
        if sales is not None:
            context['intended_sales'] = [{'product': models.product.objects.get(id=sl.split('/')[0]), 'number': sl.split('/')[1]} for sl in sales.split(":") if sl.split('/')[0]]
            context['total_intended_cost'] = sum([int(ins['number'])*ins['product'].price for ins in context['intended_sales']])
        else:
            context['intended_sales'] = None
            context['total_intended_cost'] = 0

        context['available_stock'] = sum([ps.product.price for ps in models.product_stock.objects.filter(sell_state="not sold")])
        context['total_sales'] = sum([sum([invoice_item.number*invoice_item.product.price for invoice_item in models.invoice_item.objects.filter(invoice=invoice)]) for invoice in models.invoice.objects.all()])
        context['total_debt'] = sum([sum([invoice_item.number*invoice_item.product.price for invoice_item in models.invoice_item.objects.filter(invoice=invoice)]) for invoice in models.invoice.objects.filter(pay_state="not paid")])
        context['total_paid'] = sum([sum([invoice_item.number*invoice_item.product.price for invoice_item in models.invoice_item.objects.filter(invoice=invoice)]) for invoice in models.invoice.objects.filter(pay_state="paid")])
        return context


class bulk_sale(FormView):
    form_class = forms.submitForm
    template_name = "bulk_sale.html"

    def get_success_url(self, **kwargs):
        return reverse_lazy('sales', kwargs={'page': 1})

    def form_valid(self, form, **kwargs):
        product_ids = self.request.POST.getlist("product_id")
        numbers = [numx for numx in self.request.POST.getlist("number") if numx != '']
        for p_id, num in zip(product_ids, numbers):
            sales = self.request.session.get('sales', None)
            if sales is not None:
                self.request.session['sales'] = sales + f'{p_id}/{num}:'
            else:
                self.request.session['sales'] = f'{p_id}/{num}:'
        return HttpResponseRedirect(self.get_success_url())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['object_list'] = models.product.objects.all()
        context['client'] = 'bulk_sales'
        return context


class delete_int_sale(RedirectView):
    permanent = False
    query_string = True
    pattern_name = 'sales'

    def get_redirect_url(self, *args, **kwargs):
        product_id = self.kwargs['id']
        if product_id == 'all':
            self.request.session['sales'] = None
        else:
            salex = [sl for sl in self.request.session.get('sales', None).split(":") if str(product_id) not in sl.split("/")[0]]
            self.request.session['sales'] = ":".join(salex)
        return super().get_redirect_url(1)


class invoices(FormView):
    form_class = forms.submitForm
    template_name = 'invoices.html'

    def get_success_url(self, **kwargs):
        return reverse_lazy('invoices', kwargs={'page': 1})

    def form_valid(self, form, **kwargs):
        if 'create' in self.request.POST:
            customer_name = self.request.POST.get("customer_name")
            pay_state = self.request.POST.get("pay_state")
            models.invoice.objects.create(customer_name=customer_name, pay_state=pay_state)
        elif 'add_item' in self.request.POST:
            models.invoice_item.objects.create(invoice=models.invoice.objects.get(id=self.request.POST.get("invoice_id")), product=models.product.objects.get(id=self.request.POST.get("product_id")), number=self.request.POST.get("number"))
        return HttpResponseRedirect(self.get_success_url())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if 'update' in self.request.GET:
            invoice_id = self.request.GET.get("invoice_id")
            customer_name = self.request.GET.get("customer_name")
            models.invoice.objects.filter(id=invoice_id).update(customer_name=customer_name)
        elif 'delete' in self.request.GET:
            invoice_id = self.request.GET.get("invoice_id")
            models.invoice.objects.filter(id=invoice_id).delete()
        elif 'delete_item' in self.request.GET:
            invoice_item_id = self.request.GET.get("invoice_item_id")
            models.invoice_item.objects.filter(id=invoice_item_id).delete()
        query = self.request.GET.get("q")
        if 'today' in self.request.GET:
            context['day'] = 'today'
            invoices = models.invoice.objects.filter(pay_state="paid", date=date.today())
        elif 'yesterday' in self.request.GET:
            context['day'] = 'yesterday'
            invoices = models.invoice.objects.filter(pay_state="paid", date=date.today()-timedelta(days=1))
        elif 'daybefore' in self.request.GET:
            context['day'] = 'day before yesterday'
            invoices = models.invoice.objects.filter(pay_state="paid", date=date.today()-timedelta(days=2))
        elif 'dates' in self.request.GET:
            context['day'] = 'dates'
            fro, to = context['fro'], context['to'] = self.request.GET.get('fro'), self.request.GET.get('to')
            invoices = models.invoice.objects.filter(pay_state="paid", date__range=[fro, to])
        elif query is not None:
            invoices = models.invoice.objects.filter(pay_state="paid", customer_name__icontains=query)
        else:
            invoices = models.invoice.objects.filter(pay_state="paid")
        object_list = [{'invoice': invoice, 'items': models.invoice_item.objects.filter(invoice=invoice), 'total': sum([invit.product.price * invit.number for invit in models.invoice_item.objects.filter(invoice=invoice)])} for invoice in invoices]
        paginated_list = Paginator(object_list, 10)
        page_num = self.kwargs['page']
        context['page'] = paginated_list.page(page_num)
        context['client'] = 'invoices'
        context['products'] = models.product.objects.all()

        context['available_stock'] = sum([ps.product.price for ps in models.product_stock.objects.filter(sell_state="not sold")])
        context['total_sales'] = sum([sum([invoice_item.number*invoice_item.product.price for invoice_item in models.invoice_item.objects.filter(invoice=invoice)]) for invoice in models.invoice.objects.all()])
        context['total_debt'] = sum([sum([invoice_item.number*invoice_item.product.price for invoice_item in models.invoice_item.objects.filter(invoice=invoice)]) for invoice in models.invoice.objects.filter(pay_state="not paid")])
        context['total_paid'] = sum([sum([invoice_item.number*invoice_item.product.price for invoice_item in models.invoice_item.objects.filter(invoice=invoice)]) for invoice in models.invoice.objects.filter(pay_state="paid")])
        return context


class debt_invoices(FormView):
    template_name = 'debt_invoices.html'
    form_class = forms.submitForm

    def get_success_url(self, **kwargs):
        return reverse_lazy('debt_invoices', kwargs={'page': 1})

    def form_valid(self, form, **kwargs):
        if 'create' in self.request.POST:
            customer_name = self.request.POST.get("customer_name")
            pay_state = "not paid"
            models.invoice.objects.create(customer_name=customer_name, pay_state=pay_state)
        elif 'add_item' in self.request.POST:
            models.invoice_item.objects.create(invoice=models.invoice.objects.get(id=self.request.POST.get("invoice_id")), product=models.product.objects.get(id=self.request.POST.get("product_id")), number=self.request.POST.get("number"))
        return HttpResponseRedirect(self.get_success_url())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if 'update' in self.request.GET:
            invoice_id = self.request.GET.get("invoice_id")
            customer_name = self.request.GET.get("customer_name")
            models.invoice.objects.filter(id=invoice_id).update(customer_name=customer_name)
        elif 'delete' in self.request.GET:
            invoice_id = self.request.GET.get("invoice_id")
            models.invoice.objects.filter(id=invoice_id).delete()
        elif 'delete_item' in self.request.GET:
            invoice_item_id = self.request.GET.get("invoice_item_id")
            models.invoice_item.objects.filter(id=invoice_item_id).delete()
        query = self.request.GET.get("q")
        if 'today' in self.request.GET:
            context['day'] = 'today'
            invoices = models.invoice.objects.filter(pay_state="not paid", date=date.today())
        elif 'yesterday' in self.request.GET:
            context['day'] = 'yesterday'
            invoices = models.invoice.objects.filter(pay_state="not paid", date=date.today()-timedelta(days=1))
        elif 'daybefore' in self.request.GET:
            context['day'] = 'day before yesterday'
            invoices = models.invoice.objects.filter(pay_state="not paid", date=date.today()-timedelta(days=2))
        elif 'dates' in self.request.GET:
            context['day'] = 'dates'
            fro, to = context['fro'], context['to'] = self.request.GET.get('fro'), self.request.GET.get('to')
            invoices = models.invoice.objects.filter(pay_state="not paid", date__range=[fro, to])
        elif query is not None:
            invoices = models.invoice.objects.filter(pay_state="not paid", customer_name__icontains=query)
        else:
            invoices = models.invoice.objects.filter(pay_state="not paid")
        object_list = [{'invoice': invoice, 'items': models.invoice_item.objects.filter(invoice=invoice), 'total': sum([invit.product.price * invit.number for invit in models.invoice_item.objects.filter(invoice=invoice)])} for invoice in invoices]
        paginated_list = Paginator(object_list, 10)
        page_num = self.kwargs['page']
        context['page'] = paginated_list.page(page_num)
        context['client'] = 'debt_invoices'
        context['products'] = models.product.objects.all()

        context['available_stock'] = sum([ps.product.price for ps in models.product_stock.objects.filter(sell_state="not sold")])
        context['total_sales'] = sum([sum([invoice_item.number*invoice_item.product.price for invoice_item in models.invoice_item.objects.filter(invoice=invoice)]) for invoice in models.invoice.objects.all()])
        context['total_debt'] = sum([sum([invoice_item.number*invoice_item.product.price for invoice_item in models.invoice_item.objects.filter(invoice=invoice)]) for invoice in models.invoice.objects.filter(pay_state="not paid")])
        context['total_paid'] = sum([sum([invoice_item.number*invoice_item.product.price for invoice_item in models.invoice_item.objects.filter(invoice=invoice)]) for invoice in models.invoice.objects.filter(pay_state="paid")])
        return context


class pay_toggle(RedirectView):
    permanent = False
    query_string = True
    pattern_name = 'debt_invoices'

    def get_redirect_url(self, *args, **kwargs):
        invoice = models.invoice.objects.get(id=self.kwargs['id'])
        invoice_items = models.invoice_item.objects.filter(invoice=invoice)
        if invoice.pay_state == 'paid':
            invoice.pay_state = 'not paid'
            list(map(lambda invoice_item: update_pay(models.product_stock.objects.filter(product=invoice_item.product, sell_state="sold", pay_state="not_paid")[0:invoice_item.number]), invoice_items))
        else:
            invoice.pay_state = 'paid'
            list(map(lambda invoice_item: update_pay(models.product_stock.objects.filter(product=invoice_item.product, sell_state="sold", pay_state="not_paid")[0:invoice_item.number]), invoice_items))
        invoice.save()
        return super().get_redirect_url(1)


class undo_sale(RedirectView):
    permanent = False
    query_string = True
    pattern_name = 'debt_invoices'

    def get_redirect_url(self, *args, **kwargs):
        invoice = models.invoice.objects.get(id=self.kwargs['id'])
        invoice_items = models.invoice_item.objects.filter(invoice=invoice)
        list(map(lambda invoice_item: update_sale(models.product_stock.objects.filter(product=invoice_item.product, sell_state="sold")[0:invoice_item.number]), invoice_items))
        invoice.delete()
        return super().get_redirect_url(1)


class print_invoice(DetailView):
    model = models.invoice
    template_name = 'invoice_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['invoice_items'] = models.invoice_item.objects.filter(invoice=self.object)
        context['total'] = sum([invit.product.price * invit.number for invit in models.invoice_item.objects.filter(invoice=self.object)])
        context['client'] = 'print_invoice'
        return context



