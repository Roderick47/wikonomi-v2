import json
import uuid
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import connection, transaction
from django.db.models import Q
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.urls import reverse
from django.utils.http import urlencode
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods

from core.models import BusinessBranch, Product
from .forms import MobileSubmissionForm
from .models import MobileSubmission


@login_required
@never_cache
@require_GET
def home(request):
    submissions = (
        MobileSubmission.objects.filter(contributor=request.user)
        .select_related("product", "business_branch__canonical_business")[:20]
    )
    return render(request, "mobile/home.html", {
        "submissions": submissions,
        "approved_count": MobileSubmission.objects.filter(
            contributor=request.user,
            status=MobileSubmission.Status.APPROVED,
        ).count(),
        "pending_count": MobileSubmission.objects.filter(
            contributor=request.user,
            status=MobileSubmission.Status.PENDING,
        ).count(),
    })


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def submit(request):
    if request.method == "POST":
        # Check replay identifiers before ModelForm's unique-field validation.
        # Retries from the same contributor succeed without creating duplicates.
        try:
            identifier = uuid.UUID(request.POST.get("client_submission_id", ""))
        except (TypeError, ValueError, AttributeError):
            identifier = None
        if identifier:
            existing = MobileSubmission.objects.filter(
                client_submission_id=identifier,
            ).only("contributor_id").first()
            if existing:
                if existing.contributor_id != request.user.pk:
                    raise PermissionDenied("Invalid submission ID.")
                return redirect(
                    reverse("mobile:home") + "?created=" + str(identifier)
                )
        form = MobileSubmissionForm(request.POST, request.FILES)
        if form.is_valid():
            recent_count = MobileSubmission.objects.filter(
                contributor=request.user,
                submitted_at__gte=timezone.now() - timedelta(hours=1),
            ).count()
            if recent_count >= 20:
                form.add_error(None, "Upload limit reached. Please try again in an hour.")
                return render(request, "mobile/submit.html", {
                    "form": form,
                    "product_label": form.cleaned_data["product"].name,
                    "branch_label": form.cleaned_data["business_branch"].get_full_name(),
                }, status=429)
            submission = form.save(commit=False)
            identifier = form.cleaned_data["client_submission_id"]
            with transaction.atomic():
                existing = MobileSubmission.objects.filter(
                    client_submission_id=identifier,
                ).first()
                if existing:
                    if existing.contributor_id != request.user.pk:
                        raise PermissionDenied("Invalid submission ID.")
                else:
                    submission.contributor = request.user
                    submission.client_submission_id = identifier
                    submission.save()
            return redirect(
                reverse("mobile:home") + "?created=" + str(identifier)
            )
    else:
        form = MobileSubmissionForm()

    product = Product.objects.filter(
        pk=request.POST.get("product")
    ).first() if request.method == "POST" else None
    branch = BusinessBranch.objects.filter(
        pk=request.POST.get("business_branch")
    ).select_related("canonical_business").first() if request.method == "POST" else None

    return render(request, "mobile/submit.html", {
        "form": form,
        "product_label": product.name if product else "",
        "branch_label": branch.get_full_name() if branch else "",
    })


@login_required
@require_GET
def search_products(request):
    query = request.GET.get("q", "").strip()[:80]
    if len(query) < 2:
        return JsonResponse({"results": []})
    matches = Product.objects.filter(name__icontains=query).order_by("name")[:12]
    return JsonResponse({"results": [
        {"id": obj.pk, "name": obj.name} for obj in matches
    ]})


@login_required
@require_GET
def search_branches(request):
    query = request.GET.get("q", "").strip()[:80]
    if len(query) < 2:
        return JsonResponse({"results": []})
    matches = (
        BusinessBranch.objects.filter(is_active=True)
        .filter(Q(name__icontains=query) | Q(canonical_business__name__icontains=query))
        .select_related("canonical_business").order_by("canonical_business__name", "name")[:12]
    )
    return JsonResponse({"results": [
        {"id": obj.pk, "name": obj.get_full_name()} for obj in matches
    ]})


@require_GET
def manifest(request):
    data = {
        "id": "/app/",
        "name": "Wikonomi Contributor",
        "short_name": "Wikonomi",
        "description": "Help Papua New Guinea compare prices by sharing prices you see.",
        "start_url": "/app/",
        "scope": "/app/",
        "display": "standalone",
        "background_color": "#f7f8fc",
        "theme_color": "#5149dd",
        "icons": [
            {"src": "/static/mobile/icons/icon.svg", "sizes": "any",
             "type": "image/svg+xml", "purpose": "any"},
            {"src": "/static/mobile/icons/icon.svg", "sizes": "any",
             "type": "image/svg+xml", "purpose": "any maskable"},
        ],
    }
    return HttpResponse(
        json.dumps(data), content_type="application/manifest+json",
    )


@require_GET
def service_worker(request):
    file_path = Path(__file__).resolve().parent / "static/mobile/sw.js"
    response = HttpResponse(
        file_path.read_text(encoding="utf-8"),
        content_type="application/javascript",
    )
    response["Cache-Control"] = "no-cache"
    response["Service-Worker-Allowed"] = "/app/"
    return response


@login_required
@never_cache
@require_GET
def evidence(request, submission_id):
    """Private original price-tag photo for its contributor or review staff."""
    submission = get_object_or_404(MobileSubmission, pk=submission_id)
    if not request.user.is_staff and submission.contributor_id != request.user.pk:
        raise PermissionDenied("You cannot view this price evidence.")
    # FieldFile.open streams from the configured default storage, including
    # S3-compatible storage; never expose the underlying storage URL directly.
    return FileResponse(
        submission.photo.open("rb"),
        as_attachment=False,
        filename=submission.photo.name.rsplit("/", 1)[-1],
        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
    )


@never_cache
@require_GET
def staging_db_status(request):
    """Minimal readiness probe available only on the dedicated staging domain.

    No database host, credentials, username, or database name is returned.
    """
    if (
        request.get_host().split(":")[0] != "wikonomi-mobile-staging.onrender.com"
        or not hasattr(settings, "MOBILE_STAGING_EPHEMERAL_DB")
    ):
        raise Http404()

    ready = (
        not settings.MOBILE_STAGING_EPHEMERAL_DB
        and connection.vendor == "postgresql"
    )
    migrated = False
    if ready:
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT 1 FROM django_migrations WHERE app = %s "
                    "AND name = %s LIMIT 1", ["mobile", "0001_initial"]
                )
                migrated = cursor.fetchone() is not None
        except Exception:
            ready = False
    result = bool(ready and migrated)
    response = JsonResponse(
        {"staging_database_ready": result, "mobile_migrations_ready": migrated},
        status=200 if result else 503,
    )
    response["Cache-Control"] = "no-store"
    return response
