from django.contrib.auth.models import User
from django.test import Client
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection

print('starting test script')
username = 'ci_test_user'
password = 'Testpass123!'
user, created = User.objects.get_or_create(username=username, defaults={'email':'ci@example.com'})
if created:
    user.set_password(password)
    user.save()
    print('created user')
else:
    print('user exists')

client = Client()
logged = client.login(username=username, password=password)
print('logged in via client:', logged)

# prepare a small file
file_content = b'PNGDATA'
up = SimpleUploadedFile('avatar.png', file_content, content_type='image/png')
resp = client.post('/api/profile/update/', {'username': 'ci_test_user2'}, FILES={'photo': up})
print('update status code:', resp.status_code)
try:
    print('update json:', resp.json())
except Exception as e:
    print('update resp content:', resp.content)

w = client.get('/api/whoami/')
print('whoami status', w.status_code)
try:
    print('whoami json:', w.json())
except Exception as e:
    print('whoami content:', w.content)

with connection.cursor() as cur:
    try:
        cur.execute('SELECT foto FROM "Backend_userprofile" WHERE user_id = %s', [user.id])
        row = cur.fetchone()
        print('foto column row:', row)
    except Exception as e:
        print('db error reading foto column:', e)

print('done')
