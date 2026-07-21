import json

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import F, Prefetch, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.templatetags.static import static
from django.urls import reverse
from django.utils.text import slugify
from django.views.decorators.http import require_GET, require_POST

from categories.models import BusinessCategory
from core.models import Business, Notification
from .forms import GuideAnswerForm, GuideForkForm, GuideForm, GuideQuestionForm, StepTipForm
from .models import (
    Guide, GuideAnswer, GuideQuestion, GuideRating, GuideVersion, Step,
    StepPhoto, StepTip, StepTipPhoto, StepTipVote,
)



def _unique_model_slug(model, name, fallback='item'):
    max_length = model._meta.get_field('slug').max_length
    base = (slugify(name) or fallback)[:max_length].rstrip('-') or fallback
    slug = base
    counter = 2
    while model.objects.filter(slug=slug).exists():
        suffix = f'-{counter}'
        slug = f"{base[:max_length - len(suffix)].rstrip('-')}{suffix}"
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


def _normalise_instruction(value):
    return str(value or '').replace('\r\n', '\n').replace('\r', '\n')


def _create_steps_from_payload(version, steps_payload, request=None):
    for index, item in enumerate(steps_payload, start=1):
        title = (item.get('title') or '').strip()[:120]
        instruction = _normalise_instruction(item.get('instruction'))
        if not title and not instruction.strip():
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
    return _unique_model_slug(Guide, title, fallback='guide')


def _json_body(request):
    try:
        return json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return None


def _guide_queryset():
    return Guide.objects.select_related(
        'organization', 'category', 'forked_from', 'created_by',
        'current_version', 'current_version__edited_by',
    )


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
        'can_delete': bool(user and user.is_authenticated and (
            tip.submitted_by_id == user.id or user.is_staff or user.is_superuser
        )),
        'photos': [{'url': photo.image.url} for photo in tip.photos.all()],
    }


def _notify_guide_users(users, *, notification_type, message, target_url, exclude_user=None):
    seen = set()
    for user in users:
        if not user or user.pk in seen or (exclude_user and user.pk == exclude_user.pk):
            continue
        seen.add(user.pk)
        Notification.objects.create(
            user=user,
            notification_type=notification_type,
            message=message[:255],
            target_url=target_url,
        )


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
    source_business = None
    business_id = request.GET.get('business')
    if business_id and business_id.isdigit():
        source_business = Business.objects.filter(pk=business_id).first()
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
        initial = {'organization_name': source_business.name} if source_business else None
        form = GuideForm(initial=initial)
    context = _guide_form_context(form)
    context['source_business'] = source_business
    context['guide_draft_key'] = (
        f'wikonomi-guide-new-business-{source_business.pk}'
        if source_business else 'wikonomi-guide-new'
    )
    return render(request, 'guides/guide_create.html', context)


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
    questions = list(
        guide.questions.select_related('author', 'step').prefetch_related(
            Prefetch('answers', queryset=GuideAnswer.objects.select_related('author'))
        )
    )
    for question in questions:
        question.accepted = any(answer.is_accepted for answer in question.answers.all())

    has_edits = guide.versions.exclude(pk=guide.current_version_id).exists()
    share_image_url = request.build_absolute_uri(
        guide.photo.url if guide.photo else static('img/wikonomi-og-default.jpg')
    )
    canonical_url = request.build_absolute_uri(request.path)
    return render(request, 'guides/detail.html', {
        'guide': guide,
        'steps': steps,
        'user_rating': user_rating,
        'can_edit': request.user.is_authenticated,
        'businesses': Business.objects.order_by('name'),
        'questions': questions,
        'answered_question_count': sum(1 for question in questions if question.accepted),
        'unanswered_question_count': sum(1 for question in questions if not question.accepted),
        'can_delete_guide': guide.can_delete(request.user),
        'has_edits': has_edits,
        'latest_editor': guide.current_version.edited_by if has_edits and guide.current_version else None,
        'share_image_url': share_image_url,
        'canonical_url': canonical_url,
    })


@login_required
def guide_edit(request, slug):
    guide = get_object_or_404(_guide_queryset(), slug=slug)
    source_question = None
    source_question_id = request.GET.get('from_question')
    if source_question_id:
        source_question = GuideQuestion.objects.filter(pk=source_question_id, guide=guide).first()
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
            return render(request, 'guides/edit.html', _guide_form_context(
                form,
                guide=guide,
                steps=_steps_for_version(guide.current_version),
                source_question=source_question,
            ))
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
                instruction = _normalise_instruction(item.get('instruction'))
                if not title and not instruction.strip():
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
                GuideQuestion.objects.filter(step_id=old_id).update(step_id=new_id)
            GuideQuestion.objects.filter(step_id__in=deleted_ids).update(step=None)
            guide.current_version = version
            guide.save(update_fields=['current_version'])
        return redirect('guides:detail', slug=guide.slug)
    return render(request, 'guides/edit.html', _guide_form_context(
        form,
        guide=guide,
        steps=_steps_for_version(guide.current_version),
        source_question=source_question,
    ))


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


@require_POST
def tip_delete(request, slug, tip_id):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required'}, status=401)
    guide = get_object_or_404(Guide, slug=slug)
    tip = get_object_or_404(StepTip, id=tip_id, step__version__guide=guide)
    if tip.submitted_by_id != request.user.id and not request.user.is_staff and not request.user.is_superuser:
        return JsonResponse({'error': 'Only the tip author can delete this tip'}, status=403)
    tip.delete()
    return JsonResponse({'ok': True})


