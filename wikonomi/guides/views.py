import json

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import F, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.text import slugify
from django.views.decorators.http import require_GET, require_POST

from categories.models import BusinessCategory
from core.models import Business
from .forms import GuideForkForm, GuideForm, StepTipForm
from .models import Guide, GuideRating, GuideVersion, Step, StepPhoto, StepTip, StepTipPhoto, StepTipVote



def _unique_model_slug(model, name):
    base = slugify(name) or 'item'
    slug = base
    counter = 2
    while model.objects.filter(slug=slug).exists():
        slug = f'{base}-{counter}'
        counter += 1
    return slug


def _business_from_name(name, user=None):
    name = (name or '').strip()
    if not name:
        return None
    business = Business.objects.filter(name__iexact=name).first()
    if business:
        return business
    return Business.objects.create(
        name=name,
        slug=_unique_model_slug(Business, name),
    )


def _category_from_name(name):
    name = (name or '').strip()
    if not name:
        return None
    category = BusinessCategory.objects.filter(name__iexact=name).first()
    if category:
        return category
    return BusinessCategory.objects.create(
        name=name,
        slug=_unique_model_slug(BusinessCategory, name),
    )



def _steps_payload_from_post(request):
    try:
        return json.loads(request.POST.get('steps_json', '[]'))
    except json.JSONDecodeError:
        return []


def _photo_files_for_step(request, index):
    return request.FILES.getlist(f'step_photos_{index}')


def _create_steps_from_payload(version, steps_payload, request=None):
    for index, item in enumerate(steps_payload, start=1):
        title = (item.get('title') or '').strip()[:120]
        instruction = (item.get('instruction') or '').strip()
        if not title and not instruction:
            continue
        step = Step.objects.create(
            version=version,
            title=title,
            instruction=instruction,
            position=float(item.get('position') or index),
        )
        if request is not None:
            for image in _photo_files_for_step(request, index - 1):
                StepPhoto.objects.create(step=step, image=image, uploaded_by=request.user)

def _guide_form_context(form, **extra):
    context = {
        'form': form,
        'businesses': Business.objects.order_by('name'),
        'categories': BusinessCategory.objects.order_by('order', 'name'),
    }
    context.update(extra)
    return context

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
    return version.steps.prefetch_related('photos', 'tips__photos').order_by('position')


def _ranked_tips(step):
    return StepTip.objects.filter(step=step).select_related('submitted_by').prefetch_related('photos').order_by(
        (F('upvotes') - F('downvotes')).desc(), '-created_at'
    )


def _tip_payload(tip, user=None):
    user_vote = 0
    if user and user.is_authenticated:
        user_vote = StepTipVote.objects.filter(tip=tip, user=user).values_list('value', flat=True).first() or 0
    return {
        'id': tip.id,
        'body': tip.body,
        'username': tip.submitted_by.username if tip.submitted_by else 'Deleted user',
        'score': tip.score,
        'user_vote': user_vote,
        'can_edit': bool(user and user.is_authenticated and tip.submitted_by_id == user.id),
        'photos': [{'url': photo.image.url} for photo in tip.photos.all()],
    }


def guide_list(request):
    guides = _guide_queryset()
    query = request.GET.get('q', '').strip()
    organization_id = request.GET.get('organization')
    category_id = request.GET.get('category')
    if organization_id:
        guides = guides.filter(organization_id=organization_id)
    if category_id:
        guides = guides.filter(category_id=category_id)
    if query:
        guides = guides.filter(
            Q(title__icontains=query)
            | Q(summary__icontains=query)
            | Q(organization__name__icontains=query)
            | Q(category__name__icontains=query)
        ).distinct()
    return render(request, 'guides/guide_list.html', {
        'guides': guides,
        'organizations': Business.objects.order_by('name'),
        'categories': BusinessCategory.objects.order_by('order', 'name'),
        'selected_organization': organization_id or '',
        'selected_category': category_id or '',
        'search_query': query,
    })


@login_required
def guide_create(request):
    if request.method == 'POST':
        form = GuideForm(request.POST, request.FILES)
        if form.is_valid():
            guide = form.save(commit=False)
            guide.organization = _business_from_name(form.cleaned_data.get('organization_name'), request.user)
            guide.category = _category_from_name(form.cleaned_data.get('category_name'))
            guide.slug = _unique_slug(guide.title)
            guide.created_by = request.user
            guide.save()
            version = GuideVersion.objects.create(guide=guide, edited_by=request.user, edit_summary='Initial draft')
            _create_steps_from_payload(version, _steps_payload_from_post(request), request)
            guide.current_version = version
            guide.save(update_fields=['current_version'])
            return redirect('guides:detail', slug=guide.slug)
    else:
        form = GuideForm()
    return render(request, 'guides/guide_create.html', _guide_form_context(form))


