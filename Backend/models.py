from django.contrib.gis.db import models
from django.contrib.auth.models import User

class Zona(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True)
    geometria = models.PolygonField()  # Para el GeoJSON de barrios
    
    def __str__(self):
        return self.nombre

class Reporte(models.Model):
    PRIORIDAD_CHOICES = [
        ('alto', 'Alto'),
        ('medio', 'Medio'),
        ('bajo', 'Bajo'),
    ]
    
    ubicacion = models.CharField(max_length=255)
    coordenadas = models.PointField()  # Para coordenadas lat/lng
    zona = models.ForeignKey(Zona, on_delete=models.SET_NULL, null=True)
    descripcion = models.TextField()
    prioridad = models.CharField(max_length=10, choices=PRIORIDAD_CHOICES)
    creado_por = models.ForeignKey(User, on_delete=models.CASCADE)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Reporte en {self.ubicacion}"

# ... [Agregar todos los demás modelos del SQL] ...
