from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Twilio integration removed; this command is a no-op.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('Twilio integration has been removed from this project.'))
