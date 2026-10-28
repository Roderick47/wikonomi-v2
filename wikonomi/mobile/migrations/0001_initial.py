import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("core", "0013_mcp_ai_provenance"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="MobileSubmission",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("client_submission_id", models.UUIDField(unique=True, db_index=True)),
                ("price", models.DecimalField(max_digits=12, decimal_places=2)),
                ("photo", models.ImageField(upload_to="mobile_price_evidence/%Y/%m/")),
                ("observed_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("submitted_at", models.DateTimeField(auto_now_add=True)),
                ("status", models.CharField(
                    max_length=12, default="pending", db_index=True,
                    choices=[("pending", "Pending review"), ("approved", "Approved"), ("rejected", "Rejected")],
                )),
                ("reviewed_at", models.DateTimeField(null=True, blank=True)),
                ("review_note", models.TextField(blank=True)),
                ("business_branch", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT, related_name="mobile_submissions", to="core.businessbranch",
                )),
                ("product", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT, related_name="mobile_submissions", to="core.product",
                )),
                ("contributor", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name="mobile_price_submissions", to=settings.AUTH_USER_MODEL,
                )),
                ("reviewed_by", models.ForeignKey(
                    on_delete=django.db.models.deletion.SET_NULL, null=True, blank=True,
                    related_name="reviewed_mobile_submissions", to=settings.AUTH_USER_MODEL,
                )),
                ("published_report", models.OneToOneField(
                    on_delete=django.db.models.deletion.SET_NULL, null=True, blank=True,
                    related_name="mobile_submission", to="core.pricereport",
                )),
            ],
            options={"ordering": ["-submitted_at"]},
        ),
        migrations.AddIndex(
            model_name="mobilesubmission",
            index=models.Index(fields=["contributor", "-submitted_at"], name="mobile_sub_contrib_1"),
        ),
        migrations.AddIndex(
            model_name="mobilesubmission",
            index=models.Index(fields=["status", "-submitted_at"], name="mobile_sub_status_1"),
        ),
    ]