def guide_detail(request, slug):
    guide = get_object_or_404(_guide_queryset(), slug=slug)
    steps = list(_steps_for_version(guide.current_version))
    for step in steps:
        ranked = list(_ranked_tips(step)[:5])
        step.top_tips = ranked
        step.tip_count = StepTip.objects.filter(step=step).count()
        for tip in ranked:
            tip.viewer_vote = 0
            if request.user.is_authenticated:
                tip.viewer_vote = StepTipVote.objects.filter(tip=tip, user=request.user).values_list('value', flat=True).first() or 0
    user_rating = None
    if request.user.is_authenticated:
        user_rating = GuideRating.objects.filter(guide=guide, user=request.user).first()
    return render(request, 'guides/detail.html', {
        'guide': guide,
        'steps': steps,
        'user_rating': user_rating,
        'can_edit': request.user.is_authenticated,
        'businesses': Business.objects.order_by('name'),
    })


@login_required
def guide_edit(request, slug):
    guide = get_object_or_404(_guide_queryset(), slug=slug)
    post_data = None
    if request.method == 'POST':
        post_data = request.POST.copy()
        post_data.setdefault('title', guide.title)
        post_data.setdefault('summary', guide.summary)
        post_data.setdefault('organization_name', guide.organization.name if guide.organization else '')
        post_data.setdefault('category_name', guide.category.name if guide.category else '')
    form = GuideForm(post_data, request.FILES or None, instance=guide)
    if request.method == 'POST':
        if not form.is_valid():
            return render(request, 'guides/edit.html', _guide_form_context(form, guide=guide, steps=_steps_for_version(guide.current_version)))
        steps_payload = _steps_payload_from_post(request)
        deleted_ids = set(str(step_id) for step_id in json.loads(request.POST.get('deleted_step_ids', '[]')))
        with transaction.atomic():
            guide = form.save(commit=False)
            guide.organization = _business_from_name(form.cleaned_data.get('organization_name'), request.user)
            guide.category = _category_from_name(form.cleaned_data.get('category_name'))
            guide.save(update_fields=['title', 'photo', 'organization', 'category', 'summary'])
            version = GuideVersion.objects.create(
                guide=guide,
                edited_by=request.user,
                status='published',
                edit_summary=request.POST.get('edit_summary', '').strip(),
            )
            tip_moves = []
            for index, item in enumerate(steps_payload):
                old_id = item.get('id')
                title = (item.get('title') or '').strip()[:120]
                instruction = (item.get('instruction') or '').strip()
                if not title and not instruction:
                    continue
                step = Step.objects.create(
                    version=version,
                    title=title,
                    instruction=instruction,
                    position=float(item.get('position')),
                )
                if old_id and str(old_id) not in deleted_ids:
                    tip_moves.append((old_id, step.id))
                    StepPhoto.objects.filter(step_id=old_id).update(step_id=step.id)
                for image in _photo_files_for_step(request, index):
                    StepPhoto.objects.create(step=step, image=image, uploaded_by=request.user)
            for old_id, new_id in tip_moves:
                StepTip.objects.filter(step_id=old_id).update(step_id=new_id)
            guide.current_version = version
            guide.save(update_fields=['current_version'])
        return redirect('guides:detail', slug=guide.slug)
    return render(request, 'guides/edit.html', _guide_form_context(form, guide=guide, steps=_steps_for_version(guide.current_version)))


