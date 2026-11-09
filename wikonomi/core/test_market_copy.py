"""Country-sensitive site copy must follow the active market without rewriting guide data."""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from core.models import Business, PriceReport, Product
from guides.models import Guide, GuideVersion
from users.signup_flow import WELCOME_PENDING_SESSION_KEY


class CountrySiteCopyTests(TestCase):
    def test_about_page_for_india_explains_local_scope_and_png_origin(self):
        response = self.client.get(reverse("about"), HTTP_CF_IPCOUNTRY="IN")
        self.assertContains(response, "prices in India")
        self.assertContains(response, "Wikonomi began in Papua New Guinea")
        self.assertNotContains(response, "Join Papua New Guineans using Wikonomi")
        self.assertNotContains(response, "Fresh prices added daily")

    def test_how_to_use_has_country_guidance_and_local_currency(self):
        response = self.client.get(reverse("how_to_use"), HTTP_CF_IPCOUNTRY="FJ")
        self.assertContains(response, "Browsing in Fiji")
        self.assertContains(response, "FJD")
        self.assertContains(response, "Changing country does not convert an existing price.")
        self.assertNotContains(response, "the current PNG process")

    def test_guide_list_is_honest_about_global_guides(self):
        response = self.client.get(reverse("guides:list"), HTTP_CF_IPCOUNTRY="IN")
        self.assertContains(response, "while browsing India")
        self.assertContains(response, "Guides are not yet filtered by country")
        self.assertNotContains(response, "Clear, local steps for getting things done in PNG.")

    def test_guide_detail_warns_not_country_verified(self):
        user = User.objects.create_user(username="writer", password="test-secret")
        guide = Guide.objects.create(title="Apply for a licence",
                                     slug="apply-for-licence", created_by=user)
        version = GuideVersion.objects.create(guide=guide, edited_by=user)
        guide.current_version = version
        guide.save(update_fields=["current_version"])
        response = self.client.get(
            reverse("guides:detail", args=[guide.slug]), HTTP_CF_IPCOUNTRY="IN"
        )
        self.assertContains(response, "You are browsing Wikonomi for India.")
        self.assertContains(response, "This guide has not been verified for your country.")

    def test_guide_create_page_mentions_selected_country(self):
        user = User.objects.create_user(username="author", password="test-secret")
        self.client.force_login(user)
        user.profile.preferred_country_code = "FJ"
        user.profile.save(update_fields=["preferred_country_code"])
        response = self.client.get(reverse("guides:create"))
        self.assertContains(response, "get something done in Fiji")
        self.assertContains(response, "How to register a business in Fiji")

    def test_welcome_and_sharing_message_respect_saved_choice(self):
        user = User.objects.create_user(username="welcome-reader", password="test-secret")
        self.client.force_login(user)
        user.profile.preferred_country_code = "IN"
        user.profile.save(update_fields=["preferred_country_code"])
        session = self.client.session
        session[WELCOME_PENDING_SESSION_KEY] = True
        session.save()
        response = self.client.get(reverse("welcome"), HTTP_CF_IPCOUNTRY="PG")
        self.assertContains(response, "India is full of businesses")
        self.assertContains(response, "community-reported prices in India")
        self.assertNotContains(response, "🇵🇬 Ever wished")

    def test_price_capture_shows_market_currency_help(self):
        response = self.client.get(reverse("add_price"), HTTP_CF_IPCOUNTRY="IN")
        self.assertContains(response, "Your selected country is India")
        self.assertContains(response, "INR")

    def test_product_seo_follows_browsing_market(self):
        Product.objects.create(name="Example rice", slug="example-rice")
        product = Product.objects.get(slug="example-rice")
        response = self.client.get(
            reverse("product_detail", args=[product.pk]), HTTP_CF_IPCOUNTRY="IN"
        )
        self.assertContains(response, "Compare Example rice prices in India")

    def test_business_seo_uses_business_origin_not_viewer_ip(self):
        business = Business.objects.create(name="Example Fiji Shop",
                                           slug="example-fiji-shop",
                                           country_code="FJ")
        response = self.client.get(
            reverse("business_detail", args=[business.pk]), HTTP_CF_IPCOUNTRY="IN"
        )
        self.assertContains(response, "Example Fiji Shop in Fiji")
        self.assertNotContains(response, "Example Fiji Shop in India")