@require_POST
def question_create(request, slug):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required'}, status=401)
    guide = get_object_or_404(_guide_queryset(), slug=slug)
    data = _json_body(request)
    if data is None:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    form = GuideQuestionForm({'body': data.get('body', '')})
    if not form.is_valid():
        return JsonResponse({'errors': form.errors.get_json_data()}, status=400)
    step = None
    step_id = data.get('step_id')
    if step_id not in (None, '', 'general'):
        step = get_object_or_404(Step, pk=step_id, version=guide.current_version)
    question = form.save(commit=False)
    question.guide = guide
    question.step = step
    question.author = request.user
    question.save()
    target_url = f"{reverse('guides:detail', args=[guide.slug])}#question-{question.id}"
    last_editor = guide.current_version.edited_by if guide.current_version else None
    _notify_guide_users(
        [guide.created_by, last_editor],
        notification_type=Notification.TYPE_GUIDE_QUESTION,
        message=f'{request.user.username} asked a question about {guide.title}.',
        target_url=target_url,
        exclude_user=request.user,
    )
    return JsonResponse({'ok': True, 'question_id': question.id, 'target_url': target_url})


@login_required
@require_POST
def answer_create(request, slug, question_id):
    guide = get_object_or_404(Guide, slug=slug)
    question = get_object_or_404(GuideQuestion, pk=question_id, guide=guide)
    form = GuideAnswerForm(request.POST)
    if not form.is_valid():
        return redirect(f"{reverse('guides:detail', args=[slug])}#question-{question.id}")
    answer = form.save(commit=False)
    answer.question = question
    answer.author = request.user
    answer.save()
    _notify_guide_users(
        [question.author],
        notification_type=Notification.TYPE_GUIDE_ANSWER,
        message=f'{request.user.username} answered your question on {guide.title}.',
        target_url=f"{reverse('guides:detail', args=[guide.slug])}#question-{question.id}",
        exclude_user=request.user,
    )
    return redirect(f"{reverse('guides:detail', args=[slug])}#question-{question.id}")


@login_required
@require_POST
def answer_accept(request, slug, question_id, answer_id):
    guide = get_object_or_404(Guide, slug=slug)
    question = get_object_or_404(GuideQuestion, pk=question_id, guide=guide)
    if question.author_id != request.user.id:
        return JsonResponse({'error': 'Only the person who asked can accept an answer'}, status=403)
    with transaction.atomic():
        answer = get_object_or_404(GuideAnswer.objects.select_for_update(), pk=answer_id, question=question)
        GuideAnswer.objects.filter(question=question, is_accepted=True).exclude(pk=answer.pk).update(is_accepted=False)
        answer.is_accepted = True
        answer.save(update_fields=['is_accepted'])
    _notify_guide_users(
        [answer.author],
        notification_type=Notification.TYPE_GUIDE_ANSWER,
        message=f'Your answer on {guide.title} was accepted.',
        target_url=f"{reverse('guides:detail', args=[guide.slug])}#question-{question.id}",
        exclude_user=request.user,
    )
    return redirect(f"{reverse('guides:detail', args=[slug])}#question-{question.id}")


@login_required
@require_POST
def guide_mark_delete(request, slug):
    guide = get_object_or_404(Guide, slug=slug)
    if guide.can_delete(request.user):
        return JsonResponse({'error': 'As the original author, you can delete this guide directly.'}, status=400)
    if guide.marked_for_deletion:
        return JsonResponse({'error': 'This guide is already marked for deletion.'}, status=400)
    reason = request.POST.get('reason', '').strip()[:1000]
    guide.mark_for_deletion(request.user, reason)
    _notify_guide_users(
        [guide.created_by],
        notification_type=Notification.TYPE_GUIDE_DELETION,
        message=f'{request.user.username} marked your guide {guide.title} for deletion.',
        target_url=reverse('guides:detail', args=[guide.slug]),
        exclude_user=request.user,
    )
    return JsonResponse({'ok': True, 'message': 'Guide marked for deletion. Another user can confirm it.'})


@login_required
@require_POST
def guide_veto_delete(request, slug):
    guide = get_object_or_404(Guide, slug=slug)
    if not guide.can_delete(request.user):
        return JsonResponse({'error': 'Only the original author can veto this request.'}, status=403)
    guide.marked_for_deletion = False
    guide.marked_for_deletion_by = None
    guide.marked_for_deletion_at = None
    guide.deletion_reason = ''
    guide.deletion_votes.clear()
    guide.save(update_fields=[
        'marked_for_deletion', 'marked_for_deletion_by',
        'marked_for_deletion_at', 'deletion_reason',
    ])
    return redirect('guides:detail', slug=slug)


@login_required
@require_POST
def guide_confirm_delete(request, slug):
    with transaction.atomic():
        guide = get_object_or_404(Guide.objects.select_for_update(), slug=slug)
        if not guide.marked_for_deletion:
            return JsonResponse({'error': 'This guide is not marked for deletion.'}, status=400)
        if guide.marked_for_deletion_by_id == request.user.id:
            return JsonResponse({'error': 'Another user must confirm your request.'}, status=403)
        if guide.created_by_id == request.user.id:
            return JsonResponse({'error': 'Use the author delete action instead.'}, status=400)
        guide.deletion_votes.add(request.user)
        title = guide.title
        guide.delete()
    return JsonResponse({'ok': True, 'message': f'{title} was deleted.', 'redirect_url': reverse('guides:list')})


@login_required
@require_POST
def guide_delete(request, slug):
    guide = get_object_or_404(Guide, slug=slug)
    if not guide.can_delete(request.user):
        return JsonResponse({'error': 'Only the original author can delete this guide directly.'}, status=403)
    guide.delete()
    return JsonResponse({'ok': True, 'redirect_url': reverse('guides:list')})
