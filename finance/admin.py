from django.contrib import admin

from finance.models import Account, Label, Transaction

# Register your models here.

admin.site.register(Label)
admin.site.register(Transaction)
admin.site.register(Account)
