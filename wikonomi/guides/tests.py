import json

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from core.models import Business
from .models import Guide, GuideAnswer, GuideQuestion, GuideRating, GuideVersion, Step, StepPhoto, StepTip, StepTipPhoto, StepTipVote
from .templatetags.guide_markup import guide_markdown


def tiny_png(name='tiny.png'):
    return SimpleUploadedFile(
        name,
        b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc```\x00\x00\x00\x04\x00\x01\xf6\x178U\x00\x00\x00\x00IEND\xaeB`\x82',
        content_type='image/png',
    )


class GuideBackendTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='guideuser', password='pass')
        self.business = Business.objects.create(name='BSP Boroko', slug='bsp-boroko')
        self.guide = Guide.objects.create(
            title='Open a business account',
            slug='open-business-account',
            organization=self.business,
            created_by=self.user,
        )
        self.version = GuideVersion.objects.create(guide=self.guide, edited_by=self.user)
        self.step = Step.objects.create(version=self.version, position=2.0, title='Prepare documents', instruction='Bring ID')
        self.guide.current_version = self.version
        self.guide.save(update_fields=['current_version'])

    def test_detail_links_business_and_shows_unlinked_creator_before_edits(self):
        response = self.client.get(reverse('guides:detail', args=[self.guide.slug]))

        self.assertContains(response, f'href="{reverse("business_detail", args=[self.business.pk])}"')
        self.assertContains(response, 'Created by @guideuser')
        self.assertFalse(response.context['has_edits'])
        self.assertNotContains(response, reverse('guides:history', args=[self.guide.slug]))

    def test_detail_links_creator_and_latest_editor_to_history_after_edit(self):
        editor = get_user_model().objects.create_user(username='helpful-editor', password='pass')
        edited_version = GuideVersion.objects.create(
            guide=self.guide,
            edited_by=editor,
            edit_summary='Clarified required documents',
        )
        self.guide.current_version = edited_version
        self.guide.save(update_fields=['current_version'])

        response = self.client.get(reverse('guides:detail', args=[self.guide.slug]))
        history_url = reverse('guides:history', args=[self.guide.slug])

        self.assertTrue(response.context['has_edits'])
        self.assertEqual(response.context['latest_editor'], editor)
        self.assertContains(response, 'Created by @guideuser')
        self.assertContains(response, 'Edited by @helpful-editor')
        self.assertContains(response, f'href="{history_url}"', count=2)

    def test_detail_social_image_uses_guide_photo_or_branded_fallback(self):
        response = self.client.get(reverse('guides:detail', args=[self.guide.slug]))
        self.assertEqual(
            response.context['share_image_url'],
            'http://testserver/static/img/wikonomi-guide-og-default.jpg',
        )
        self.assertContains(
            response,
            '<meta property="og:image" content="http://testserver/static/img/wikonomi-guide-og-default.jpg">',
            html=True,
        )

        self.guide.photo = tiny_png('guide-share.png')
        self.guide.save(update_fields=['photo'])
        response = self.client.get(reverse('guides:detail', args=[self.guide.slug]))

        self.assertEqual(
            response.context['share_image_url'],
            f'http://testserver{self.guide.photo.url}',
        )
        self.assertContains(
            response,
            f'<meta property="og:image" content="http://testserver{self.guide.photo.url}">',
            html=True,
        )

    def test_guide_rate_requires_auth_json_status(self):
        response = self.client.post(
            reverse('guides:rate', args=[self.guide.slug]),
            data=json.dumps({'score': 5}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()['error'], 'Authentication required')

    def test_guide_rate_updates_rating_and_average(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('guides:rate', args=[self.guide.slug]),
            data=json.dumps({'score': 4}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['score'], 4)
        self.assertEqual(response.json()['average_score'], 4.0)
        self.assertEqual(GuideRating.objects.get(guide=self.guide, user=self.user).score, 4)

    def test_edit_creates_new_version_and_reparents_surviving_tips(self):
        tip = StepTip.objects.create(step=self.step, body='Photocopy everything', submitted_by=self.user)
        self.client.force_login(self.user)
        response = self.client.post(reverse('guides:edit', args=[self.guide.slug]), {
            'steps_json': json.dumps([
                {'id': str(self.step.id), 'title': 'Prepare documents', 'instruction': 'Bring ID and IPA certificate', 'position': 2.5},
                {'id': None, 'title': 'Submit application', 'instruction': 'Fill in the form', 'position': 3.5},
            ]),
            'deleted_step_ids': json.dumps([]),
            'edit_summary': 'Add form step',
        })
        self.assertRedirects(response, reverse('guides:detail', args=[self.guide.slug]))
        self.guide.refresh_from_db()
        self.assertNotEqual(self.guide.current_version_id, self.version.id)
        self.assertEqual(list(self.guide.current_version.steps.values_list('position', flat=True)), [2.5, 3.5])
        self.assertEqual(list(self.guide.current_version.steps.values_list('title', flat=True)), ['Prepare documents', 'Submit application'])
        tip.refresh_from_db()
        self.assertEqual(tip.step.version, self.guide.current_version)

    def test_fork_copies_steps_without_tips(self):
        StepTip.objects.create(step=self.step, body='Local tip', submitted_by=self.user)
        new_business = Business.objects.create(name='BSP Waigani', slug='bsp-waigani')
        self.client.force_login(self.user)
        response = self.client.post(reverse('guides:fork', args=[self.guide.slug]), {'organization_name': new_business.name})
        fork = Guide.objects.get(forked_from=self.guide)
        self.assertRedirects(response, reverse('guides:detail', args=[fork.slug]))
        self.assertEqual(fork.organization, new_business)
        self.assertEqual(fork.current_version.steps.count(), 1)
        self.assertEqual(fork.current_version.steps.first().title, self.step.title)
        self.assertEqual(fork.current_version.steps.first().instruction, self.step.instruction)
        self.assertEqual(StepTip.objects.filter(step__version=fork.current_version).count(), 0)

    def test_fork_creates_new_business_from_typed_name(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('guides:fork', args=[self.guide.slug]),
            {'organization_name': 'New Government Office'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 200)
        fork = Guide.objects.get(forked_from=self.guide)
        self.assertEqual(fork.organization.name, 'New Government Office')
        self.assertTrue(response.json()['url'].endswith(f'/{fork.slug}/'))

    def test_tip_votes_toggle_and_switch_direction(self):
        tip = StepTip.objects.create(step=self.step, body='Bring copies', submitted_by=self.user)
        voter = get_user_model().objects.create_user(username='voter', password='pass')
        self.client.force_login(voter)
        url = reverse('guides:tip_vote', args=[self.guide.slug, tip.id])

        response = self.client.post(url, json.dumps({'value': 1}), content_type='application/json')
        self.assertEqual(response.json(), {'score': 1, 'user_vote': 1})
        response = self.client.post(url, json.dumps({'value': -1}), content_type='application/json')
        self.assertEqual(response.json(), {'score': -1, 'user_vote': -1})
        response = self.client.post(url, json.dumps({'value': -1}), content_type='application/json')
        self.assertEqual(response.json(), {'score': 0, 'user_vote': 0})
        self.assertFalse(StepTipVote.objects.filter(tip=tip, user=voter).exists())

    def test_only_tip_author_can_edit_tip(self):
        tip = StepTip.objects.create(step=self.step, body='Old advice', submitted_by=self.user)
        self.client.force_login(self.user)
        url = reverse('guides:tip_edit', args=[self.guide.slug, tip.id])
        response = self.client.post(url, json.dumps({'body': 'Updated advice'}), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        tip.refresh_from_db()
        self.assertEqual(tip.body, 'Updated advice')

        other = get_user_model().objects.create_user(username='other', password='pass')
        self.client.force_login(other)
        response = self.client.post(url, json.dumps({'body': 'Hijacked'}), content_type='application/json')
        self.assertEqual(response.status_code, 403)

    def test_detail_shows_five_tips_and_loads_rest_ranked(self):
        for number in range(7):
            StepTip.objects.create(step=self.step, body=f'Tip {number}', submitted_by=self.user, upvotes=number)
        response = self.client.get(reverse('guides:detail', args=[self.guide.slug]))
        self.assertContains(response, 'data-tip-id=', count=5)
        self.assertContains(response, 'Show 2 more tips')

        response = self.client.get(reverse('guides:tip_list', args=[self.guide.slug, self.step.id]), {'offset': 5})
        self.assertEqual(response.status_code, 200)
        self.assertEqual([tip['body'] for tip in response.json()['tips']], ['Tip 1', 'Tip 0'])

    def test_create_accepts_inline_steps_with_titles(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('guides:create'), {
            'title': 'Get a passport',
            'organization_name': 'ICA PNG',
            'category_name': 'Government services',
            'summary': 'Passport application basics',
            'steps_json': json.dumps([
                {'title': 'Collect forms', 'instruction': 'Download and print the application.', 'position': 1},
                {'title': '', 'instruction': 'Submit the application in person.', 'position': 2},
            ]),
            'deleted_step_ids': json.dumps([]),
        })
        guide = Guide.objects.get(title='Get a passport')
        self.assertRedirects(response, reverse('guides:detail', args=[guide.slug]))
        self.assertEqual(guide.current_version.steps.count(), 2)
        self.assertEqual(list(guide.current_version.steps.values_list('title', flat=True)), ['Collect forms', ''])
        self.assertEqual(guide.organization.name, 'ICA PNG')
        self.assertEqual(guide.category.name, 'Government services')

    def test_create_saves_main_photo(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('guides:create'), {
            'title': 'Guide with a cover',
            'summary': 'A searchable guide summary',
            'steps_json': '[]',
            'photo': tiny_png('cover.png'),
        })
        guide = Guide.objects.get(title='Guide with a cover')
        self.assertRedirects(response, reverse('guides:detail', args=[guide.slug]))
        self.assertTrue(guide.photo.name.startswith('guide_photos/'))

    def test_home_lists_new_guides_and_searches_them(self):
        response = self.client.get(reverse('home'))
        self.assertContains(response, self.guide.title)

        response = self.client.get(reverse('home'), {'q': 'business account'})
        self.assertContains(response, self.guide.title)

        response = self.client.get(reverse('home'), {'q': 'unrelated phrase'})
        self.assertNotContains(response, self.guide.title)

    def test_guide_list_searches_summary(self):
        self.guide.summary = 'Renew an official document'
        self.guide.save(update_fields=['summary'])
        response = self.client.get(reverse('guides:list'), {'q': 'official document'})
        self.assertContains(response, self.guide.title)

    def test_tip_can_include_photos(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('guides:tip_create', args=[self.guide.slug, self.step.id]),
            {'body': 'This queue is usually closed', 'photos': [tiny_png()]},
        )
        self.assertEqual(response.status_code, 200)
        tip = StepTip.objects.get(body='This queue is usually closed')
        self.assertEqual(StepTipPhoto.objects.filter(tip=tip).count(), 1)
        self.assertEqual(len(response.json()['photos']), 1)

    def test_question_can_be_general_or_linked_to_current_step(self):
        self.client.force_login(self.user)
        general = self.client.post(
            reverse('guides:question_create', args=[self.guide.slug]),
            json.dumps({'body': 'Does this apply everywhere?', 'step_id': 'general'}),
            content_type='application/json',
        )
        linked = self.client.post(
            reverse('guides:question_create', args=[self.guide.slug]),
            json.dumps({'body': 'Which ID is accepted?', 'step_id': self.step.id}),
            content_type='application/json',
        )
        self.assertEqual(general.status_code, 200)
        self.assertEqual(linked.status_code, 200)
        self.assertIsNone(GuideQuestion.objects.get(body='Does this apply everywhere?').step)
        self.assertEqual(GuideQuestion.objects.get(body='Which ID is accepted?').step, self.step)

    def test_question_author_can_accept_answer(self):
        question = GuideQuestion.objects.create(guide=self.guide, step=self.step, author=self.user, body='What do I bring?')
        answerer = get_user_model().objects.create_user(username='answerer', password='pass')
        answer = GuideAnswer.objects.create(question=question, author=answerer, body='Bring photo ID.')
        self.client.force_login(self.user)
        response = self.client.post(reverse('guides:answer_accept', args=[self.guide.slug, question.id, answer.id]))
        self.assertRedirects(response, f"{reverse('guides:detail', args=[self.guide.slug])}#question-{question.id}")
        answer.refresh_from_db()
        self.assertTrue(answer.is_accepted)

    def test_guide_deletion_requires_independent_confirmation(self):
        marker = get_user_model().objects.create_user(username='marker', password='pass')
        confirmer = get_user_model().objects.create_user(username='confirmer', password='pass')
        self.client.force_login(marker)
        response = self.client.post(reverse('guides:mark_delete', args=[self.guide.slug]), {'reason': 'Duplicate'})
        self.assertEqual(response.status_code, 200)
        self.guide.refresh_from_db()
        self.assertTrue(self.guide.marked_for_deletion)

        response = self.client.post(reverse('guides:confirm_delete', args=[self.guide.slug]))
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Guide.objects.filter(pk=self.guide.pk).exists())

        self.client.force_login(confirmer)
        response = self.client.post(reverse('guides:confirm_delete', args=[self.guide.slug]))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Guide.objects.filter(pk=self.guide.pk).exists())

    def test_original_author_can_veto_or_delete_guide(self):
        marker = get_user_model().objects.create_user(username='marker2', password='pass')
        self.client.force_login(marker)
        self.client.post(reverse('guides:mark_delete', args=[self.guide.slug]), {'reason': 'Outdated'})
        self.client.force_login(self.user)
        response = self.client.post(reverse('guides:veto_delete', args=[self.guide.slug]))
        self.assertRedirects(response, reverse('guides:detail', args=[self.guide.slug]))
        self.guide.refresh_from_db()
        self.assertFalse(self.guide.marked_for_deletion)

        response = self.client.post(reverse('guides:delete', args=[self.guide.slug]))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Guide.objects.filter(pk=self.guide.pk).exists())

    def test_only_tip_author_can_delete_tip(self):
        tip = StepTip.objects.create(step=self.step, body='Author-owned tip', submitted_by=self.user)
        other = get_user_model().objects.create_user(username='other-delete', password='pass')
        self.client.force_login(other)
        response = self.client.post(reverse('guides:tip_delete', args=[self.guide.slug, tip.id]))
        self.assertEqual(response.status_code, 403)
        self.client.force_login(self.user)
        response = self.client.post(reverse('guides:tip_delete', args=[self.guide.slug, tip.id]))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(StepTip.objects.filter(pk=tip.pk).exists())

    def test_create_accepts_step_photos_and_markdown(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('guides:create'), {
            'title': 'Guide with photos',
            'steps_json': json.dumps([
                {'title': 'Photo step', 'instruction': '**Bring ID**\n- Copy', 'position': 1},
            ]),
            'step_photos_0': [tiny_png()],
        })
        guide = Guide.objects.get(title='Guide with photos')
        self.assertRedirects(response, reverse('guides:detail', args=[guide.slug]))
        step = guide.current_version.steps.get()
        self.assertEqual(StepPhoto.objects.filter(step=step).count(), 1)
        self.assertIn('<strong>Bring ID</strong>', str(guide_markdown(step.instruction)))
