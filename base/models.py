from django.db import models

# Create your models here.


class Relationship(models.Model):
    male = models.OneToOneField('accounts.User', on_delete=models.SET_NULL, related_name='user_1', null=True, blank=True)
    female = models.OneToOneField('accounts.User', on_delete=models.SET_NULL, related_name='user_2', null=True, blank=True)
    anniversary = models.DateField(auto_now_add=True, null=True)

    def __str__(self):
        return str(f'{self.male} & {self.female}')
