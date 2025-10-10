from django.db import models

from django.conf import settings


class Zona(models.Model):
    nombre = models.CharField(unique=True, max_length=100)
    descripcion = models.TextField(blank=True, null=True)
    geometria = models.JSONField(blank=True, null=True, db_column='perimetro_geografico')
    fecha_creacion = models.DateTimeField(blank=True, null=True)
    fecha_actualizacion = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'zona'


class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('admin', 'Administrador'),
        ('user', 'Usuario'),
        ('moderator', 'Moderador'),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='user')
    telefono = models.CharField(max_length=30, blank=True)

    class Meta:
        db_table = 'Backend_userprofile'
        managed = False

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.role})"


class Rol(models.Model):
    nombre = models.CharField(unique=True, max_length=50)
    descripcion = models.CharField(max_length=255, blank=True, null=True)
    fecha_creacion = models.DateTimeField(blank=True, null=True)
    fecha_actualizacion = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'rol'


class TipoRiesgo(models.Model):
    nombre = models.CharField(unique=True, max_length=100)
    descripcion = models.TextField(blank=True, null=True)
    nivel_prioridad = models.CharField(max_length=10)
    fecha_creacion = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'tipo_riesgo'


class Usuario(models.Model):
    nombre = models.CharField(max_length=100)
    correo = models.CharField(unique=True, max_length=100)
    contrasena_hash = models.CharField(max_length=255, db_column='contrase±a_hash')
    fecha_nacimiento = models.DateField(blank=True, null=True)
    rol = models.ForeignKey(Rol, models.DO_NOTHING)
    estado = models.CharField(max_length=20, blank=True, null=True)
    zona_preferida = models.CharField(max_length=100, blank=True, null=True)
    fecha_ultima_conexion = models.DateTimeField(blank=True, null=True)
    token_notificaciones = models.CharField(max_length=255, blank=True, null=True)
    fecha_creacion = models.DateTimeField(blank=True, null=True)
    fecha_actualizacion = models.DateTimeField(blank=True, null=True)
    fecha_eliminacion = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'usuario'


class EstadoReporte(models.Model):
    nombre = models.CharField(unique=True, max_length=50)
    descripcion = models.CharField(max_length=255, blank=True, null=True)
    prioridad = models.IntegerField()
    fecha_creacion = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'estado_reporte'


class Reporte(models.Model):
    ubicacion = models.CharField(max_length=255)
    coordenadas = models.JSONField(blank=True, null=True, db_column='coordenadas')
    descripcion = models.TextField()
    prioridad = models.CharField(max_length=20, blank=True, null=True)
    fecha_creacion = models.DateTimeField(blank=True, null=True)
    estado = models.CharField(max_length=50, blank=True, null=True)
    creado_por = models.ForeignKey('auth.User', models.DO_NOTHING, db_column='creado_por_id', blank=True, null=True, related_name='reportes_creados')
    zona = models.ForeignKey(Zona, models.DO_NOTHING, db_column='zona_id', blank=True, null=True)
    imagen = models.CharField(max_length=255, blank=True, null=True)
    tipo = models.CharField(max_length=50, blank=True, null=True)
        # fecha_actualizacion = models.DateTimeField(blank=True, null=True)
        # fecha_eliminacion = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'Backend_reporte'

    @property
    def imagen_url(self):
        from django.conf import settings
        if self.imagen:
            return settings.MEDIA_URL.rstrip('/') + '/' + str(self.imagen).lstrip('/')
        return None


class Comentario(models.Model):
    reporte = models.ForeignKey(Reporte, models.DO_NOTHING)
    usuario = models.ForeignKey(Usuario, models.DO_NOTHING)
    contenido = models.TextField()
    fecha_comentario = models.DateTimeField(blank=True, null=True)
    fecha_actualizacion = models.DateTimeField(blank=True, null=True)
    fecha_eliminacion = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'comentario'


class Multimedia(models.Model):
    reporte = models.ForeignKey(Reporte, models.DO_NOTHING)
    usuario_creador = models.ForeignKey(Usuario, models.DO_NOTHING)
    ruta_archivo = models.CharField(max_length=512)
    tipo_archivo = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True, null=True)
    fecha_creacion = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'multimedia'


class ValidacionReporte(models.Model):
    reporte = models.ForeignKey(Reporte, models.DO_NOTHING)
    usuario_validador = models.ForeignKey(Usuario, models.DO_NOTHING)
    decision = models.CharField(max_length=20, blank=True, null=True)
    comentario_validacion = models.TextField(blank=True, null=True)
    fecha_validacion = models.DateTimeField(blank=True, null=True)
    fecha_actualizacion = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'validacion_reporte'


