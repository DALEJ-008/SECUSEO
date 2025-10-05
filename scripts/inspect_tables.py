from django.apps import apps
from django.db import connection

print('Installed models and their db_table:')
for m in apps.get_models():
    print(m._meta.app_label, m.__name__, m._meta.db_table)

# check specific Spanish-named tables
tables_to_check=['usuario','reporte','zona','comentario','multimedia','rol','tipo_riesgo','validacion_reporte','usuario']
cur=connection.cursor()
cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE';")
all_tables=[r[0] for r in cur.fetchall()]
print('\nAll tables in public schema (sample):', all_tables[:200])
for t in tables_to_check:
    if t in all_tables:
        try:
            cur.execute(f'SELECT COUNT(*) FROM "{t}";')
            c=cur.fetchone()[0]
        except Exception as e:
            c=str(e)
    else:
        c='not present'
    print(t, c)
