from django.db import models
from django.conf import settings
from django.contrib.auth.models import AbstractUser


class Zona(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True)
    # Store geometry as GeoJSON in a JSONField for development (no native GIS libs needed).
    geometria = models.JSONField(null=True, blank=True)

    def __str__(self):
        return self.nombre


class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('admin', 'Administrador'),
        ('user', 'Usuario'),
        ('moderator', 'Moderador'),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='user')
    telefono = models.CharField(max_length=30, blank=True)

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.role})"


class Reporte(models.Model):
    PRIORIDAD_CHOICES = [
        ('muy_alto', 'Muy alto'),
        ('alto', 'Alto'),
        ('medio', 'Medio'),
        ('bajo', 'Bajo'),
    ]

    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('validado', 'Validado'),
        ('rechazado', 'Rechazado'),
    ]

    ubicacion = models.CharField(max_length=255)
    coordenadas = models.JSONField(null=True, blank=True)  # Store point as GeoJSON or [lng, lat]
    zona = models.ForeignKey(Zona, on_delete=models.SET_NULL, null=True, blank=True)
    descripcion = models.TextField()
    # Tipo de riesgo (más específico) y prioridad derivada
    TIPO_CHOICES = [
        ('robo', 'Robo'),
        ('asalto', 'Asalto'),
        ('hurto', 'Hurto'),
        ('vandalismo', 'Vandalismo'),
        ('iluminacion', 'Poca iluminación'),
        ('accidente', 'Accidente de Tránsito'),
        ('violencia', 'Violencia'),
        ('consumo_drogas', 'Consumo/venta de drogas'),
        ('incendio', 'Incendio'),
        ('amenaza', 'Amenaza'),
        ('otro', 'Otro'),
    ]
    # Add missing types
    TIPO_EXTRA = [
        ('robo_vehiculo', 'Robo de vehículos'),
        ('acoso_callejero', 'Acoso callejero'),
        ('prostitucion_ilegal', 'Prostitución ilegal'),
        ('fraude_estafa', 'Fraudes y estafas'),
    ]
    # combine lists
    TIPO_CHOICES = TIPO_CHOICES + TIPO_EXTRA
    tipo = models.CharField(max_length=30, choices=TIPO_CHOICES, default='otro')
    prioridad = models.CharField(max_length=10, choices=PRIORIDAD_CHOICES, blank=True)
    # Imagen opcional
    imagen = models.ImageField(upload_to='report_images/', null=True, blank=True)
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='pendiente')

    def __str__(self):
        return f"Reporte #{self.pk} - {self.ubicacion}"

    def save(self, *args, **kwargs):
        # Map tipo -> prioridad if prioridad not explicitly set
        tipo_to_prioridad = {
            'robo': 'alto',
            'asalto': 'alto',
            'hurto': 'alto',
            'vandalismo': 'medio',
            'iluminacion': 'medio',
            'accidente': 'alto',
            'violencia': 'muy_alto',
            'consumo_drogas': 'muy_alto',
            'incendio': 'alto',
            'amenaza': 'alto',
            'robo_vehiculo': 'alto',
            'acoso_callejero': 'medio',
            'prostitucion_ilegal': 'medio',
            'fraude_estafa': 'medio',
            'otro': 'medio'
        }
        if not self.prioridad:
            self.prioridad = tipo_to_prioridad.get(self.tipo, 'medio')
        super().save(*args, **kwargs)


class Comentario(models.Model):
    reporte = models.ForeignKey(Reporte, on_delete=models.CASCADE, related_name='comentarios')
    autor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    texto = models.TextField()
    fecha = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Comentario de {self.autor} en {self.reporte_id}"

