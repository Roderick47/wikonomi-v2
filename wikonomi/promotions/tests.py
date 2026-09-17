from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from categories.models import Category as PriceCategory, Subcategory
from core.models import Business, BusinessBranch, PriceReport, Product

from .forms import PNG_TIME_ZONE, PromotionForm
from .models import Promotion, PromotionTarget
from .services import applicable_promotions, effective_price


class PromotionTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester', password='pass12345')
        self.business = Business.objects.create(name='Example Store', slug='example-store')
        self.other_business = Business.objects.create(name='Other Store', slug='other-store')
        self.product = Product.objects.create(name='Example Rice 1kg', slug='example-rice-1kg')
        self.other_product = Product.objects.create(name='Example Oil 1L', slug='example-oil-1l')
        self.price = PriceReport.objects.create(
            product=self.product,
            business=self.business,
            user=self.user,
            price=Decimal('100.00'),
            currency='PGK',
        )

    def _promotion(self, **overrides):
        values = {
            'business': self.business,
            'title': 'Weekend Sale',
            'deal_type': Promotion.DealType.PERCENT,
            'scope': Promotion.Scope.STOREWIDE,
            'discount_value': Decimal('20.00'),
            'start_at': timezone.now() - timedelta(hours=1),
            'end_at': timezone.now() + timedelta(days=2),
            'created_by': self.user,
        }
        values.update(overrides)
        return Promotion.objects.create(**values)

    def test_active_queryset_excludes_scheduled_and_expired_promotions(self):
        active = self._promotion(title='Active')
        self._promotion(title='Scheduled', start_at=timezone.now() + timedelta(days=1), end_at=timezone.now() + timedelta(days=2))
        self._promotion(title='Expired', start_at=timezone.now() - timedelta(days=2), end_at=timezone.now() - timedelta(days=1))
        self.assertEqual(list(Promotion.objects.active()), [active])

    def test_storewide_percent_overlay_does_not_mutate_observed_price(self):
        promotion = self._promotion(discount_value=Decimal('20.00'))
        result = effective_price(self.price)
        self.assertEqual(result['effective_price'], Decimal('80.00'))
        self.assertEqual(result['regular_price'], Decimal('100.00'))
        self.assertEqual(result['promotion'], promotion)
        self.price.refresh_from_db()
        self.assertEqual(self.price.price, Decimal('100.00'))

    def test_product_promotion_only_applies_to_selected_product(self):
        promotion = self._promotion(scope=Promotion.Scope.PRODUCT)
        PromotionTarget.objects.create(promotion=promotion, product=self.product)
        other_price = PriceReport.objects.create(product=self.other_product, business=self.business, user=self.user, price=Decimal('50.00'))
        self.assertEqual(list(applicable_promotions(self.price)), [promotion])
        self.assertFalse(applicable_promotions(other_price).exists())

    def test_category_promotion_uses_existing_price_subcategory_taxonomy(self):
        category = PriceCategory.objects.create(name='Groceries', slug='groceries')
        subcategory = Subcategory.objects.create(category=category, name='Rice', slug='rice')
        self.price.subcategory = subcategory
        self.price.save(update_fields=['subcategory'])
        promotion = self._promotion(scope=Promotion.Scope.CATEGORY)
        PromotionTarget.objects.create(promotion=promotion, category=category)
        self.assertEqual(list(applicable_promotions(self.price)), [promotion])

    def test_multiple_promotions_are_not_stacked_and_best_single_offer_wins(self):
        twenty_percent = self._promotion(title='20 percent', discount_value=Decimal('20'))
        thirty_percent = self._promotion(title='30 percent', discount_value=Decimal('30'))
        result = effective_price(self.price)
        self.assertEqual(result['effective_price'], Decimal('70.00'))
        self.assertEqual(result['promotion'], thirty_percent)
        self.assertNotEqual(result['promotion'], twenty_percent)

    def test_fixed_special_price_is_marked_as_observed_not_calculated(self):
        promotion = self._promotion(deal_type=Promotion.DealType.FIXED_PRICE, discount_value=None, special_price=Decimal('65.00'))
        result = effective_price(self.price)
        self.assertEqual(result['effective_price'], Decimal('65.00'))
        self.assertFalse(result['is_estimate'])
        self.assertEqual(result['promotion'], promotion)

    def test_promotion_from_other_business_does_not_apply(self):
        self._promotion(business=self.other_business)
        self.assertFalse(applicable_promotions(self.price).exists())


