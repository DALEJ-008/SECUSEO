from django.db import connection

tables = ['usuario','reporte','zona','comentario','multimedia','rol','tipo_riesgo','validacion_reporte']
cur = connection.cursor()
for t in tables:
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name=%s;", [t])
    exists = cur.fetchone()
    print('\nTABLE:', t, 'EXISTS:' , bool(exists))
    if not exists:
        continue
    cur.execute("SELECT column_name, data_type, is_nullable, column_default FROM information_schema.columns WHERE table_name=%s ORDER BY ordinal_position;", [t])
    cols = cur.fetchall()
    for col in cols:
        print('  ', col[0], col[1], 'nullable=' + col[2], 'default=' + str(col[3]))
