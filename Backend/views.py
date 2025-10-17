from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from .models import Reporte, Zona, UserProfile
from .forms import ReporteForm
import json

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.db import connection
from django.views.decorators.http import require_http_methods
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings
import os
from django.utils import timezone
import random
import hashlib
import pathlib
from django.views.decorators.csrf import csrf_exempt
# ...existing code...


def _punto_en_poligono (lon, lat, polygon_coords):
    # Algoritmo ray casting para determinar si unas coordenadas estan dentro de un polígono geografico
    #Asigna reportes a zonas geograficas
    def _ring_contains(x, y, ring):
        inside = False
        j = len(ring) - 1
        for i in range(len(ring)):
            xi, yi = ring[i][0], ring[i][1]
            xj, yj = ring[j][0], ring[j][1]
            intersect = ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi)
            if intersect:
                inside = not inside
            j = i
        return inside

    if not polygon_coords:
        return False

    if isinstance(polygon_coords[0][0], list) and isinstance(polygon_coords[0][0][0], list):
        for poly in polygon_coords:
            if _ring_contains(lon, lat, poly[0]):
                return True
        return False
    return _ring_contains(lon, lat, polygon_coords[0])


def _coincidencia_zona_nombre (ubicacion):
    # Intenta encontrar una zona por nombre en el texto de ubicación
    if not ubicacion:
        return None
    try:
        text = str(ubicacion).lower()
    except Exception:
        text = str(ubicacion)
    zonas = Zona.objects.all()
    for z in zonas:
        try:
            if not getattr(z, 'nombre', None):
                continue
            if z.nombre.lower() in text:
                return z
        except Exception:
            continue
    return None


def lista_reportes(request):
    # Devuelve lista de reportes validados con información de zona
    if not request.user or not request.user.is_authenticated:
        return JsonResponse({'ok': False, 'error': 'authentication required'}, status=401)

    qs = Reporte.objects.filter(estado='validado').select_related('zona', 'creado_por')[:100]
    # load lifecycle states for these reports (file-based storage) and skip resolved
    statuses = {}
    try:
        ids = [r.id for r in qs]
        statuses_dir = os.path.join(settings.MEDIA_ROOT, 'report_statuses')
        for rid in ids:
            sf = os.path.join(statuses_dir, f'report_{rid}.json')
            if os.path.exists(sf):
                try:
                    with open(sf, 'r', encoding='utf-8') as fh:
                        import json as _json
                        statuses[rid] = _json.load(fh)
                except Exception:
                    statuses[rid] = {'state': None}
            else:
                statuses[rid] = {'state': 'Activo'}
    except Exception:
        statuses = {}
    data = []
    for r in qs:
        # Determina el nombre de la zona
        zona_name = None
        try:
            if getattr(r, 'zona', None):
                zona_name = r.zona.nombre
            else:
                # intenta inferir primero a partir de las coordenadas, luego geocodifica la dirección, y luego coincide por nombre
                coords = getattr(r, 'coordenadas', None)
                if coords and isinstance(coords, (list, tuple)) and len(coords) >= 2:
                    try:
                        lng = float(coords[0])
                        lat = float(coords[1])
                        zonas = Zona.objects.exclude(geometria__isnull=True)
                        found = None
                        for z in zonas:
                            geom = z.geometria
                            if not geom:
                                continue
                            poly_coords = geom.get('coordinates')
                            try:
                                if _punto_en_poligono(lng, lat, poly_coords):
                                    found = z
                                    break
                            except Exception:
                                continue
                        if found:
                            zona_name = found.nombre
                            try:
                                r.zona = found
                                r.save(update_fields=['zona'])
                            except Exception:
                                pass
                    except Exception:
                        # coordenada invalida: pasa al intento de geocodificación
                        pass

                # si no se resuelve por coordenadas, intenta geocodificar la dirección
                if not zona_name:
                    ubic = getattr(r, 'ubicacion', None)
                    if ubic:
                        try:
                            import requests
                            user_agent = 'Secuseo/1.0 (contact@example.com)'
                            params = {'q': ubic, 'format': 'json', 'limit': 1}
                            headers = {'User-Agent': user_agent}
                            geores = requests.get('https://nominatim.openstreetmap.org/search', params=params, headers=headers, timeout=4)
                            if geores.ok:
                                arr = geores.json()
                                if isinstance(arr, list) and len(arr) > 0:
                                    latf = float(arr[0].get('lat'))
                                    lngf = float(arr[0].get('lon'))
                                    zonas = Zona.objects.exclude(geometria__isnull=True)
                                    found2 = None
                                    for z in zonas:
                                        geom = z.geometria
                                        if not geom:
                                            continue
                                        poly_coords = geom.get('coordinates')
                                        try:
                                            if _punto_en_poligono(lngf, latf, poly_coords):
                                                found2 = z
                                                break
                                        except Exception:
                                            continue
                                    if found2:
                                        zona_name = found2.nombre
                                        try:
                                            r.zona = found2
                                            r.coordenadas = [lngf, latf]
                                            r.save(update_fields=['zona', 'coordenadas'])
                                        except Exception:
                                            pass
                        except Exception:
                            # La geocodificacion puede fallar; lo ignora y deja la zona como None
                            pass

                # último recurso: intentar coincidir con un nombre de zona dentro del texto de la dirección
                if not zona_name:
                    zmatch = _coincidencia_zona_nombre(getattr(r, 'ubicacion', None))
                    if zmatch:
                        zona_name = zmatch.nombre
                        try:
                            r.zona = zmatch
                            r.save(update_fields=['zona'])
                        except Exception:
                            pass
        except Exception:
            zona_name = None

        # skip if lifecycle state is Resuelto
        st = statuses.get(r.id, {}).get('state') if statuses else None
        if st == 'Resuelto':
            continue

        data.append({
            'id': r.id,
            'ubicacion': r.ubicacion,
            'descripcion': r.descripcion,
            'prioridad': r.prioridad,
            'tipo': getattr(r, 'tipo', None),
            'estado': r.estado,
            'zona': zona_name,
            'coordenadas': r.coordenadas,
            'fecha_creacion': r.fecha_creacion.isoformat(),
        })
    return JsonResponse({'reportes': data})


def lista_zonas(request):
    # Lista todas las zonas disponibles
    if not request.user or not request.user.is_authenticated:
        return JsonResponse({'ok': False, 'error': 'authentication required'}, status=401)
    qs = Zona.objects.all()
    data = []
    for z in qs:
        data.append({
            'id': z.id,
            'nombre': z.nombre,
            'descripcion': z.descripcion,
            'geometria': z.geometria,
        })
    return JsonResponse({'zonas': data})

