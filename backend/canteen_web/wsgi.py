# Description: WSGI entry-point configuration for web server deployment.
"""
WSGI config for canteen_web project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'canteen_web.settings')

application = get_wsgi_application()
