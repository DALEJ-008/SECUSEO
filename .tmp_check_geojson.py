import json, sys, os
p = r"C:\Users\dnalj\PycharmProjects\Secuseo\Frontend\Recursos\Barrios_Funza.geojson"
print('Path:', p)
with open(p, 'rb') as f:
    b = f.read()
# try common decodings
for enc in ('utf-8','utf-8-sig','latin-1'):
    try:
        s = b.decode(enc)
        print('Decoded with', enc)
        break
    except Exception as e:
        # try next
        s = None
if s is None:
    s = b.decode('utf-8', errors='replace')
    print('Decoded with replace')
try:
    data = json.loads(s)
    print('OK - features', len(data.get('features', [])))
    sys.exit(0)
except json.JSONDecodeError as e:
    print('JSONDecodeError:', e)
    pos = e.pos
    start = max(0, pos-200)
    end = min(len(s), pos+200)
    context = s[start:end]
    # compute line/col
    prefix = s[:pos]
    line_no = prefix.count('\n') + 1
    col_no = pos - (prefix.rfind('\n') + 1) if '\n' in prefix else pos + 1
    print('Error at pos', pos, 'line', line_no, 'col', col_no)
    excerpt_path = p + '.err_excerpt.txt'
    with open(excerpt_path, 'w', encoding='utf-8') as out:
        out.write(context)
    print('Wrote excerpt to', excerpt_path)
    print('---context---')
    print(context)
    sys.exit(2)
except Exception as e:
    print('Other error:', e)
    sys.exit(3)