#DETALLE REPORTE
def detalle_reporte(request, pk):
    if not request.user or not request.user.is_authenticated:
        return JsonResponse({'ok': False, 'error': 'authentication required'}, status=401)
    r = get_object_or_404(Reporte, pk=pk)
    return JsonResponse({
        'id': r.id,
        'ubicacion': r.ubicacion,
        'descripcion': r.descripcion,
        'prioridad': r.prioridad,
        'tipo': getattr(r, 'tipo', None),
        'estado': r.estado,
        'zona': (lambda rr: (rr.zona.nombre if getattr(rr, 'zona', None) else None)) (r) if True else None,
    })

 # CREACION REPORTE
def crear_reporte(request):
    if request.method == 'POST':
        form = ReporteForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                rep = form.save(commit=False)
            except Exception as e:
                import traceback
                return JsonResponse({'ok': False, 'error': 'form.save failed', 'detail': str(e), 'trace': traceback.format_exc()}, status=500)
            lat = request.POST.get('lat')
            lng = request.POST.get('lng')
            if not lat or not lng:
                coords = request.POST.get('coordenadas')
                if coords:
                    try:
                        c = json.loads(coords)
                        if isinstance(c, list) and len(c) >= 2:
                            lng, lat = c[0], c[1]
                    except Exception:
                        pass

            if lat and lng:
                try:
                    latf = float(lat)
                    lngf = float(lng)
                    rep.coordenadas = [lngf, latf]
                    zonas = Zona.objects.exclude(geometria__isnull=True)
                    found = None
                    for z in zonas:
                        geom = z.geometria
                        if not geom: continue
                        coords = geom.get('coordinates')
                        if _punto_en_poligono(lngf, latf, coords):
                            found = z
                            break
                    if found:
                        rep.zona = found
                except ValueError:
                    # si no se puede analizar latitud/longitud numérica, pasa a intentar la geocodificación
                    pass
            else:
                #Si no se puede analizar lat/lon, se trata de geocodificar la ubicacion
                ubic = rep.ubicacion if getattr(rep, 'ubicacion', None) else None
                if ubic:
                    try:
                        # Se usa la búsqueda de Nominatim para resolver la dirección a coordenadas
                        import requests
                        user_agent = 'Secuseo/1.0 (contact@example.com)'
                        params = {'q': ubic, 'format': 'json', 'limit': 1}
                        headers = {'User-Agent': user_agent}
                        r = requests.get('https://nominatim.openstreetmap.org/search', params=params, headers=headers, timeout=5)
                        if r.ok:
                            arr = r.json()
                            if isinstance(arr, list) and len(arr) > 0:
                                latf = float(arr[0].get('lat'))
                                lngf = float(arr[0].get('lon'))
                                rep.coordenadas = [lngf, latf]
                                # now try to find a containing Zona
                                zonas = Zona.objects.exclude(geometria__isnull=True)
                                found2 = None
                                for z in zonas:
                                    geom = z.geometria
                                    if not geom: continue
                                    coords = geom.get('coordinates')
                                    try:
                                        if _punto_en_poligono(lngf, latf, coords):
                                            found2 = z
                                            break
                                    except Exception:
                                        continue
                                if found2:
                                    rep.zona = found2
                            else:

                                zmatch = _coincidencia_zona_nombre(rep.ubicacion if getattr(rep, 'ubicacion', None) else None)
                                if zmatch:
                                    rep.zona = zmatch
                    except Exception:
                        # La red/geocodificación puede fallar; ignora y continua
                        pass

            try:
                if request.user.is_authenticated:
                    rep.creado_por = request.user

                if 'imagen' in request.FILES:
                    # Almacena la imagen cargada como un archivo y conservar la cadena de ruta en el CharField de la imagen
                    try:
                        f = request.FILES['imagen']
                        dest_dir = os.path.join(settings.MEDIA_ROOT, 'report_images')
                        os.makedirs(dest_dir, exist_ok=True)
                        timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
                        safe_name = f"report_{timestamp}_{f.name}"
                        path = default_storage.save(os.path.join('report_images', safe_name), ContentFile(f.read()))
                        # store relative path
                        rep.imagen = path
                    except Exception:
                        #  Si falla al intentar guardar la imagen. ignora el error y continua con la creacion del reporte
                        pass

                # Ensure required DB columns are populated (legacy DB may have NOT NULL constraints)
                if not getattr(rep, 'prioridad', None):
                    # fall back to tipo if available, otherwise use a safe default
                    rep.prioridad = (rep.tipo if getattr(rep, 'tipo', None) else 'normal')
                # Legacy DB may have short varchar limits (e.g., prioridad varchar(10)); truncate to be safe
                try:
                    if getattr(rep, 'prioridad', None):
                        rep.prioridad = str(rep.prioridad)[:10]
                except Exception:
                    pass
                if not getattr(rep, 'fecha_creacion', None):
                    rep.fecha_creacion = timezone.now()
                if not getattr(rep, 'estado', None):
                    rep.estado = 'pendiente'

                # set lifecycle status file (default: Activo)
                try:
                    statuses_dir = os.path.join(settings.MEDIA_ROOT, 'report_statuses')
                    os.makedirs(statuses_dir, exist_ok=True)
                    status_path = os.path.join(statuses_dir, f'report_{rep.id if getattr(rep, "id", None) else "new"}.json')
                    # only write after save (below) when we have id; we'll handle after saving
                except Exception:
                    pass

                # Run model validation to surface errors before attempting to save
                try:
                    # exclude imagen if it's a file-like issue
                    rep.full_clean()
                except Exception as clean_exc:
                    # return validation errors to the client
                    try:
                        import traceback as _tb
                        tb = _tb.format_exc()
                    except Exception:
                        tb = None
                    return JsonResponse({'ok': False, 'error': 'validation failed', 'detail': str(clean_exc), 'trace': tb}, status=400)

                try:
                    rep.save()
                    # write lifecycle status file now that we have an id
                    try:
                        statuses_dir = os.path.join(settings.MEDIA_ROOT, 'report_statuses')
                        os.makedirs(statuses_dir, exist_ok=True)
                        status_path = os.path.join(statuses_dir, f'report_{rep.id}.json')
                        import json as _json
                        _json.dump({'state': 'Activo', 'updated': timezone.now().isoformat()}, open(status_path, 'w', encoding='utf-8'))
                    except Exception:
                        pass
                    return JsonResponse({'ok': True, 'id': rep.id})
                except Exception as save_exc:
                    # write detailed debug info to a server-side file under MEDIA_ROOT for inspection
                    import traceback as _tb
                    trace = _tb.format_exc()
                    try:
                        log_dir = os.path.join(settings.MEDIA_ROOT, 'debug')
                        os.makedirs(log_dir, exist_ok=True)
                        log_path = os.path.join(log_dir, f'report_save_error_{timezone.now().strftime("%Y%m%d%H%M%S")}.log')
                        with open(log_path, 'w', encoding='utf-8') as lf:
                            lf.write('=== Exception saving Reporte ===\n')
                            lf.write(trace + '\n\n')
                            lf.write('--- form.cleaned_data ---\n')
                            try:
                                lf.write(json.dumps(getattr(form, 'cleaned_data', {}), default=str, ensure_ascii=False, indent=2))
                            except Exception:
                                lf.write(repr(getattr(form, 'cleaned_data', None)))
                            lf.write('\n\n')
                            lf.write('--- request.POST keys ---\n')
                            try:
                                lf.write(repr(list(request.POST.keys())))
                            except Exception:
                                lf.write('unavailable')
                            lf.write('\n\n')
                            lf.write('--- request.FILES keys ---\n')
                            try:
                                lf.write(repr(list(request.FILES.keys())))
                            except Exception:
                                lf.write('unavailable')
                            lf.write('\n\n')
                            lf.write('--- rep.__dict__ ---\n')
                            try:
                                lf.write(repr(rep.__dict__))
                            except Exception:
                                lf.write('unavailable')
                    except Exception:
                        log_path = None
                    # Try fallback: raw SQL INSERT into Backend_reporte (useful for managed=False/inspectdb models)
                    try:
                        coords_json = json.dumps(rep.coordenadas) if getattr(rep, 'coordenadas', None) is not None else None
                        fecha_val = rep.fecha_creacion if getattr(rep, 'fecha_creacion', None) else timezone.now()
                        with connection.cursor() as cur:
                            cur.execute(
                                'INSERT INTO "Backend_reporte" (ubicacion, coordenadas, descripcion, prioridad, fecha_creacion, estado, creado_por_id, zona_id, imagen, tipo) VALUES (%s, %s::json, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id',
                                [
                                    rep.ubicacion,
                                    coords_json,
                                    rep.descripcion,
                                    rep.prioridad,
                                    fecha_val,
                                    rep.estado,
                                    (rep.creado_por.id if getattr(rep, 'creado_por', None) else None),
                                    (rep.zona.id if getattr(rep, 'zona', None) else None),
                                    rep.imagen,
                                    rep.tipo,
                                ]
                            )
                            new_id = cur.fetchone()[0]
                        if new_id:
                            return JsonResponse({'ok': True, 'id': new_id, 'note': 'inserted via raw SQL fallback'})
                    except Exception:
                        # raw insert also failed, fall through to returning the original error
                        pass
                    # Return a shorter error to client but include path to debug file if available
                    resp = {'ok': False, 'error': 'save failed', 'detail': str(save_exc)}
                    if log_path:
                        # provide URL-ish path for easier retrieval by developer
                        try:
                            resp['debug_file'] = settings.MEDIA_URL.rstrip('/') + '/debug/' + os.path.basename(log_path)
                        except Exception:
                            resp['debug_file'] = log_path
                    return JsonResponse(resp, status=500)
            except Exception as e:
                import traceback
                return JsonResponse({'ok': False, 'error': 'save failed', 'detail': str(e), 'trace': traceback.format_exc()}, status=500)
        return JsonResponse({'ok': False, 'errors': form.errors}, status=400)
    return JsonResponse({'ok': False, 'error': 'POST required'}, status=405)


