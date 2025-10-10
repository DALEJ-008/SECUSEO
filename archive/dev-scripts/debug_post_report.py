import os
import sys
from pathlib import Path
import django
from django.conf import settings

# ensure project root is on sys.path so secuseo_project can be imported
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'secuseo_project.settings')
django.setup()

from django.test import Client
from io import BytesIO

c = Client()

# create a dummy user and login if needed - this app requires authentication for POSTs
from django.contrib.auth.models import User
# Try to use an existing user to avoid creating users (which can fail if DB sequences are misaligned)
u = User.objects.first()
if u is None:
    # As a last resort, try to create a minimal user but catch failures
    try:
        u = User.objects.create_user('debugtester', 'debug@example.com', 'secret')
    except Exception:
        u = User.objects.first()

# Use force_login to bypass auth backend password checks in the test client
c.force_login(u)

# create a small fake image
img = BytesIO()
img.write(b'GIF87a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;')
img.seek(0)

post = {
    'ubicacion': 'Lugar de prueba',
    'descripcion': 'texto debug',
    'tipo': 'otro',
    'lat': '4.709117',
    'lng': '-74.2001442'
}

files = {
    'imagen': ('debug.gif', img, 'image/gif')
}

resp = c.post('/api/reportes/crear/', post, files=files)
print('STATUS:', resp.status_code)
try:
    print('JSON:', resp.json())
except Exception as e:
    print('RAW:', resp.content[:1000])
