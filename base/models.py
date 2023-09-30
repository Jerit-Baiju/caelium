from django.db import models
from django.utils import timezone
# Create your models here.


class Relationship(models.Model):
    male = models.OneToOneField('accounts.User', on_delete=models.SET_NULL, related_name='user_1', null=True, blank=True)
    female = models.OneToOneField('accounts.User', on_delete=models.SET_NULL, related_name='user_2', null=True, blank=True)
    room = models.CharField(max_length=20, unique=True, blank=True, null=True)
    anniversary = models.DateField(default=timezone.now, null=True, blank=True, editable=True)

    def __str__(self):
        return str(f'{self.male} & {self.female}')
