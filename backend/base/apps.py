# Description: AppConfig configuration for the base canteen application.
from django.apps import AppConfig


class BaseConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'base'

class AccountsConfig(AppConfig):
    name = 'accounts'

