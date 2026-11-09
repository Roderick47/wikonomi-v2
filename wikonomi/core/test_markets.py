from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from core.markets import country_info, country_options, resolve_country, valid_country


class CountryCatalogTests(SimpleTestCase):
    def test_major_pacific_and_asian_markets_have_local_currency(self):
        expected = {"PG": "PGK", "AU": "AUD", "NZ": "NZD", "FJ": "FJD",
                    "SB": "SBD", "VU": "VUV", "WS": "WST", "TO": "TOP",
                    "IN": "INR", "ID": "IDR", "PH": "PHP", "SG": "SGD",
                    "JP": "JPY", "CN": "CNY", "KR": "KRW"}
        for code, currency in expected.items():
            with self.subTest(country=code):
                self.assertEqual(country_info(code)["currency"], currency)

    def test_broad_iso_coverage(self):
        self.assertGreaterEqual(len(country_options()), 240)
        self.assertTrue(valid_country("IN"))
        self.assertFalse(valid_country("XX"))


class CountryPreferenceTests(TestCase):
    def test_geo_ip_country_is_detected(self):
        response = self.client.get("/", HTTP_CF_IPCOUNTRY="IN")
        self.assertEqual(response.wsgi_request.market["code"], "IN")

    def test_invalid_geo_ip_falls_back_to_png(self):
        response = self.client.get("/", HTTP_CF_IPCOUNTRY="XX")
        self.assertEqual(response.wsgi_request.market["code"], "PG")

    def test_anonymous_user_can_select_country(self):
        response = self.client.post(reverse("choose_market"),
                                    {"country": "FJ", "next": "/"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.cookies["wk_country"].value, "FJ")
        self.assertEqual(self.client.get("/").wsgi_request.market["code"], "FJ")

    def test_logged_in_preference_persists(self):
        user = User.objects.create_user("country-user", password="test-secret")
        self.client.force_login(user)
        response = self.client.post(reverse("choose_market"),
                                    {"country": "IN", "next": "/"})
        self.assertEqual(response.status_code, 302)
        user.refresh_from_db()
        self.assertEqual(user.profile.preferred_country_code, "IN")

    def test_bad_country_is_rejected(self):
        response = self.client.post(reverse("choose_market"), {"country": "XX"})
        self.assertEqual(response.status_code, 400)

    def test_external_redirect_is_rejected(self):
        response = self.client.post(reverse("choose_market"),
                                    {"country": "AU", "next": "https://example.com/"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/")
