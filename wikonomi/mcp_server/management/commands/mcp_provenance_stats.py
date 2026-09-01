"""Read-only internal reporting; no provenance is exposed by a public endpoint."""

import json

from django.core.management.base import BaseCommand
from django.db.models import Count, Q
from django.utils import timezone

from core.models import PriceReport, Product
from guides.models import Guide, GuideVersion


class Command(BaseCommand):
    help = 'Report stored AI-assisted and MCP contribution counts as JSON (read-only).'

    def handle(self, *args, **options):
        report = {
            'generated_at': timezone.now().isoformat(),
            'basis': 'Currently stored records, not a lifetime total of deleted contributions.',
        }
        for name, model in (
            ('prices', PriceReport),
            ('products', Product),
            ('guides', Guide),
            ('guide_versions', GuideVersion),
        ):
            report[name] = model.objects.aggregate(
                total=Count('pk'),
                ai_assisted=Count('pk', filter=Q(ai_assisted=True)),
                mcp=Count('pk', filter=Q(created_via='mcp')),
            )
        report['ai_price_breakdown'] = list(
            PriceReport.objects.filter(ai_assisted=True)
            .values('ai_provider', 'ai_model')
            .annotate(count=Count('pk'))
            .order_by('-count', 'ai_provider', 'ai_model')
        )
        self.stdout.write(json.dumps(report, indent=2))
