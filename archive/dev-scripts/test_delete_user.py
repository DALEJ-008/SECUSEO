from django.contrib.auth.models import User
from django.test import Client

# create admin
admin, created = User.objects.get_or_create(username='admin_for_test', defaults={'email':'admin_test@example.com','is_staff':True,'is_superuser':True})
if created:
    admin.set_password('AdminPass123')
    admin.save()
    print('admin created')
# create target
u, created = User.objects.get_or_create(username='user_to_delete', defaults={'email':'delete_me@example.com'})
if created:
    u.set_password('UserPass1')
    u.save()
    print('target created')
# use test client to delete
c = Client()
c.force_login(admin)
resp = c.post(f'/admin/api/users/{u.id}/delete/')
print('STATUS', resp.status_code, resp.content.decode())
# try delete self
resp2 = c.post(f'/admin/api/users/{admin.id}/delete/')
print('DEL SELF', resp2.status_code, resp2.content.decode())
