import json

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import F
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from categories.models import BusinessCategory
from core.models import Business
from .forms import GuideForkForm, GuideForm
from .models import Guide, GuideRating, GuideVersion, Step, StepTip


def _unique_slug(title):
    base = slugify(title) or 'guide'
    slug = base
    counter = 2
    while Guide.objects.filter(slug=slug).exists():
        slug = f'{base}-{counter}'
        counter += 1
    return slug


def _json_body(request):
    try:
        return json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return None


def _guide_queryset():
    return Guide.objects.select_related('organization', 'category', 'forked_from', 'current_version')


def _steps_for_version(version):
    if not version:
        return Step.objects.none()
    return version.steps.prefetch_related('tips').order_by('position')


def guide_list(request):
    guides = _guide_queryset()
    organization_id = request.GET.get('organization')
    category_id = request.GET.get('category')
    if organization_id:
        guides = guides.filter(organization_id=organization_id)
    if category_id:
        guides = guides.filter(category_id=category_id)
    return render(request, 'guides/guide_list.html', {
        'guides': guides,
        'organizations': Business.objects.order_by('name'),
        'categories': BusinessCategory.objects.order_by('order', 'name'),
        'selected_organization': organization_id or '',
        'selected_category': category_id or '',
    })


@login_required
def guide_create(request):
    if request.method == 'POST':
        form = GuideForm(request.POST)
        if form.is_valid():
            guide = form.save(commit=False)
            guide.slug = _unique_slug(guide.title)
            guide.created_by = request.user
            guide.save()
            version = GuideVersion.objects.create(guide=guide, edited_by=request.user, edit_summary='Initial draft')
            guide.current_version = version
            guide.save(update_fields=['current_version'])
            return redirect('guides:edit', slug=guide.slug)
    else:
        form = GuideForm()
    return render(request, 'guides/guide_create.html', {'form': form})


def guide_detail(request, slug):
    guide = get_object_or_404(_guide_queryset(), slug=slug)
    steps = _steps_for_version(guide.current_version)
    user_rating = None
    if request.user.is_authenticated:
        user_rating = GuideRating.objects.filter(guide=guide, user=request.user).first()
    return render(request, 'guides/detail.html', {
        'guide': guide,
        'steps': steps,
        'user_rating': user_rating,
        'can_edit': request.user.is_authenticated,
    })


@login_required
def guide_edit(request, slug):
    guide = get_object_or_404(_guide_queryset(), slug=slug)
    if request.method == 'POST':
        steps_payload = json.loads(request.POST.get('steps_json', '[]'))
        deleted_ids = set(str(step_id) for step_id in json.loads(request.POST.get('deleted_step_ids', '[]')))
        with transaction.atomic():
            version = GuideVersion.objects.create(
                guide=guide,
                edited_by=request.user,
                status='published',
                edit_summary=request.POST.get('edit_summary', '').strip(),
            )
            tip_moves = []
            for item in steps_payload:
                old_id = item.get('id')
                step = Step.objects.create(
                    version=version,
                    instruction=(item.get('instruction') or '').strip(),
                    position=float(item.get('position')),
                )
                if old_id and str(old_id) not in deleted_ids:
                    tip_moves.append((old_id, step.id))
            for old_id, new_id in tip_moves:
                StepTip.objects.filter(step_id=old_id).update(step_id=new_id)
            guide.current_version = version
            guide.save(update_fields=['current_version'])
        return redirect('guides:detail', slug=guide.slug)
    return render(request, 'guides/edit.html', {'guide': guide, 'steps': _steps_for_version(guide.current_version)})


@login_required
def guide_fork(request, slug):
    source = get_object_or_404(_guide_queryset(), slug=slug)
    if request.method == 'POST':
        form = GuideForkForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                guide = Guide.objects.create(
                    title=source.title,
                    slug=_unique_slug(source.title),
                    organization=form.cleaned_data['organization'],
                    category=source.category,
                    summary=source.summary,
                    forked_from=source,
                    created_by=request.user,
                )
                version = GuideVersion.objects.create(guide=guide, edited_by=request.user, edit_summary='Forked guide')
                for step in _steps_for_version(source.current_version):
                    Step.objects.create(version=version, position=step.position, instruction=step.instruction)
                guide.current_version = version
                guide.save(update_fields=['current_version'])
            return redirect('guides:detail', slug=guide.slug)
    else:
        form = GuideForkForm(initial={'organization': source.organization_id})
    return render(request, 'guides/fork_select_org.html', {'form': form, 'guide': source})


@require_POST
def guide_rate(request, slug):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required'}, status=401)
    guide = get_object_or_404(Guide, slug=slug)
    data = _json_body(request)
    if data is None:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    try:
        score = int(data.get('score'))
    except (TypeError, ValueError):
        return JsonResponse({'error': 'Score must be an integer'}, status=400)
    if score < 1 or score > 5:
        return JsonResponse({'error': 'Score must be between 1 and 5'}, status=400)
    GuideRating.objects.update_or_create(guide=guide, user=request.user, defaults={'score': score})
    return JsonResponse({'score': score, 'average_score': float(guide.average_rating), 'rating_count': guide.ratings.count()})


def guide_history(request, slug):
    guide = get_object_or_404(_guide_queryset(), slug=slug)
    return render(request, 'guides/guide_history.html', {'guide': guide, 'versions': guide.versions.select_related('edited_by')})


def guide_version_detail(request, slug, version_id):
    guide = get_object_or_404(_guide_queryset(), slug=slug)
    version = get_object_or_404(guide.versions.select_related('edited_by'), id=version_id)
    return render(request, 'guides/guide_version_detail.html', {'guide': guide, 'version': version, 'steps': _steps_for_version(version)})


@require_POST
def tip_create(request, slug, step_id):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required'}, status=401)
    guide = get_object_or_404(Guide, slug=slug)
    step = get_object_or_404(Step, id=step_id, version=guide.current_version)
    data = _json_body(request)
    if data is None:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    body = (data.get('body') or '').strip()[:300]
    if not body:
        return JsonResponse({'error': 'Tip body is required'}, status=400)
    tip = StepTip.objects.create(step=step, body=body, submitted_by=request.user)
    return JsonResponse({'id': tip.id, 'body': tip.body, 'upvotes': 0})


@require_POST
def tip_vote(request, slug, tip_id):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required'}, status=401)
    guide = get_object_or_404(Guide, slug=slug)
    tip = get_object_or_404(StepTip, id=tip_id, step__version__guide=guide)
    StepTip.objects.filter(id=tip.id).update(upvotes=F('upvotes') + 1)
    tip.refresh_from_db(fields=['upvotes'])
    return JsonResponse({'upvotes': tip.upvotes})
