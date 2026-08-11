from django.core.management.base import BaseCommand

from transport_index.services import FRESHNESS_MINUTES, set_stale_statuses_offline


class Command(BaseCommand):
    help = 'Mark available cab listings offline when location freshness expires.'

    def add_arguments(self, parser):
        parser.add_argument('--minutes', type=int, default=FRESHNESS_MINUTES)

    def handle(self, *args, **options):
        count = set_stale_statuses_offline(options['minutes'])
        self.stdout.write(self.style.SUCCESS(f'Marked {count} stale cab status(es) offline.'))
