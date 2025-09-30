from django.core.management.base import BaseCommand, CommandError
from django.contrib.gis.geos import GEOSGeometry
from django.conf import settings
import json
from Backend.models import Zona
from pathlib import Path

class Command(BaseCommand):
    help = 'Importa zonas desde un archivo GeoJSON a modelos Zona'

    def add_arguments(self, parser):
        parser.add_argument('--file', type=str, help='Ruta al archivo GeoJSON', default=str(Path(settings.BASE_DIR) / 'Frontend' / 'Recursos' / 'Barrios_Funza.geojson'))
        parser.add_argument('--overwrite', action='store_true', help='Sobrescribir zonas existentes con el mismo nombre')
        parser.add_argument('--dry-run', action='store_true', help='Solo mostrar cuántas zonas se importarían')

    def handle(self, *args, **options):
        file_path = Path(options['file'])
        if not file_path.exists():
            raise CommandError(f'Archivo no encontrado: {file_path}')

        with open(file_path, 'r', encoding='utf-8') as f:
            geo = json.load(f)

        if geo.get('type') != 'FeatureCollection' or 'features' not in geo:
            raise CommandError('El archivo no parece un GeoJSON FeatureCollection')

        features = geo['features']
        created = 0
        skipped = 0
        for feat in features:
            props = feat.get('properties', {})
            nombre = props.get('NOMBRE') or props.get('nombre') or props.get('NOMBRE_BARRIO')
            if not nombre:
                self.stdout.write(self.style.WARNING('Saltando feature sin nombre'))
                skipped += 1
                continue

            geom = feat.get('geometry')
            if not geom:
                self.stdout.write(self.style.WARNING(f'Saltando {nombre}: sin geometría'))
                skipped += 1
                continue

            geom_json = json.dumps(geom)
            try:
                g = GEOSGeometry(geom_json)
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error al parsear geometría de {nombre}: {e}'))
                skipped += 1
                continue

            if options['dry_run']:
                self.stdout.write(self.style.NOTICE(f'Importar: {nombre}'))
                continue

            obj, created_flag = Zona.objects.get_or_create(nombre=nombre)
            if created_flag:
                obj.geometria = g
                obj.descripcion = props.get('DESCRIPCIO') or props.get('DESCRIPCION') or ''
                obj.save()
                created += 1
            else:
                if options['overwrite']:
                    obj.geometria = g
                    obj.descripcion = props.get('DESCRIPCIO') or props.get('DESCRIPCION') or obj.descripcion
                    obj.save()
                    created += 1
                else:
                    skipped += 1

        self.stdout.write(self.style.SUCCESS(f'Import terminado. Creadas/actualizadas: {created}. Saltadas: {skipped}'))
