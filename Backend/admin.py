from django.contrib import admin
from .models import Zona, Reporte, Comentario, UserProfile

@admin.register(Zona)
class ZonaAdmin(admin.ModelAdmin):
    list_display = ('nombre',)

@admin.register(Reporte)
class ReporteAdmin(admin.ModelAdmin):
    list_display = ('id', 'ubicacion', 'zona', 'tipo', 'estado', 'fecha_creacion')
    list_filter = ('tipo', 'zona')
    search_fields = ('ubicacion', 'descripcion')

@admin.register(Comentario)
class ComentarioAdmin(admin.ModelAdmin):
    list_display = ('reporte', 'usuario', 'fecha_comentario')

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'telefono')
