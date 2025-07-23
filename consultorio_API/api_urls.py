from django.urls import path
from .viewscitas import citas_json


urlpatterns = [
    path('citas-json/', citas_json, name='citas_json'),
]
