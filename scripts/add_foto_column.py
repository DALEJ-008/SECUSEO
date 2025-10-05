import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE','secuseo_project.settings')
from django import setup
setup()
from django.db import connection
with connection.cursor() as cur:
    cur.execute('ALTER TABLE "Backend_userprofile" ADD COLUMN IF NOT EXISTS foto varchar(512)')
print('ALTER OK')
