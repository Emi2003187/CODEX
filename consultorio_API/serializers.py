from rest_framework import serializers
from .models import Paciente, Usuario

class UsuarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Usuario
        fields = ['id', 'username', 'first_name', 'last_name', 'email', 'rol']


# serializers.py
class PacienteSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Paciente
        fields = "__all__"
