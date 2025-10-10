import os
import sys
from django.conf import settings
from django.db import transaction

DB_SQLITE = r"C:\Users\dnalj\PycharmProjects\Secuseo\db.sqlite3"

print('Using DB aliases before change:', list(settings.DATABASES.keys()))
# Build sqlite alias by copying the default DB config so Django's DB machinery
# finds expected keys (TIME_ZONE, OPTIONS, etc.). Then override the engine/name.
default_db = settings.DATABASES.get('default', {}).copy()
sqlite_db = default_db
sqlite_db.update({
    'ENGINE': 'django.db.backends.sqlite3',
    'NAME': DB_SQLITE,
})
if 'OPTIONS' not in sqlite_db:
    sqlite_db['OPTIONS'] = {}
settings.DATABASES['sqlite'] = sqlite_db
print('Using DB aliases after change:', list(settings.DATABASES.keys()))

from Backend.models import Reporte

src_alias = 'sqlite'
dst_alias = 'default'

# gather ids
src_ids = list(Reporte.objects.using(src_alias).values_list('id', flat=True))
dst_ids = list(Reporte.objects.using(dst_alias).values_list('id', flat=True))
print('sqlite report ids:', src_ids)
print('postgres report ids:', dst_ids)
missing = [i for i in src_ids if i not in dst_ids]
print('missing ids to copy:', missing)

if not missing:
    print('No missing reports detected.')
else:
    # Copy missing rows one by one preserving PK and fields
    for pk in missing:
        try:
            r = Reporte.objects.using(src_alias).get(pk=pk)
        except Reporte.DoesNotExist:
            print(f'Warning: source report {pk} disappeared')
            continue
        # Build data dict of concrete fields except id
        data = {}
        for f in r._meta.concrete_fields:
            if f.name == 'id':
                continue
            val = getattr(r, f.name)
            # For ImageField, ORM expects either a File object or name. We'll pass the name (string).
            if f.get_internal_type() == 'ImageField':
                data[f.name] = val.name if val else None
            else:
                data[f.name] = val
        try:
            with transaction.atomic(using=dst_alias):
                Reporte.objects.using(dst_alias).create(id=r.id, **data)
            print('Copied report', pk)
        except Exception as e:
            print('Failed to copy', pk, 'error:', e)

# Verify counts after copy
print('Verifying counts...')
print('sqlite count:', Reporte.objects.using(src_alias).count())
print('postgres count:', Reporte.objects.using(dst_alias).count())

# If all sqlite report ids now present in postgres, remove sqlite DB file
remaining_missing = [i for i in Reporte.objects.using(src_alias).values_list('id', flat=True) if i not in Reporte.objects.using(dst_alias).values_list('id', flat=True)]
if remaining_missing:
    print('After attempted copy, still missing ids:', remaining_missing)
    print('Will NOT delete sqlite DB. Please review failures.')
    sys.exit(1)

# safe to delete sqlite file (ask user?) since user requested deletion, proceed
try:
    if os.path.exists(DB_SQLITE):
        os.remove(DB_SQLITE)
        print('Deleted sqlite DB file:', DB_SQLITE)
    # also remove journal if present
    journal = DB_SQLITE + '-journal'
    if os.path.exists(journal):
        os.remove(journal)
        print('Deleted sqlite journal file:', journal)
except Exception as e:
    print('Failed to delete sqlite files:', e)
    sys.exit(1)

print('Done.')