@login_required
def pagina_principal(request):
    return render(request, 'PaginaPrincipal.html')


def formulario_reporte(request):
    form = ReporteForm()
    return render(request, 'FormularioReporte.html', {'form': form})


def inicio_sesion(request):
    # Serve login/register page on GET
    if request.method == 'GET':
        return render(request, 'InicioSesion.html')

    action = request.POST.get('action') or request.GET.get('action')
    if action == 'login':
        email = request.POST.get('email')
        password = request.POST.get('password')
        if not email or not password:
            return JsonResponse({'ok': False, 'error': 'credenciales requeridas'}, status=400)

        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            return JsonResponse({'ok': False, 'error': 'El correo no está registrado. Por favor regístrate.'}, status=400)

        user = authenticate(request, username=user.username, password=password)
        if user is None:
            return JsonResponse({'ok': False, 'error': 'Credenciales inválidas'}, status=400)

        login(request, user)
        #Asegura que el usuario tenga una cuenta, si no tiene que crear una
        try:
            profile = user.profile
        except Exception:
            # si el usuario es un Django superuser/staff
            default_role = 'admin' if (user.is_superuser or user.is_staff) else 'user'
            profile = None
            try:
                profile = UserProfile.objects.create(user=user, role=default_role)
            except Exception as _create_exc:
                # Don't block login if legacy profile table insertion fails; write debug log and continue
                try:
                    import traceback as _tb
                    log_dir = os.path.join(settings.MEDIA_ROOT, 'debug')
                    os.makedirs(log_dir, exist_ok=True)
                    log_path = os.path.join(log_dir, f'userprofile_create_error_{timezone.now().strftime("%Y%m%d%H%M%S")}.log')
                    with open(log_path, 'w', encoding='utf-8') as lf:
                        lf.write('=== Exception creating UserProfile ===\n')
                        lf.write(_tb.format_exc() + '\n\n')
                        try:
                            lf.write(repr({'user_id': getattr(user, 'id', None), 'username': getattr(user, 'username', None), 'email': getattr(user, 'email', None)}))
                        except Exception:
                            lf.write('user info unavailable')
                except Exception:
                    pass

        role = getattr(profile, 'role', 'user')
        if role == 'admin':
            return JsonResponse({'ok': True, 'redirect': '/admin-panel/'} )
        return JsonResponse({'ok': True, 'redirect': '/'} )

    if action == 'register':
        name = request.POST.get('name')
        email = request.POST.get('email')
        password = request.POST.get('password')
        telefono = request.POST.get('telefono')
        dob = request.POST.get('dob')
        if not email or not password or not name or not telefono:
            return JsonResponse({'ok': False, 'error': 'Nombre, correo, contraseña y teléfono son requeridos'}, status=400)

        # check telefono not used in legacy Usuario or existing profile
        try:
            from .models import Usuario
            if Usuario.objects.filter(correo=telefono).exists():
                pass
        except Exception:
            pass

        # check in UserProfile table (if telefono column is used there) via raw SQL fallback
        try:
            with connection.cursor() as cur:
                cur.execute('SELECT 1 FROM "Backend_userprofile" WHERE telefono = %s LIMIT 1', [telefono])
                if cur.fetchone():
                    return JsonResponse({'ok': False, 'error': 'El teléfono ya está en uso'}, status=400)
        except Exception:
            # ignore DB issues; still proceed
            pass

        if User.objects.filter(email__iexact=email).exists():
            return JsonResponse({'ok': False, 'error': 'El correo ya está registrado. Intenta iniciar sesión.'}, status=400)

        username = email.split('@')[0]
        base = username
        i = 1
        while User.objects.filter(username=username).exists():
            username = f"{base}{i}"
            i += 1

        # Using raw telefono (no Twilio integration / normalization)

        user = User.objects.create(username=username, email=email, first_name=name)
        # Temporarily set is_active=False until phone is verified
        user.is_active = False
        user.set_password(password)
        user.save()

        profile = None
        try:
            profile = UserProfile.objects.create(user=user, role='user')
                # persist normalized phone into legacy profile table if possible
            try:
                with connection.cursor() as cur:
                    cur.execute('UPDATE "Backend_userprofile" SET telefono = %s WHERE user_id = %s', [telefono, user.id])
                    if cur.rowcount == 0:
                        cur.execute('INSERT INTO "Backend_userprofile" (user_id, role, telefono) VALUES (%s, %s, %s)', [user.id, 'user', telefono])
            except Exception:
                pass
        except Exception as _create_exc:
            # Registration should not fail completely if legacy profile insert fails.
            try:
                import traceback as _tb
                log_dir = os.path.join(settings.MEDIA_ROOT, 'debug')
                os.makedirs(log_dir, exist_ok=True)
                log_path = os.path.join(log_dir, f'userprofile_create_error_{timezone.now().strftime("%Y%m%d%H%M%S")}.log')
                with open(log_path, 'w', encoding='utf-8') as lf:
                    lf.write('=== Exception creating UserProfile during registration ===\n')
                    lf.write(_tb.format_exc() + '\n\n')
                    try:
                        lf.write(repr({'user_id': getattr(user, 'id', None), 'username': getattr(user, 'username', None), 'email': getattr(user, 'email', None)}))
                    except Exception:
                        lf.write('user info unavailable')
            except Exception:
                pass

        # Local-only OTP generation (no Twilio). Store OTP file and return debug_code in DEBUG mode.
        try:
            vdir = os.path.join(settings.MEDIA_ROOT, 'phone_verifications')
            os.makedirs(vdir, exist_ok=True)
            code = f"{random.randint(100000, 999999)}"
            expires = (timezone.now() + timezone.timedelta(minutes=10)).isoformat()
            token_hash = hashlib.sha256((code + str(user.id)).encode('utf-8')).hexdigest()
            data = {'user_id': user.id, 'telefono': telefono, 'code_hash': token_hash, 'expires': expires}
            file_path = os.path.join(vdir, f'verify_{user.id}.json')
            with open(file_path, 'w', encoding='utf-8') as fh:
                import json
                json.dump(data, fh)
            extra = {'debug_code': code} if getattr(settings, 'DEBUG', False) else {}
        except Exception:
            return JsonResponse({'ok': False, 'error': 'no se pudo generar código de verificación'}, status=500)

        return JsonResponse({'ok': True, 'verify_user_id': user.id, 'message': 'Usuario creado. Verifica el teléfono con el código enviado.' , **(extra if 'extra' in locals() else {})})

    return JsonResponse({'ok': False, 'error': 'Método no soportado'}, status=405)


