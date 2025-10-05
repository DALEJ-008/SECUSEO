from django.core.management.base import BaseCommand, CommandError
from django.core.management import call_command
from django.conf import settings
import os


class Command(BaseCommand):
    help = 'Copy core data from default DB to a PostgreSQL database. Preserves PKs and relations for Users, UserProfile, Zona, Reporte, Comentario.'

    def add_arguments(self, parser):
        parser.add_argument('--engine', default='django.db.backends.postgresql', help='DB engine')
        parser.add_argument('--name', required=True, help='Database name')
        parser.add_argument('--user', required=True, help='DB user')
        parser.add_argument('--password', required=True, help='DB password')
        parser.add_argument('--host', default='localhost', help='DB host')
        parser.add_argument('--port', default='5432', help='DB port')

    def handle(self, *args, **options):
        engine = options['engine']
        name = options['name']
        user = options['user']
        password = options['password']
        host = options['host']
        port = options['port']

        # Build the new DB config by copying the existing default config and overriding
        # the connection-specific keys. This preserves keys Django expects (like TIME_ZONE,
        # OPTIONS, etc.) so migrations won't fail due to missing entries.
        default_db = settings.DATABASES.get('default', {})
        new_db = default_db.copy()
        new_db.update({
            'ENGINE': engine,
            'NAME': name,
            'USER': user,
            'PASSWORD': password,
            'HOST': host,
            'PORT': port,
        })
        # Ensure OPTIONS exists
        if 'OPTIONS' not in new_db:
            new_db['OPTIONS'] = {}

        settings.DATABASES['pg'] = new_db

        self.stdout.write(self.style.NOTICE('Running migrations on target Postgres DB...'))
        # Run migrations on the target DB to create tables
        try:
            call_command('migrate', database='pg', interactive=False)
        except Exception as e:
            raise CommandError(f'Could not run migrations on target DB: {e}')

        # Now copy data model by model
        from django.contrib.auth.models import User
        from Backend.models import UserProfile, Zona, Reporte, Comentario

        src = 'default'
        dst = 'pg'

        # Helper to copy queryset preserving PK
        def copy_qs(Model, qs, fields=None):
            objs = []
            for o in qs:
                data = {}
                for f in (fields or [f.name for f in o._meta.concrete_fields]):
                    # skip auto fields if not present
                    try:
                        val = getattr(o, f)
                    except Exception:
                        continue
                    data[f] = val
                # preserve PK
                objs.append(Model(**data))
            if objs:
                Model.objects.using(dst).bulk_create(objs)

        # Copy Users
        self.stdout.write('Copying users...')
        users_src = User.objects.using(src).all()
        # Build user list with raw fields to preserve password
        for u in users_src:
            if User.objects.using(dst).filter(pk=u.pk).exists():
                continue
            User.objects.using(dst).create(
                id=u.id,
                username=u.username,
                first_name=u.first_name,
                last_name=u.last_name,
                email=u.email,
                password=u.password,
                is_staff=u.is_staff,
                is_superuser=u.is_superuser,
                is_active=u.is_active,
                date_joined=u.date_joined,
            )

        # Copy UserProfile
        self.stdout.write('Copying user profiles...')
        for p in UserProfile.objects.using(src).all():
            if UserProfile.objects.using(dst).filter(user_id=p.user_id).exists():
                continue
            UserProfile.objects.using(dst).create(
                user_id=p.user_id,
                role=p.role,
                telefono=p.telefono,
            )

        # Copy Zonas
        self.stdout.write('Copying zonas...')
        for z in Zona.objects.using(src).all():
            if Zona.objects.using(dst).filter(pk=z.pk).exists():
                continue
            Zona.objects.using(dst).create(id=z.id, nombre=z.nombre, descripcion=z.descripcion, geometria=z.geometria)

        # Copy Reportes
        self.stdout.write('Copying reportes...')
        for r in Reporte.objects.using(src).all():
            if Reporte.objects.using(dst).filter(pk=r.pk).exists():
                continue
            Reporte.objects.using(dst).create(
                id=r.id,
                ubicacion=r.ubicacion,
                coordenadas=r.coordenadas,
                zona_id=(r.zona_id if r.zona_id else None),
                descripcion=r.descripcion,
                tipo=r.tipo,
                prioridad=r.prioridad,
                imagen=r.imagen.name if r.imagen else None,
                creado_por_id=(r.creado_por_id if r.creado_por_id else None),
                fecha_creacion=r.fecha_creacion,
                estado=r.estado,
            )

        # Copy Comentarios
        self.stdout.write('Copying comentarios...')
        for c in Comentario.objects.using(src).all():
            if Comentario.objects.using(dst).filter(pk=c.pk).exists():
                continue
            Comentario.objects.using(dst).create(
                id=c.id,
                reporte_id=c.reporte_id,
                autor_id=(c.autor_id if c.autor_id else None),
                texto=c.texto,
                fecha=c.fecha,
            )

        self.stdout.write(self.style.SUCCESS('Data copy complete. You may want to run sqlsequencereset for apps on the target DB to fix sequences.'))