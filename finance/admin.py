from django.contrib import admin

from finance.models import Label, Transaction

# Register your models here.

admin.site.register(Label)
admin.site.register(Transaction)