@require_http_methods(['POST'])
def verify_phone(request):
    """Endpoint to verify a phone code. Expects: user_id, code"""
    user_id = request.POST.get('user_id') or request.GET.get('user_id')
    code = request.POST.get('code') or request.GET.get('code')
    if not user_id or not code:
        return JsonResponse({'ok': False, 'error': 'user_id y code requeridos'}, status=400)
    try:
        # File-based verification (local)
        vdir = os.path.join(settings.MEDIA_ROOT, 'phone_verifications')
        file_path = os.path.join(vdir, f'verify_{int(user_id)}.json')
        if not os.path.exists(file_path):
            return JsonResponse({'ok': False, 'error': 'No hay código de verificación para este usuario'}, status=404)
        import json
        with open(file_path, 'r', encoding='utf-8') as fh:
            data = json.load(fh)
        expires = timezone.datetime.fromisoformat(data.get('expires'))
        if timezone.now() > expires:
            return JsonResponse({'ok': False, 'error': 'Código expirado'}, status=400)
        expected_hash = data.get('code_hash')
        check_hash = hashlib.sha256((code + str(user_id)).encode('utf-8')).hexdigest()
        if check_hash != expected_hash:
            return JsonResponse({'ok': False, 'error': 'Código inválido'}, status=400)
        # mark user active
        from django.contrib.auth.models import User as DjUser
        u = DjUser.objects.get(pk=int(user_id))
        u.is_active = True
        u.save()
        # option: delete verification file
        try:
            os.remove(file_path)
        except Exception:
            pass
        return JsonResponse({'ok': True})
    except Exception as e:
        import traceback
        return JsonResponse({'ok': False, 'error': str(e), 'trace': traceback.format_exc()}, status=500)


def logout_view(request):
    logout(request)
    return redirect('/login/')


@require_http_methods(['POST'])
@login_required
def api_set_report_state(request, pk):
    # Only authenticated users can mark states; optionally restrict to moderators/admins later
    if not request.user or not request.user.is_authenticated:
        return JsonResponse({'ok': False, 'error': 'authentication required'}, status=401)
    state = request.POST.get('state') or request.GET.get('state')
    if not state:
        return JsonResponse({'ok': False, 'error': 'state required'}, status=400)
    # normalize allowed states
    allowed = ['Activo', 'En progreso', 'Resuelto']
    if state not in allowed:
        return JsonResponse({'ok': False, 'error': 'invalid state'}, status=400)
    # write status file
    try:
        statuses_dir = os.path.join(settings.MEDIA_ROOT, 'report_statuses')
        os.makedirs(statuses_dir, exist_ok=True)
        status_path = os.path.join(statuses_dir, f'report_{int(pk)}.json')
        import json as _json
        _json.dump({'state': state, 'updated_by': request.user.username, 'updated': timezone.now().isoformat()}, open(status_path, 'w', encoding='utf-8'))
        return JsonResponse({'ok': True, 'state': state})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


@login_required
def panel_administracion(request):
    # only admins
    try:
        if request.user.profile.role != 'admin':
            return redirect('/login/')
    except Exception:
        return redirect('/login/')
    return render(request, 'PanelAdministracion.html')


@login_required
def validacion_reportes(request):
    try:
        if request.user.profile.role != 'admin':
            return redirect('/login/')
    except Exception:
        return redirect('/login/')
    return render(request, 'ValidacionyComentariosReportes.html')


