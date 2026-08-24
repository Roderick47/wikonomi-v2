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
        self.answer.refresh_from_db()
        self.assertTrue(self.answer.upvoters.filter(pk=self.voter.pk).exists())
        self.assertEqual(self.answer.upvote_count, 1)

        self.client.post(self.vote_url)
        self.answer.refresh_from_db()
        self.assertFalse(self.answer.upvoters.filter(pk=self.voter.pk).exists())
        self.assertEqual(self.answer.upvote_count, 0)

    def test_answer_author_cannot_upvote_own_answer(self):
        self.client.force_login(self.answerer)
        self.client.post(self.vote_url)

        self.answer.refresh_from_db()
        self.assertFalse(self.answer.upvoters.filter(pk=self.answerer.pk).exists())
        self.assertEqual(self.answer.upvote_count, 0)

    def test_ajax_vote_returns_new_rank_state_without_page_reload(self):
        self.client.force_login(self.voter)

        response = self.client.post(
            self.vote_url,
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            'answer_id': self.answer.id,
            'upvote_count': 1,
            'upvoted': True,
            'is_accepted': False,
        })

    def test_answers_rank_by_upvotes_and_drop_when_vote_removed(self):
        other_author = get_user_model().objects.create_user(username='other-answerer', password='pass')
        other_answer = GuideAnswer.objects.create(
            question=self.question,
            author=other_author,
            body='A second answer.',
        )
        self.client.force_login(self.voter)

        self.client.post(self.vote_url)
        ranked = list(self.question.answers.values_list('id', flat=True))
        self.assertEqual(ranked, [self.answer.id, other_answer.id])

        other_voter = get_user_model().objects.create_user(username='other-voter', password='pass')
        self.client.force_login(other_voter)
        other_vote_url = reverse(
            'guides:answer_vote',
            args=[self.guide.slug, self.question.id, other_answer.id],
        )
        self.client.post(other_vote_url)
        third_voter = get_user_model().objects.create_user(username='third-voter', password='pass')
        self.client.force_login(third_voter)
        self.client.post(other_vote_url)

        ranked = list(self.question.answers.values_list('id', flat=True))
        self.assertEqual(ranked, [other_answer.id, self.answer.id])

        self.client.post(other_vote_url)
        ranked = list(self.question.answers.values_list('id', flat=True))
        self.assertEqual(ranked, [self.answer.id, other_answer.id])

    def test_accepted_answer_stays_above_higher_voted_answers(self):
        accepted_author = get_user_model().objects.create_user(username='accepted-author', password='pass')
        accepted = GuideAnswer.objects.create(
            question=self.question,
            author=accepted_author,
            body='Accepted answer.',
            is_accepted=True,
            upvote_count=0,
        )
        self.answer.upvote_count = 5
        self.answer.save(update_fields=['upvote_count'])

        ranked = list(self.question.answers.values_list('id', flat=True))
        self.assertEqual(ranked[0], accepted.id)

    def test_detail_shows_answer_upvote_count_and_control(self):
        self.answer.upvoters.add(self.voter)
        self.answer.upvote_count = 1
        self.answer.save(update_fields=['upvote_count'])
        self.client.force_login(self.asker)

        response = self.client.get(reverse('guides:detail', args=[self.guide.slug]))

        self.assertContains(response, '1 upvote')
        self.assertContains(response, self.vote_url)
        self.assertContains(response, 'aria-label="Upvote this answer"')
