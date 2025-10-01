from django.apps import AppConfig


class ReportesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    # Use the full Python path to the app so Django can import it when
    # referenced as 'secuseo_project.reportes' in INSTALLED_APPS.
    name = 'secuseo_project.reportes'