@login_required
def reporte_detalle_page(request, pk):
    # Page is restricted to authenticated users
    r = get_object_or_404(Reporte, pk=pk)
    try:
        zona_nombre = r.zona.nombre if getattr(r, 'zona', None) else None
    except Exception:
        zona_nombre = None
    try:
        creado_nombre = r.creado_por.username if getattr(r, 'creado_por', None) else None
    except Exception:
        creado_nombre = None

    # Lista de imagenes
    imagenes = []
    if getattr(r, 'imagen_url', None):
        imagenes.append(r.imagen_url)
    # Si model almacena varias imagenes en el modelo ComentarioImagen, trata de incluirlas
    try:
        from .models import ComentarioImagen
        imgs = ComentarioImagen.objects.filter(reporte_id=r.id)
        for i in imgs:
            if getattr(i, 'url', None): imagenes.append(i.url)
    except Exception:
        pass

    # comments placeholder: if Comentario model exists, include recent comments
    comentarios = []
    try:
        from .models import Comentario
        cs = Comentario.objects.filter(reporte_id=r.id).order_by('-fecha_creacion')[:20]
        for c in cs:
            comentarios.append({'autor': getattr(c, 'autor_nombre', None) or (c.usuario.username if getattr(c, 'usuario', None) else 'Usuario'), 'texto': c.texto if getattr(c, 'texto', None) else getattr(c, 'mensaje', ''), 'fecha': getattr(c, 'fecha_creacion', None)})
    except Exception:
        comentarios = []

    context = {
        'ubicacion': r.ubicacion,
        'tipo': r.tipo or r.prioridad,
        'descripcion': r.descripcion,
        'fecha': r.fecha_creacion,
        'imagenes': imagenes,
        'comentarios': comentarios,
        'creado_por': creado_nombre,
        'zona': zona_nombre,
        'id': r.id,
    }
    # adjunta comentarios (almacenados como archivos JSON en MEDIA_ROOT/comments/)
    try:
        comments_dir = os.path.join(settings.MEDIA_ROOT, 'comments')
        comments_file = os.path.join(comments_dir, f'report_{r.id}.json')
        if os.path.exists(comments_file):
            with open(comments_file, 'r', encoding='utf-8') as fh:
                extra = json.load(fh)
                # expected format: list of {autor, texto, fecha}
                for c in extra:
                    comentarios.append({'autor': c.get('autor'), 'texto': c.get('texto'), 'fecha': c.get('fecha')})
                context['comentarios'] = comentarios
    except Exception:
        pass
    # attach local validations summary
    try:
        vals_dir = os.path.join(settings.MEDIA_ROOT, 'validations')
        vals_file = os.path.join(vals_dir, f'report_{r.id}.json')
        validations = []
        if os.path.exists(vals_file):
            with open(vals_file, 'r', encoding='utf-8') as vf:
                validations = json.load(vf)
        context['validations'] = validations
        context['validations_count'] = len(validations)
    except Exception:
        context['validations'] = []
        context['validations_count'] = 0
    return render(request, 'ValidacionyComentariosReportes.html', context)


@require_http_methods(['GET', 'POST'])
def api_report_comment_local(request, pk):
    if not request.user or not request.user.is_authenticated:
        return JsonResponse({'ok': False, 'error': 'authentication required'}, status=401)


    if request.method == 'GET':
        comments = []
        try:
            from .models import Comentario
            cs = Comentario.objects.filter(reporte_id=pk).order_by('-fecha_creacion')[:200]
            for c in cs:
                comments.append({
                    'autor': getattr(c, 'autor_nombre', None) or (c.usuario.username if getattr(c, 'usuario', None) else 'Usuario'),
                    'texto': getattr(c, 'texto', None) or getattr(c, 'mensaje', ''),
                    'fecha': getattr(c, 'fecha_creacion', None).isoformat() if getattr(c, 'fecha_creacion', None) else None,
                })
        except Exception:
            comments = []

        try:
            comments_dir = os.path.join(settings.MEDIA_ROOT, 'comments')
            comments_file = os.path.join(comments_dir, f'report_{pk}.json')
            if os.path.exists(comments_file):
                with open(comments_file, 'r', encoding='utf-8') as fh:
                    extra = json.load(fh)
                    for c in extra:
                        comments.append({'autor': c.get('autor'), 'texto': c.get('texto'), 'fecha': c.get('fecha')})
        except Exception:
            pass
        return JsonResponse({'ok': True, 'comments': comments})

    # POST: create a comment (existing behavior)
    texto = request.POST.get('texto') or request.POST.get('comment') or ''
    if not texto or not texto.strip():
        return JsonResponse({'ok': False, 'error': 'texto requerido'}, status=400)
    autor = 'Anonimo'
    if request.user and request.user.is_authenticated:
        autor = request.user.get_full_name() or request.user.username
    comment = {'autor': autor, 'texto': texto.strip(), 'fecha': timezone.now().isoformat()}
    try:
        comments_dir = os.path.join(settings.MEDIA_ROOT, 'comments')
        os.makedirs(comments_dir, exist_ok=True)
        comments_file = os.path.join(comments_dir, f'report_{pk}.json')
        existing = []
        if os.path.exists(comments_file):
            with open(comments_file, 'r', encoding='utf-8') as fh:
                try:
                    existing = json.load(fh)
                except Exception:
                    existing = []
        existing.insert(0, comment)
        with open(comments_file, 'w', encoding='utf-8') as fh:
            json.dump(existing, fh, ensure_ascii=False, indent=2)
        return JsonResponse({'ok': True, 'comment': comment})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


@require_http_methods(['GET', 'POST'])
def api_report_validation_local(request, pk):
    """Record or return user validations for a report.
    GET: return list of validations and count
    POST: add a validation entry (dedup by username)
    """
    # Ensure authenticated (return JSON 401 for AJAX clients)
    if not request.user or not request.user.is_authenticated:
        return JsonResponse({'ok': False, 'error': 'authentication required'}, status=401)

    # GET -> return validations
    if request.method == 'GET':
        try:
            vals_dir = os.path.join(settings.MEDIA_ROOT, 'validations')
            vals_file = os.path.join(vals_dir, f'report_{pk}.json')
            existing = []
            if os.path.exists(vals_file):
                with open(vals_file, 'r', encoding='utf-8') as vf:
                    try:
                        existing = json.load(vf)
                    except Exception:
                        existing = []
            return JsonResponse({'ok': True, 'validations': existing, 'count': len(existing)})
        except Exception as e:
            return JsonResponse({'ok': False, 'error': str(e)}, status=500)

    # POST -> create validation
    username = 'anonimo'
    if request.user and request.user.is_authenticated:
        username = request.user.get_full_name() or request.user.username
    try:
        vals_dir = os.path.join(settings.MEDIA_ROOT, 'validations')
        os.makedirs(vals_dir, exist_ok=True)
        vals_file = os.path.join(vals_dir, f'report_{pk}.json')
        existing = []
        if os.path.exists(vals_file):
            with open(vals_file, 'r', encoding='utf-8') as vf:
                try:
                    existing = json.load(vf)
                except Exception:
                    existing = []
        # dedupe by username
        if any(v.get('usuario') == username for v in existing):
            return JsonResponse({'ok': False, 'error': 'ya validado', 'count': len(existing)}, status=400)
        entry = {'usuario': username, 'fecha': timezone.now().isoformat()}
        existing.append(entry)
        with open(vals_file, 'w', encoding='utf-8') as vf:
            json.dump(existing, vf, ensure_ascii=False, indent=2)
        return JsonResponse({'ok': True, 'count': len(existing)})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


