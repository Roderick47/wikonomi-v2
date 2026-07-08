import json

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from core.models import Business
from .models import Guide, GuideRating, GuideVersion, Step, StepPhoto, StepTip, StepTipPhoto
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
        response = self.client.post(reverse('guides:fork', args=[self.guide.slug]), {'organization': new_business.id})
        fork = Guide.objects.get(forked_from=self.guide)
        self.assertRedirects(response, reverse('guides:detail', args=[fork.slug]))
        self.assertEqual(fork.organization, new_business)
        self.assertEqual(fork.current_version.steps.count(), 1)
        self.assertEqual(fork.current_version.steps.first().title, self.step.title)
        self.assertEqual(fork.current_version.steps.first().instruction, self.step.instruction)
        self.assertEqual(StepTip.objects.filter(step__version=fork.current_version).count(), 0)

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
