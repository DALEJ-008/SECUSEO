p = r"C:\Users\dnalj\PycharmProjects\Secuseo\Frontend\Recursos\Barrios_Funza.geojson"
with open(p, 'rb') as f:
    b = f.read()
# decode utf-8
s = b.decode('utf-8')
pos = 261248
start = max(0, pos-200)
end = min(len(s), pos+200)
excerpt = s[start:end]
# compute line/col
prefix = s[:pos]
line_no = prefix.count('\n') + 1
col_no = pos - (prefix.rfind('\n') + 1) if '\n' in prefix else pos + 1
print('pos', pos, 'line', line_no, 'col', col_no)
print('---excerpt---')
print(excerpt)
# also print surrounding lines with numbers
lines = s.splitlines()
ln = line_no
from_line = max(1, ln-10)
to_line = min(len(lines), ln+10)
print('\n---lines {}..{}---'.format(from_line,to_line))
for i in range(from_line, to_line+1):
    marker = '>>' if i==ln else '  '
    print(f"{marker} {i:4d}: {lines[i-1]}")
with open(p + '.inspect.txt','w',encoding='utf-8') as out:
    out.write(excerpt)
print('\nWrote excerpt to', p + '.inspect.txt')
