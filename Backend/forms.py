from django import forms
from .models import Reporte, Comentario, TipoRiesgo, Zona


class ReporteForm(forms.ModelForm):
    class Meta:
        model = Reporte
        # Use fields that exist on the Spanish-mapped Backend_reporte model
        fields = ['ubicacion', 'coordenadas', 'descripcion', 'tipo', 'zona', 'prioridad', 'imagen']


class ComentarioForm(forms.ModelForm):
    class Meta:
        model = Comentario
        # the Spanish table uses 'contenido' for the comment text
        fields = ['contenido']
