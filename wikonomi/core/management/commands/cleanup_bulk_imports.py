from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import BulkImportSession


class Command(BaseCommand):
    help = 'Delete expired bulk-import staging files and database sessions.'

    def handle(self, *args, **options):
        sessions = BulkImportSession.objects.filter(
            expires_at__lt=timezone.now()
        ).prefetch_related('images')
        deleted = 0
        for session in sessions.iterator(chunk_size=100):
            if session.inventory_file:
                session.inventory_file.delete(save=False)
            for image in session.images.all():
                if image.file:
                    image.file.delete(save=False)
            session.delete()
            deleted += 1
        self.stdout.write(self.style.SUCCESS(
            f'Deleted {deleted} expired bulk import session(s).'
        ))
