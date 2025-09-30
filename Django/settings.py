import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': 'SECUSEO',
        'USER': 'postgres',
        'PASSWORD': 'Aa280425',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}

# Agregar apps instaladas
INSTALLED_APPS = [
    ...,
    'reportes',
    'leaflet',
    'django.contrib.gis',
]

# Configuración de Leaflet para el mapa
LEAFLET_CONFIG = {
    'DEFAULT_CENTER': (4.716, -74.212),  # Coordenadas de Funza
    'DEFAULT_ZOOM': 13,
    'MIN_ZOOM': 3,
    'MAX_ZOOM': 18,
}
