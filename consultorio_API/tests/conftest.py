import os
import sys
from pathlib import Path
import pytest
from django.conf import settings
import django

def pytest_configure():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "consultorio_medico.settings")
    # Ensure the project root is on the Python path so Django can import the
    # settings module when tests are run from a different working directory.
    project_root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(project_root))
    settings.DATABASES['default'] = {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
        'ATOMIC_REQUESTS': False,
    }
    django.setup()
