import os
import pytest
from django.conf import settings
import django

def pytest_configure():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "consultorio_medico.settings")
    settings.DATABASES['default'] = {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
        'ATOMIC_REQUESTS': False,
    }
    django.setup()