class PromotionFormTests(TestCase):
    def setUp(self):
        self.business = Business.objects.create(name='PNG Store', slug='png-store')

    def _save_for_business(self, form):
        promotion = form.save(commit=False)
        promotion.business = self.business
        promotion.save()
        return promotion

    def test_one_week_duration_is_calculated_in_png_local_time(self):
        form = PromotionForm(data={
            'business_name': self.business.name,
            'title': 'PNG Week Sale',
            'kind': Promotion.Kind.SALE,
            'deal_type': Promotion.DealType.PERCENT,
            'scope': Promotion.Scope.STOREWIDE,
            'discount_value': '10',
            'start_at': '2026-09-16T08:00',
            'duration': PromotionForm.Duration.ONE_WEEK,
            'description': '',
            'terms': '',
        })
        self.assertTrue(form.is_valid(), form.errors)
        promotion = self._save_for_business(form)
        local_start = promotion.start_at.astimezone(PNG_TIME_ZONE)
        local_end = promotion.end_at.astimezone(PNG_TIME_ZONE)
        self.assertEqual((local_start.hour, local_start.minute), (8, 0))
        self.assertEqual(local_end - local_start, timedelta(days=7))

    def test_today_only_ends_at_png_end_of_day(self):
        form = PromotionForm(data={
            'business_name': self.business.name,
            'title': 'One Day Sale',
            'kind': Promotion.Kind.SALE,
            'deal_type': Promotion.DealType.PERCENT,
            'scope': Promotion.Scope.STOREWIDE,
            'discount_value': '15',
            'start_at': '2026-09-16T08:00',
            'duration': PromotionForm.Duration.TODAY,
            'description': '',
            'terms': '',
        })
        self.assertTrue(form.is_valid(), form.errors)
        promotion = self._save_for_business(form)
        local_end = promotion.end_at.astimezone(PNG_TIME_ZONE)
        self.assertEqual((local_end.year, local_end.month, local_end.day), (2026, 9, 16))
        self.assertEqual((local_end.hour, local_end.minute, local_end.second), (23, 59, 59))


class PromotionRolloutTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='normal', password='pass12345')
        self.staff = User.objects.create_user(username='staff', password='pass12345', is_staff=True)
        self.business = Business.objects.create(name='Rollout Store', slug='rollout-store')
        self.branch = BusinessBranch.objects.create(
            canonical_business=self.business,
            name='Waigani',
            is_active=True,
        )

    def _special_payload(self, **overrides):
        payload = {
            'business_name': self.business.name,
            'title': 'Easter Sale',
            'kind': Promotion.Kind.EVENT,
            'deal_type': Promotion.DealType.PERCENT,
            'scope': Promotion.Scope.STOREWIDE,
            'discount_value': '30',
            'start_at': '2026-09-16T09:00',
            'duration': PromotionForm.Duration.TWO_WEEKS,
            'description': '30% off across the store.',
            'terms': '',
        }
        payload.update(overrides)
        return payload

    @override_settings(PROMOTIONS_ENABLED=False)
    def test_public_specials_route_is_hidden_when_feature_is_disabled(self):
        response = self.client.get(reverse('promotions:list'))
        self.assertEqual(response.status_code, 404)

    @override_settings(PROMOTIONS_ENABLED=False)
    def test_staff_can_preview_when_public_feature_is_disabled(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse('promotions:list'))
        self.assertEqual(response.status_code, 200)

    @override_settings(PROMOTIONS_ENABLED=True)
    def test_special_report_form_offers_existing_business_and_branch_names(self):
        response = self.client.get(reverse('promotions:create'))
        self.assertContains(response, 'list="business_list"')
        self.assertContains(response, f'value="{self.business.name}"')
        self.assertContains(response, 'list="branch_list"')
        self.assertContains(response, f'value="{self.branch.name}"')
        self.assertContains(response, f'label="{self.business.name}"')

    @override_settings(PROMOTIONS_ENABLED=True)
    def test_create_special_reuses_existing_business_and_branch(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('promotions:create'),
            data=self._special_payload(branch_name=self.branch.name),
        )
        self.assertEqual(response.status_code, 302)
        promotion = Promotion.objects.get(title='Easter Sale')
        self.assertEqual(promotion.business, self.business)
        self.assertEqual(promotion.business_branch, self.branch)
        self.assertEqual(BusinessBranch.objects.filter(canonical_business=self.business, name=self.branch.name).count(), 1)

    @override_settings(PROMOTIONS_ENABLED=True)
    def test_typing_new_branch_creates_and_links_it(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('promotions:create'),
            data=self._special_payload(title='Boroko Special', branch_name='Boroko'),
        )
        self.assertEqual(response.status_code, 302)
        promotion = Promotion.objects.get(title='Boroko Special')
        self.assertEqual(promotion.business, self.business)
        self.assertIsNotNone(promotion.business_branch)
        self.assertEqual(promotion.business_branch.canonical_business, self.business)
        self.assertEqual(promotion.business_branch.name, 'Boroko')

    @override_settings(PROMOTIONS_ENABLED=True)
    def test_create_special_from_question_driven_form_reuses_existing_business(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('promotions:create'), data=self._special_payload())
        self.assertEqual(response.status_code, 302)
        promotion = Promotion.objects.get(title='Easter Sale')
        self.assertEqual(promotion.created_by, self.user)
        self.assertEqual(promotion.business, self.business)
        self.assertEqual(Business.objects.filter(name=self.business.name).count(), 1)
        self.assertEqual(promotion.scope, Promotion.Scope.STOREWIDE)
        self.assertEqual(promotion.discount_value, Decimal('30.00'))

    @override_settings(PROMOTIONS_ENABLED=True)
    def test_typing_new_business_name_creates_business_and_links_special(self):
        self.client.force_login(self.user)
        new_business_name = 'New Market Shop'
        response = self.client.post(
            reverse('promotions:create'),
            data=self._special_payload(business_name=new_business_name, title='Opening Special'),
        )
        self.assertEqual(response.status_code, 302)
        business = Business.objects.get(name=new_business_name)
        promotion = Promotion.objects.get(title='Opening Special')
        self.assertEqual(promotion.business, business)
