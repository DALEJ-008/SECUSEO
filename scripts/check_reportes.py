import requests

try:
    r = requests.get('http://127.0.0.1:8000/api/reportes/')
    print('STATUS', r.status_code)
    data = r.json()
    rs = data.get('reportes', [])
    print('TOTAL', len(rs))
    for R in rs:
        print('ID:', R.get('id'), '| zona=', repr(R.get('zona')) , '| coords=', R.get('coordenadas'), '| tipo/prio=', R.get('tipo') or R.get('prioridad'))
except Exception as e:
    print('ERROR', e)
