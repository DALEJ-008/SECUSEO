from django import forms
from .models import Reporte, Comentario

class ReporteForm(forms.ModelForm):
    class Meta:
        model = Reporte
        fields = ['ubicacion', 'coordenadas', 'descripcion', 'tipo', 'imagen']

class ComentarioForm(forms.ModelForm):
    class Meta:
        model = Comentario
        fields = ['texto']