### Admin API endpoints
@login_required
def api_admin_pending_reportes(request):
    if request.user.profile.role != 'admin':
        return JsonResponse({'ok': False, 'error': 'forbidden'}, status=403)
    qs = Reporte.objects.filter(estado='pendiente').select_related('zona', 'creado_por').order_by('fecha_creacion')
    out = []
    for r in qs:
        # creator contact info
        creator = None
        try:
            cp = None
            if getattr(r, 'creado_por', None):
                try:
                    cp = r.creado_por.profile
                except Exception:
                    cp = None
            creator = {
                'username': (r.creado_por.username if getattr(r, 'creado_por', None) else None),
                'email': (r.creado_por.email if getattr(r, 'creado_por', None) else None),
                'telefono': (cp.telefono if cp and getattr(cp, 'telefono', None) else None)
            }
        except Exception:
            creator = {'username': None, 'email': None, 'telefono': None}

        out.append({
            'id': r.id,
            'ubicacion': r.ubicacion,
            'descripcion': r.descripcion,
            'prioridad': r.prioridad,
            'zona': (lambda rr: (rr.zona.nombre if getattr(rr, 'zona', None) else None)) (r) if True else None,
            'coordenadas': r.coordenadas,
            'fecha_creacion': r.fecha_creacion.isoformat(),
            'imagen_url': r.imagen_url if hasattr(r, 'imagen_url') else (r.imagen.url if getattr(r, 'imagen', None) else None),
            'creado_por': creator,
        })
    return JsonResponse({'reportes': out})


@login_required
def api_admin_validated_reportes(request):
    if request.user.profile.role != 'admin':
        return JsonResponse({'ok': False, 'error': 'forbidden'}, status=403)
    qs = Reporte.objects.filter(estado='validado').select_related('zona', 'creado_por').order_by('-fecha_creacion')[:200]
    out = []
    for r in qs:
        # creator contact info
        creator = None
        try:
            cp = None
            if getattr(r, 'creado_por', None):
                try:
                    cp = r.creado_por.profile
                except Exception:
                    cp = None
            creator = {
                'username': (r.creado_por.username if getattr(r, 'creado_por', None) else None),
                'email': (r.creado_por.email if getattr(r, 'creado_por', None) else None),
                'telefono': (cp.telefono if cp and getattr(cp, 'telefono', None) else None)
            }
        except Exception:
            creator = {'username': None, 'email': None, 'telefono': None}

        out.append({
            'id': r.id,
            'ubicacion': r.ubicacion,
            'descripcion': r.descripcion,
            'prioridad': r.prioridad,
            'zona': (lambda rr: (rr.zona.nombre if getattr(rr, 'zona', None) else None)) (r) if True else None,
            'coordenadas': r.coordenadas,
            'fecha_creacion': r.fecha_creacion.isoformat() if r.fecha_creacion else None,
            'imagen_url': r.imagen_url if hasattr(r, 'imagen_url') else (r.imagen.url if getattr(r, 'imagen', None) else None),
            'creado_por': creator,
        })
    return JsonResponse({'reportes': out})


@login_required
def api_admin_reportes_search(request):
    """Search admin reports by q (text) and estado filter.
    Query params: q (string), estado (pendiente|validado|rechazado|all)
    """
    if request.user.profile.role != 'admin':
        return JsonResponse({'ok': False, 'error': 'forbidden'}, status=403)
    q = request.GET.get('q') or request.GET.get('query')
    estado = request.GET.get('estado') or request.GET.get('status') or 'all'
    qs = Reporte.objects.all().select_related('zona', 'creado_por')
    if estado and estado != 'all':
        qs = qs.filter(estado=estado)
    if q and q.strip():
        ql = q.strip()
        # search in ubicacion, descripcion, creado_por username/email
        from django.db.models import Q
        qs = qs.filter(
            Q(ubicacion__icontains=ql) | Q(descripcion__icontains=ql) | Q(creado_por__username__icontains=ql) | Q(creado_por__email__icontains=ql)
        )
    qs = qs.order_by('-fecha_creacion')[:500]
    out = []
    for r in qs:
        # creator info
        try:
            cp = None
            if getattr(r, 'creado_por', None):
                try:
                    cp = r.creado_por.profile
                except Exception:
                    cp = None
            creator = {
                'username': (r.creado_por.username if getattr(r, 'creado_por', None) else None),
                'email': (r.creado_por.email if getattr(r, 'creado_por', None) else None),
                'telefono': (cp.telefono if cp and getattr(cp, 'telefono', None) else None)
            }
        except Exception:
            creator = {'username': None, 'email': None, 'telefono': None}

        out.append({
            'id': r.id,
            'ubicacion': r.ubicacion,
            'descripcion': r.descripcion,
            'prioridad': r.prioridad,
            'estado': r.estado,
            'zona': (lambda rr: (rr.zona.nombre if getattr(rr, 'zona', None) else None)) (r) if True else None,
            'coordenadas': r.coordenadas,
            'fecha_creacion': r.fecha_creacion.isoformat() if r.fecha_creacion else None,
            'imagen_url': r.imagen_url if hasattr(r, 'imagen_url') else (r.imagen.url if getattr(r, 'imagen', None) else None),
            'creado_por': creator,
        })
    return JsonResponse({'reportes': out})


@require_POST
@login_required
def api_admin_validar_reporte(request, pk):
    if request.user.profile.role != 'admin':
        return JsonResponse({'ok': False, 'error': 'forbidden'}, status=403)
    r = get_object_or_404(Reporte, pk=pk)
    r.estado = 'validado'
    r.save()
    return JsonResponse({'ok': True})


@require_POST
@login_required
def api_admin_rechazar_reporte(request, pk):
    if request.user.profile.role != 'admin':
        return JsonResponse({'ok': False, 'error': 'forbidden'}, status=403)
    r = get_object_or_404(Reporte, pk=pk)
    r.estado = 'rechazado'
    r.save()
    return JsonResponse({'ok': True})


@require_POST
@login_required
def api_admin_eliminar_reporte(request, pk):
    """Permanently delete a report that has been previously validated.

    This removes the DB row (or raw SQL delete), deletes any stored
    JSON artifacts under MEDIA_ROOT (comments, validations), and removes
    the stored image file if present. Only admins may call this.
    """
    try:
        if request.user.profile.role != 'admin':
            return JsonResponse({'ok': False, 'error': 'forbidden'}, status=403)
    except Exception:
        return JsonResponse({'ok': False, 'error': 'forbidden'}, status=403)

    # Fetch the report and ensure it was validated
    r = get_object_or_404(Reporte, pk=pk)
    if getattr(r, 'estado', None) != 'validado':
        return JsonResponse({'ok': False, 'error': 'only validated reports can be permanently deleted'}, status=400)

    # Delete file-based artifacts: comments, validations
    try:
        comments_dir = os.path.join(settings.MEDIA_ROOT, 'comments')
        comments_file = os.path.join(comments_dir, f'report_{r.id}.json')
        if os.path.exists(comments_file):
            os.remove(comments_file)
    except Exception:
        pass

    try:
        vals_dir = os.path.join(settings.MEDIA_ROOT, 'validations')
        vals_file = os.path.join(vals_dir, f'report_{r.id}.json')
        if os.path.exists(vals_file):
            os.remove(vals_file)
    except Exception:
        pass

    # Delete stored image file if it exists and is under report_images
    try:
        if getattr(r, 'imagen', None):
            img_path = os.path.join(settings.MEDIA_ROOT, str(r.imagen))
            if os.path.exists(img_path):
                os.remove(img_path)
    except Exception:
        pass

    # Delete any multimedia/comment DB rows that reference this report (best-effort)
    try:
        from .models import Comentario, Multimedia
        try:
            Comentario.objects.filter(reporte_id=r.id).delete()
        except Exception:
            pass
        try:
            Multimedia.objects.filter(reporte_id=r.id).delete()
        except Exception:
            pass
    except Exception:
        pass

    # Finally remove the report row. Use raw SQL delete to be safe with legacy managed=False models
    try:
        with connection.cursor() as cur:
            cur.execute('DELETE FROM "Backend_reporte" WHERE id = %s', [r.id])
    except Exception:
        # fallback to model delete
        try:
            r.delete()
        except Exception as e:
            return JsonResponse({'ok': False, 'error': 'could not delete report', 'detail': str(e)}, status=500)

    return JsonResponse({'ok': True})


