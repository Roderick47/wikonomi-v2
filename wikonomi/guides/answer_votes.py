from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.http import require_POST

from .models import Guide, GuideAnswer, GuideQuestion


@login_required
@require_POST
def answer_vote(request, slug, question_id, answer_id):
    guide = get_object_or_404(Guide, slug=slug)
    question = get_object_or_404(GuideQuestion, pk=question_id, guide=guide)
    answer = get_object_or_404(GuideAnswer, pk=answer_id, question=question)

    # Community voting should reflect other readers' preferences, not self-votes.
    if answer.author_id != request.user.id:
        if answer.upvoters.filter(pk=request.user.pk).exists():
            answer.upvoters.remove(request.user)
        else:
            answer.upvoters.add(request.user)

    return redirect(
        f"{reverse('guides:detail', args=[guide.slug])}#question-{question.id}"
    )
