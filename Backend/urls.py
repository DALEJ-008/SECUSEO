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
    path('reportes/<int:pk>/', views.reporte_detalle_page, name='reporte_detalle_page'),
    # Local endpoints for comments and simple validations (stored as JSON under MEDIA_ROOT)
    path('api/reportes/<int:pk>/comentario-local/', views.api_report_comment_local, name='api_report_comment_local'),
    path('api/reportes/<int:pk>/validar-local/', views.api_report_validation_local, name='api_report_validation_local'),
    # Admin APIs
    path('admin/api/reportes/pending/', views.api_admin_pending_reportes, name='api_admin_pending_reportes'),
    path('admin/api/reportes/<int:pk>/validar/', views.api_admin_validar_reporte, name='api_admin_validar_reporte'),
    path('admin/api/reportes/<int:pk>/rechazar/', views.api_admin_rechazar_reporte, name='api_admin_rechazar_reporte'),
    path('admin/api/reportes/<int:pk>/detail/', views.api_admin_reporte_detail, name='api_admin_reporte_detail'),
    path('admin/api/reportes/<int:pk>/eliminar/', views.api_admin_eliminar_reporte, name='api_admin_eliminar_reporte'),
    path('admin/api/reportes/validated/', views.api_admin_validated_reportes, name='api_admin_validated_reportes'),
    path('admin/api/reportes/search/', views.api_admin_reportes_search, name='api_admin_reportes_search'),
    # User management
    path('admin/api/users/', views.api_admin_users, name='api_admin_users'),
    path('admin/api/users/<int:pk>/set-role/', views.api_admin_user_set_role, name='api_admin_user_set_role'),
    path('admin/api/users/<int:pk>/delete/', views.api_admin_user_delete, name='api_admin_user_delete'),
    path('admin/api/counts/', views.api_admin_counts, name='api_admin_counts'),
    path('admin/api/whoami/', views.api_admin_whoami, name='api_admin_whoami'),
    # Notifications and comunicados
    path('api/comunicado/create/', views.api_create_comunicado, name='api_create_comunicado'),
    path('api/notificaciones/', views.api_notificaciones_list, name='api_notificaciones_list'),
    path('api/notificaciones/<int:pk>/leer/', views.api_notificacion_marcar_leida, name='api_notificacion_marcar_leida'),
    path('api/notificaciones/<int:pk>/detail/', views.api_notificacion_detail, name='api_notificacion_detail'),
    path('api/whoami/', views.api_whoami, name='api_whoami'),
    path('api/profile/update/', views.api_profile_update, name='api_profile_update'),
    path('verify-phone/', views.verify_phone, name='verify_phone'),
]
