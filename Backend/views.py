from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from .models import Reporte, Zona, UserProfile
from .forms import ReporteForm, ComentarioForm
import json

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.views.decorators.csrf import csrf_exempt


def logout_view(request):
    # log the user out and redirect to login page
    logout(request)
    return redirect('/login/')


def _point_in_polygon(lon, lat, polygon_coords):
    # polygon_coords: list of linear rings (outer ring first). We'll test against outer ring only.
    # Ray casting algorithm for point-in-polygon
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

    # polygon_coords can be nested multipolygons; handle simple Polygon first
    if not polygon_coords:
        return False
    # If MultiPolygon-like (list of polygons), check each
    if isinstance(polygon_coords[0][0], list) and isinstance(polygon_coords[0][0][0], list):
        for poly in polygon_coords:
            if _ring_contains(lon, lat, poly[0]):
                return True
        return False
    # Otherwise treat as a single ring
    return _ring_contains(lon, lat, polygon_coords[0])

# Minimal views that serve JSON endpoints consumed by the static frontend (if needed)

def lista_reportes(request):
    # Only return reports that have been validated by an admin; pending reports should not appear on the public map
    qs = Reporte.objects.filter(estado='validado').select_related('zona', 'creado_por')[:100]
    data = []
    for r in qs:
        data.append({
            'id': r.id,
            'ubicacion': r.ubicacion,
            'descripcion': r.descripcion,
            'prioridad': r.prioridad,
            'estado': r.estado,
            'zona': r.zona.nombre if r.zona else None,
            'coordenadas': r.coordenadas,
            'fecha_creacion': r.fecha_creacion.isoformat(),
        })
    return JsonResponse({'reportes': data})


def lista_zonas(request):
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


def detalle_reporte(request, pk):
    r = get_object_or_404(Reporte, pk=pk)
    return JsonResponse({
        'id': r.id,
        'ubicacion': r.ubicacion,
        'descripcion': r.descripcion,
        'prioridad': r.prioridad,
        'estado': r.estado,
        'zona': r.zona.nombre if r.zona else None,
    })


def crear_reporte(request):
    if request.method == 'POST':
        # accept multipart/form-data for images
        form = ReporteForm(request.POST, request.FILES)
        if form.is_valid():
            rep = form.save(commit=False)
            # parse coordinates: accept 'lat' and 'lng' fields or a 'coordenadas' json
            lat = request.POST.get('lat')
            lng = request.POST.get('lng')
            if not lat or not lng:
                # try coordenadas json
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
                    # determine zona by checking point-in-polygon against Zona.geometria
                    zonas = Zona.objects.exclude(geometria__isnull=True)
                    found = None
                    for z in zonas:
                        geom = z.geometria
                        if not geom: continue
                        coords = geom.get('coordinates')
                        if _point_in_polygon(lngf, latf, coords):
                            found = z
                            break
                    if found:
                        rep.zona = found
                except ValueError:
                    pass

            if request.user.is_authenticated:
                rep.creado_por = request.user

            # handle image file
            if 'imagen' in request.FILES:
                rep.imagen = request.FILES['imagen']

            rep.save()
            return JsonResponse({'ok': True, 'id': rep.id})
        return JsonResponse({'ok': False, 'errors': form.errors}, status=400)
    return JsonResponse({'ok': False, 'error': 'POST required'}, status=405)


def pagina_principal(request):
    return render(request, 'PaginaPrincipal.html')


def formulario_reporte(request):
    form = ReporteForm()
    return render(request, 'FormularioReporte.html', {'form': form})


def inicio_sesion(request):
    # Serve login/register page on GET
    if request.method == 'GET':
        return render(request, 'InicioSesion.html')

    # Handle POST actions: login or register (AJAX expected)
    action = request.POST.get('action') or request.GET.get('action')
    if action == 'login':
        email = request.POST.get('email')
        password = request.POST.get('password')
        if not email or not password:
            return JsonResponse({'ok': False, 'error': 'credenciales requeridas'}, status=400)

        # Find user by email
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            return JsonResponse({'ok': False, 'error': 'El correo no está registrado. Por favor regístrate.'}, status=400)

        user = authenticate(request, username=user.username, password=password)
        if user is None:
            return JsonResponse({'ok': False, 'error': 'Credenciales inválidas'}, status=400)

        login(request, user)
        # Determine redirect based on role
        role = 'user'
        try:
            role = user.profile.role
        except Exception:
            pass
        if role == 'admin':
            return JsonResponse({'ok': True, 'redirect': '/admin-panel/'} )
        return JsonResponse({'ok': True, 'redirect': '/'} )

    if action == 'register':
        name = request.POST.get('name')
        email = request.POST.get('email')
        password = request.POST.get('password')
        dob = request.POST.get('dob')
        if not email or not password or not name:
            return JsonResponse({'ok': False, 'error': 'Nombre, correo y contraseña son requeridos'}, status=400)

        if User.objects.filter(email__iexact=email).exists():
            return JsonResponse({'ok': False, 'error': 'El correo ya está registrado. Intenta iniciar sesión.'}, status=400)

        # create user: use email as username
        username = email.split('@')[0]
        # ensure unique username
        base = username
        i = 1
        while User.objects.filter(username=username).exists():
            username = f"{base}{i}"
            i += 1

        user = User.objects.create(username=username, email=email, first_name=name)
        user.set_password(password)
        user.save()

        # create profile
        profile = UserProfile.objects.create(user=user, role='user')

        # auto-login after register
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return JsonResponse({'ok': True, 'redirect': '/'} )
        return JsonResponse({'ok': True, 'redirect': '/login/'} )

    return JsonResponse({'ok': False, 'error': 'Método no soportado'}, status=405)


def panel_administracion(request):
    # The admin panel HTML is static; real admin actions should use Django admin.
    return render(request, 'PanelAdministracion.html')


def validacion_reportes(request):
    return render(request, 'ValidacionyComentariosReportes.html')
