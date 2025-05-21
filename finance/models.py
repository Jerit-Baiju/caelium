from django.db import models
from django.db.models import Sum

from accounts.models import User

# Create your models here.


class Label(models.Model):
    name = models.CharField(max_length=50)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="labels", null=True, blank=True)

    def __str__(self):
        return f"{self.name}"


class Transaction(models.Model):
    TRANSACTION_TYPES = [
        ("income", "Income"),
        ("expense", "Expense"),
        ("float", "Float"),
    ]
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="transactions")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    type = models.CharField(max_length=10, choices=TRANSACTION_TYPES)
    description = models.TextField(blank=True, null=True)
    date = models.DateTimeField(blank=True, null=True)  # Allow user/API to set date
    label = models.ForeignKey(Label, on_delete=models.SET_NULL, null=True, blank=True, related_name="transactions")

    def __str__(self):
        return f"{self.owner} - {self.type} - {self.amount}"


class Account(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="accounts")
    name = models.CharField(max_length=100)
    account_number = models.CharField(max_length=50, unique=True)
    currency = models.CharField(max_length=3, default="USD", help_text="ISO 4217 currency code, e.g., USD, EUR, INR")
    minimum_balance = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.owner} - {self.name} ({self.account_number})"

    @property
    def original_balance(self):
        # The total balance as currently calculated
        income = self.transactions.filter(type="income").aggregate(total=Sum("amount"))["total"] or 0
        expense = self.transactions.filter(type="expense").aggregate(total=Sum("amount"))["total"] or 0
        float_amt = self.transactions.filter(type="float").aggregate(total=Sum("amount"))["total"] or 0
        return income - expense + float_amt

    @property
    def spendable_balance(self):
        # Spendable balance is the original balance minus the minimum balance
        return self.original_balance - self.minimum_balance

    @property
    def balance(self):
        # For backward compatibility, keep balance as original_balance
        return self.original_balance
