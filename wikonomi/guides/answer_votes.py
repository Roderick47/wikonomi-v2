from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.http import require_POST

from .models import Guide, GuideAnswer, GuideQuestion


@login_required
@require_POST
def answer_vote(request, slug, question_id, answer_id):
    guide = get_object_or_404(Guide, slug=slug)
    question = get_object_or_404(GuideQuestion, pk=question_id, guide=guide)

    with transaction.atomic():
        answer = get_object_or_404(
            GuideAnswer.objects.select_for_update(),
            pk=answer_id,
            question=question,
        )

        # Community ranking should reflect other readers' preferences, not self-votes.
        if answer.author_id == request.user.id:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'error': 'You cannot upvote your own answer.'}, status=403)
            return redirect(f"{reverse('guides:detail', args=[guide.slug])}#question-{question.id}")

        existing_vote = answer.upvoters.filter(pk=request.user.pk).exists()
        if existing_vote:
            answer.upvoters.remove(request.user)
            answer.upvote_count = max(0, answer.upvote_count - 1)
            active = False
        else:
            answer.upvoters.add(request.user)
            answer.upvote_count += 1
            active = True
        answer.save(update_fields=['upvote_count'])

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'answer_id': answer.id,
            'upvote_count': answer.upvote_count,
            'upvoted': active,
            'is_accepted': answer.is_accepted,
        })

    return redirect(
        f"{reverse('guides:detail', args=[guide.slug])}#question-{question.id}"
    )