@login_required
def api_admin_reporte_detail(request, pk):
    # return detailed info for a report (used by admin 'Ver' action)
    if request.user.profile.role != 'admin':
        return JsonResponse({'ok': False, 'error': 'forbidden'}, status=403)
    r = get_object_or_404(Reporte, pk=pk)
    # Defensive access to related objects (legacy DB may have missing FK targets)
    try:
        zona_nombre = r.zona.nombre if getattr(r, 'zona', None) else None
    except Exception:
        zona_nombre = None
    try:
        creado_nombre = r.creado_por.username if getattr(r, 'creado_por', None) else None
    except Exception:
        creado_nombre = None
    return JsonResponse({
        'id': r.id,
        'ubicacion': r.ubicacion,
        'descripcion': r.descripcion,
        'prioridad': r.prioridad,
        'tipo': r.tipo,
        'estado': r.estado,
        'zona': zona_nombre,
        'coordenadas': r.coordenadas,
        'fecha_creacion': r.fecha_creacion.isoformat() if r.fecha_creacion else None,
        'imagen_url': r.imagen_url if getattr(r, 'imagen_url', None) else None,
        'creado_por': creado_nombre,
    })


@login_required
def api_admin_users(request):
    """Return list of users for admin panel."""
    if request.user.profile.role != 'admin':
        return JsonResponse({'ok': False, 'error': 'forbidden'}, status=403)
    from django.contrib.auth.models import User
    qs = User.objects.all().order_by('id')
    out = []
    for u in qs:
        try:
            role = u.profile.role
        except Exception:
            role = 'admin' if (u.is_superuser or u.is_staff) else 'user'
        out.append({
            'id': u.id,
            'username': u.username,
            'email': u.email,
            'nombre': u.get_full_name(),
            'role': role,
        })
    return JsonResponse({'users': out})


@login_required
def api_admin_counts(request):
    """Return summary counts for admin dashboard: pending reports, total users, comunicados (comentarios)."""
    if request.user.profile.role != 'admin':
        return JsonResponse({'ok': False, 'error': 'forbidden'}, status=403)
    from django.contrib.auth.models import User
    pending = Reporte.objects.filter(estado='pendiente').count()
    validated = Reporte.objects.filter(estado='validado').count()
    users = User.objects.count()
    comunicados = 0
    try:
        from .models import Comentario
        comunicados = Comentario.objects.count()
    except Exception:
        comunicados = 0
    return JsonResponse({'pending_reportes': pending, 'validated_reportes': validated, 'users_total': users, 'comunicados_recientes': comunicados})


@login_required
def api_admin_whoami(request):
    try:
        role = request.user.profile.role
    except Exception:
        role = 'admin' if (request.user.is_superuser or request.user.is_staff) else 'user'
    return JsonResponse({'username': request.user.username, 'role': role})


def api_tipo_labels(request):
    """Return canonical mapping of tipo keys to display labels."""
    labels = {
        'robo': 'Robo',
        'asalto': 'Asalto',
        'hurto': 'Hurto',
        'vandalismo': 'Vandalismo',
        'iluminacion': 'Poca Iluminación',
        'accidente': 'Accidente de Tránsito',
        'violencia': 'Violencia',
        'consumo_drogas': 'Consumo/Venta de Drogas',
        'incendio': 'Incendio',
        'amenaza': 'Amenaza',
        'otro': 'Otro',
        'robo_vehiculo': 'Robo de Vehículos',
        'acoso_callejero': 'Acoso Callejero',
        'prostitucion_ilegal': 'Prostitución Ilegal',
        'fraude_estafa': 'Fraudes y Estafas'
    }
    return JsonResponse({'labels': labels})


@login_required
def api_whoami(request):
    """Public endpoint for frontend to know current user and role."""
    try:
        role = request.user.profile.role
    except Exception:
        role = 'admin' if (request.user.is_superuser or request.user.is_staff) else 'user'
    # try to read a persisted profile photo from the legacy Backend_userprofile table (if present)
    photo_url = None
    try:
        with connection.cursor() as cur:
            # try to select the foto column; if it doesn't exist this will raise
            cur.execute('SELECT foto FROM "Backend_userprofile" WHERE user_id = %s', [request.user.id])
            row = cur.fetchone()
        if row and row[0]:
            foto_path = row[0]
            if foto_path.startswith('http'):
                photo_url = foto_path
            else:
                photo_url = settings.MEDIA_URL.rstrip('/') + '/' + str(foto_path).lstrip('/')
    except Exception:
        # ignore DB errors (legacy schema differences) and return without photo
        photo_url = None

    # If DB didn't return a foto, try to find a saved file in MEDIA/profile_photos
    if not photo_url:
        try:
            folder = os.path.join(settings.MEDIA_ROOT, 'profile_photos')
            if os.path.isdir(folder):
                candidates = [f for f in os.listdir(folder) if f.startswith(f'profile_{request.user.id}_')]
                if candidates:
                    # pick most recently modified
                    candidates.sort(key=lambda fn: os.path.getmtime(os.path.join(folder, fn)), reverse=True)
                    chosen = candidates[0]
                    photo_url = settings.MEDIA_URL.rstrip('/') + '/' + os.path.join('profile_photos', chosen).replace('\\','/')
        except Exception:
            photo_url = None

    return JsonResponse({'ok': True, 'username': request.user.username, 'email': request.user.email, 'role': role, 'photo_url': photo_url})


