from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Guide, GuideAnswer, GuideQuestion


class GuideAnswerVoteTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.asker = user_model.objects.create_user(username='asker', password='pass')
        self.answerer = user_model.objects.create_user(username='answerer', password='pass')
        self.voter = user_model.objects.create_user(username='voter', password='pass')
        self.guide = Guide.objects.create(
            title='Community guide',
            slug='community-guide',
            created_by=self.asker,
        )
        self.question = GuideQuestion.objects.create(
            guide=self.guide,
            author=self.asker,
            body='What should I do?',
        )
        self.answer = GuideAnswer.objects.create(
            question=self.question,
            author=self.answerer,
            body='Use the community answer.',
        )
        self.vote_url = reverse(
            'guides:answer_vote',
            args=[self.guide.slug, self.question.id, self.answer.id],
        )

    def test_user_can_toggle_answer_upvote(self):
        self.client.force_login(self.voter)

        response = self.client.post(self.vote_url)
        self.assertRedirects(
            response,
            f"{reverse('guides:detail', args=[self.guide.slug])}#question-{self.question.id}",
        )
        self.assertTrue(self.answer.upvoters.filter(pk=self.voter.pk).exists())

        self.client.post(self.vote_url)
        self.assertFalse(self.answer.upvoters.filter(pk=self.voter.pk).exists())

    def test_answer_author_cannot_upvote_own_answer(self):
        self.client.force_login(self.answerer)
        self.client.post(self.vote_url)

        self.assertFalse(self.answer.upvoters.filter(pk=self.answerer.pk).exists())

    def test_detail_shows_answer_upvote_count_and_control(self):
        self.answer.upvoters.add(self.voter)
        self.client.force_login(self.asker)

        response = self.client.get(reverse('guides:detail', args=[self.guide.slug]))

        self.assertContains(response, '1 upvote')
        self.assertContains(response, self.vote_url)
        self.assertContains(response, 'aria-label="Upvote this answer"')