@login_required
def guide_fork(request, slug):
    source = get_object_or_404(_guide_queryset(), slug=slug)
    if request.method == 'POST':
        form = GuideForkForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                organization = _business_from_name(form.cleaned_data['organization_name'], request.user)
                guide = Guide.objects.create(
                    title=source.title,
                    slug=_unique_slug(source.title),
                    photo=source.photo,
                    organization=organization,
                    category=source.category,
                    summary=source.summary,
                    forked_from=source,
                    created_by=request.user,
                )
                version = GuideVersion.objects.create(guide=guide, edited_by=request.user, edit_summary='Forked guide')
                for step in _steps_for_version(source.current_version):
                    new_step = Step.objects.create(version=version, position=step.position, title=step.title, instruction=step.instruction)
                    for photo in step.photos.all():
                        StepPhoto.objects.create(step=new_step, image=photo.image, caption=photo.caption, uploaded_by=request.user)
                guide.current_version = version
                guide.save(update_fields=['current_version'])
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'ok': True, 'url': guide.get_absolute_url() if hasattr(guide, 'get_absolute_url') else f'/guides/{guide.slug}/'})
            return redirect('guides:detail', slug=guide.slug)
    else:
        form = GuideForkForm(initial={'organization_name': source.organization.name if source.organization else ''})
    if request.method == 'POST' and request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'errors': form.errors.get_json_data()}, status=400)
    return render(request, 'guides/fork_select_org.html', {'form': form, 'guide': source, 'businesses': Business.objects.order_by('name')})


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
    if request.content_type and request.content_type.startswith('multipart/form-data'):
        post_data = request.POST.copy()
        uploaded_files = request.FILES.getlist('photos')
        if uploaded_files:
            post_data['photo'] = uploaded_files[0]
        form = StepTipForm(post_data, {'photo': uploaded_files[0]} if uploaded_files else None)
    else:
        data = _json_body(request)
        if data is None:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        form = StepTipForm({'body': data.get('body', '')})
        uploaded_files = []
    if not form.is_valid():
        return JsonResponse({'errors': form.errors.get_json_data()}, status=400)
    tip = form.save(commit=False)
    tip.step = step
    tip.submitted_by = request.user
    tip.save()
    photos = []
    for image in uploaded_files:
        photo = StepTipPhoto.objects.create(tip=tip, image=image, uploaded_by=request.user)
        photos.append({'url': photo.image.url})
    payload = _tip_payload(tip, request.user)
    payload['image_url'] = photos[0]['url'] if photos else ''
    return JsonResponse(payload)


@require_GET
def tip_list(request, slug, step_id):
    guide = get_object_or_404(Guide, slug=slug)
    step = get_object_or_404(Step, id=step_id, version=guide.current_version)
    try:
        offset = max(0, int(request.GET.get('offset', 5)))
    except (TypeError, ValueError):
        offset = 5
    tips = list(_ranked_tips(step)[offset:offset + 50])
    total = StepTip.objects.filter(step=step).count()
    return JsonResponse({'tips': [_tip_payload(tip, request.user) for tip in tips], 'total': total})


@require_POST
def tip_edit(request, slug, tip_id):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required'}, status=401)
    guide = get_object_or_404(Guide, slug=slug)
    tip = get_object_or_404(StepTip, id=tip_id, step__version__guide=guide)
    if tip.submitted_by_id != request.user.id:
        return JsonResponse({'error': 'You can only edit your own tips'}, status=403)
    data = _json_body(request)
    if data is None:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    form = StepTipForm({'body': data.get('body', '')})
    if not form.is_valid():
        return JsonResponse({'errors': form.errors.get_json_data()}, status=400)
    tip.body = form.cleaned_data['body']
    tip.save(update_fields=['body'])
    return JsonResponse(_tip_payload(tip, request.user))


@require_POST
def tip_vote(request, slug, tip_id):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required'}, status=401)
    guide = get_object_or_404(Guide, slug=slug)
    tip = get_object_or_404(StepTip, id=tip_id, step__version__guide=guide)
    data = _json_body(request)
    try:
        value = int((data or {}).get('value'))
    except (TypeError, ValueError):
        return JsonResponse({'error': 'Vote must be 1 or -1'}, status=400)
    if value not in (-1, 1):
        return JsonResponse({'error': 'Vote must be 1 or -1'}, status=400)

    with transaction.atomic():
        tip = StepTip.objects.select_for_update().get(pk=tip.pk)
        existing = StepTipVote.objects.filter(tip=tip, user=request.user).first()
        if existing and existing.value == value:
            if value == 1:
                tip.upvotes = max(0, tip.upvotes - 1)
            else:
                tip.downvotes = max(0, tip.downvotes - 1)
            existing.delete()
            active_vote = 0
        elif existing:
            if existing.value == 1:
                tip.upvotes = max(0, tip.upvotes - 1)
                tip.downvotes += 1
            else:
                tip.downvotes = max(0, tip.downvotes - 1)
                tip.upvotes += 1
            existing.value = value
            existing.save(update_fields=['value', 'updated_at'])
            active_vote = value
        else:
            StepTipVote.objects.create(tip=tip, user=request.user, value=value)
            if value == 1:
                tip.upvotes += 1
            else:
                tip.downvotes += 1
            active_vote = value
        tip.save(update_fields=['upvotes', 'downvotes'])
    return JsonResponse({'score': tip.score, 'user_vote': active_vote})