@login_required
@require_http_methods(['POST'])
def api_create_comunicado(request):
    """Admin creates a comunicado and we create notifications for all users (simple implementation).
    Expects: title, body, prioridad (optional)
    """
    try:
        if request.user.profile.role != 'admin':
            return JsonResponse({'ok': False, 'error': 'forbidden'}, status=403)
    except Exception:
        return JsonResponse({'ok': False, 'error': 'forbidden'}, status=403)

    title = request.POST.get('title') or request.POST.get('titulo')
    body = request.POST.get('body') or request.POST.get('cuerpo')
    prioridad = request.POST.get('prioridad')
    if not title or not body:
        return JsonResponse({'ok': False, 'error': 'title and body required'}, status=400)

    # insert into comunicado and notificacion / notificacion_destinatario using raw SQL to avoid model mismatch
    with connection.cursor() as cur:
        cur.execute("INSERT INTO comunicado (titulo, cuerpo, usuario_creador, prioridad, fecha_publicacion) VALUES (%s,%s,%s,%s,now()) RETURNING id", [title, body, request.user.id, prioridad])
        comunicado_id = cur.fetchone()[0]
        # create a notification entry
        cur.execute("INSERT INTO notificacion (tipo, titulo, cuerpo, usuario_creador, fecha_creacion) VALUES (%s,%s,%s,%s,now()) RETURNING id", ['comunicado', title, body, request.user.id])
        noti_id = cur.fetchone()[0]
        # broadcast to all users (note: for large userbases this should be async/batched)
        cur.execute("INSERT INTO notificacion_destinatario (notificacion, usuario_destinatario, leida, fecha_creacion) SELECT %s, id, false, now() FROM usuario", [noti_id])

    return JsonResponse({'ok': True, 'comunicado_id': comunicado_id, 'notificacion_id': noti_id})


@login_required
def api_notificaciones_list(request):
    """Return the current user's notifications (most recent first).
    Query the legacy notificacion_destinatario table.
    """
    uid = request.user.id
    with connection.cursor() as cur:
        cur.execute("SELECT nd.id, n.titulo, n.cuerpo, nd.leida, nd.fecha_creacion FROM notificacion_destinatario nd JOIN notificacion n ON n.id = nd.notificacion WHERE nd.usuario_destinatario = %s ORDER BY nd.fecha_creacion DESC LIMIT 50", [uid])
        rows = cur.fetchall()
    notis = []
    for r in rows:
        nid, title, body, leida, fecha = r
        summary = (body[:140] + '...') if body and len(body) > 140 else (body or '')
        notis.append({'id': nid, 'titulo': title, 'resumen': summary, 'leida': bool(leida), 'fecha': fecha.isoformat() if fecha else None})
    return JsonResponse({'notificaciones': notis})


@login_required
@require_http_methods(['POST'])
def api_notificacion_marcar_leida(request, pk):
    uid = request.user.id
    with connection.cursor() as cur:
        cur.execute("UPDATE notificacion_destinatario SET leida = true, fecha_lectura = now() WHERE id = %s AND usuario_destinatario = %s", [pk, uid])
    return JsonResponse({'ok': True})


@login_required
def api_notificacion_detail(request, pk):
    uid = request.user.id
    with connection.cursor() as cur:
        cur.execute("SELECT n.id, n.titulo, n.cuerpo, n.datos_extra, n.fecha_creacion FROM notificacion n JOIN notificacion_destinatario nd ON nd.notificacion = n.id WHERE nd.id = %s AND nd.usuario_destinatario = %s", [pk, uid])
        row = cur.fetchone()
    if not row:
        return JsonResponse({'ok': False, 'error': 'not found'}, status=404)
    nid, title, body, datos_extra, fecha = row
    return JsonResponse({'id': nid, 'titulo': title, 'cuerpo': body, 'datos_extra': datos_extra, 'fecha_creacion': fecha.isoformat() if fecha else None})


@login_required
@require_http_methods(['POST'])
def api_profile_update(request):
    """Allow user to update display name and profile photo (simple implementation using default storage).
    Accepts: username, photo (file)
    """
    user = request.user
    username = request.POST.get('username')
    if username and username.strip():
        user.username = username.strip()
        user.save()

    if 'photo' in request.FILES:
        f = request.FILES['photo']
        # store under MEDIA_ROOT/profile_photos/<user_id>_<filename>
        dest_dir = os.path.join(settings.MEDIA_ROOT, 'profile_photos')
        os.makedirs(dest_dir, exist_ok=True)
        dest_name = f"profile_{user.id}_{f.name}"
        path = default_storage.save(os.path.join('profile_photos', dest_name), ContentFile(f.read()))
        # Persist the stored path into the legacy Backend_userprofile table under a new 'foto' column.
        photo_db_value = path
        try:
            with connection.cursor() as cur:
                # Try to update existing profile row
                cur.execute('UPDATE "Backend_userprofile" SET foto = %s WHERE user_id = %s', [photo_db_value, user.id])
                if cur.rowcount == 0:
                    # no existing row, create one with sane defaults
                    cur.execute('INSERT INTO "Backend_userprofile" (user_id, role, telefono, foto) VALUES (%s, %s, %s, %s)', [user.id, 'user', '', photo_db_value])
        except Exception:
            # possibly the column doesn't exist; attempt to add it and retry
            try:
                with connection.cursor() as cur:
                    cur.execute('ALTER TABLE "Backend_userprofile" ADD COLUMN foto varchar(512)')
                    cur.execute('UPDATE "Backend_userprofile" SET foto = %s WHERE user_id = %s', [photo_db_value, user.id])
                    if cur.rowcount == 0:
                        cur.execute('INSERT INTO "Backend_userprofile" (user_id, role, telefono, foto) VALUES (%s, %s, %s, %s)', [user.id, 'user', '', photo_db_value])
            except Exception:
                # If even this fails, swallow the exception and continue (we still return the generated URL)
                pass

        photo_url = settings.MEDIA_URL.rstrip('/') + '/' + path.lstrip('/')
    else:
        photo_url = None

    return JsonResponse({'ok': True, 'username': user.username, 'photo_url': photo_url})


@require_POST
@login_required
def api_admin_user_set_role(request, pk):
    if request.user.profile.role != 'admin':
        return JsonResponse({'ok': False, 'error': 'forbidden'}, status=403)
    from django.contrib.auth.models import User
    u = get_object_or_404(User, pk=pk)
    role = request.POST.get('role') or request.GET.get('role')
    if role not in ('admin', 'user', 'moderator'):
        return JsonResponse({'ok': False, 'error': 'invalid role'}, status=400)
    profile, created = UserProfile.objects.get_or_create(user=u, defaults={'role': role})
    if not created:
        profile.role = role
        profile.save()
    return JsonResponse({'ok': True})


@require_POST
@login_required
def api_admin_user_delete(request, pk):
    if request.user.profile.role != 'admin':
        return JsonResponse({'ok': False, 'error': 'forbidden'}, status=403)
    from django.contrib.auth.models import User
    u = get_object_or_404(User, pk=pk)
    # Prevent deleting self
    if u == request.user:
        return JsonResponse({'ok': False, 'error': 'cannot delete self'}, status=400)
    u.delete()
    return JsonResponse({'ok': True})
