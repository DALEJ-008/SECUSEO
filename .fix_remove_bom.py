import json
p = r"C:\Users\dnalj\PycharmProjects\Secuseo\Frontend\Recursos\Barrios_Funza.geojson"
print('File:', p)
# Read with utf-8-sig to strip BOM if present
with open(p, 'r', encoding='utf-8-sig') as f:
    s = f.read()
# Write back with standard utf-8 (no BOM)
with open(p, 'w', encoding='utf-8') as f:
    f.write(s)
print('Rewritten without BOM (utf-8)')
# Validate JSON
try:
    data = json.loads(s)
    print('Parsed OK - features:', len(data.get('features', [])))
except Exception as e:
    print('Parse failed:', e)
    raise
