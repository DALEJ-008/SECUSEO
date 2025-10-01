from django.urls import path
from . import views

app_name = 'Backend'

urlpatterns = [
    path('api/reportes/', views.lista_reportes, name='lista_reportes'),
    path('api/zonas/', views.lista_zonas, name='lista_zonas'),
    path('api/reportes/crear/', views.crear_reporte, name='crear_reporte'),
    path('api/reportes/<int:pk>/', views.detalle_reporte, name='detalle_reporte'),
    # Frontend pages
    path('', views.pagina_principal, name='pagina_principal'),
    path('reporte/form/', views.formulario_reporte, name='formulario_reporte'),
    path('login/', views.inicio_sesion, name='inicio_sesion'),
    path('logout/', views.logout_view, name='logout'),
    path('admin-panel/', views.panel_administracion, name='panel_administracion'),
    path('reportes/validacion/', views.validacion_reportes, name='validacion_reportes'),
]
