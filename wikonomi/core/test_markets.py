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

    def test_country_cookie_overrides_geolocation(self):
        self.client.cookies["wk_country"] = "FJ"
        response = self.client.get("/", HTTP_CF_IPCOUNTRY="IN")
        self.assertEqual(response.wsgi_request.market["code"], "FJ")

    def test_returns_to_detection_after_clearing_manual_choice(self):
        self.client.post(reverse("choose_market"), {"country": "IN"})
        response = self.client.post(reverse("choose_market"), {"country": "AUTO"})
        self.assertEqual(response.status_code, 302)
        response = self.client.get("/", HTTP_CF_IPCOUNTRY="AU")
        self.assertEqual(response.wsgi_request.market["code"], "AU")


class MarketDataIsolationTests(TestCase):
    def setUp(self):
        from core.models import Business, Product, PriceReport
        user = User.objects.create_user("market-tester", password="test-secret")
        product = Product.objects.create(name="Market test rice", slug="market-test-rice")
        png_store = Business.objects.create(name="Market Demo Store", slug="market-demo-store", country_code="PG")
        india_store = Business.objects.create(name="Market Demo Store", slug="market-demo-store-in", country_code="IN")
        self.pg = PriceReport.objects.create(
            product=product, business=png_store, user=user,
            price="15.50", currency="PGK", country_code="PG",
            latitude=-9.45, longitude=147.18,
        )
        self.india = PriceReport.objects.create(
            product=product, business=india_store, user=user,
            price="88.00", currency="INR", country_code="IN",
            latitude=28.61, longitude=77.20,
        )
        self.product = product

    def test_home_and_map_are_isolated_per_market(self):
        response = self.client.get("/", HTTP_CF_IPCOUNTRY="IN")
        ids = {r.id for r in response.context["latest_prices"]}
        self.assertEqual(ids, {self.india.id})
        response = self.client.get("/api/map-prices/", HTTP_CF_IPCOUNTRY="IN")
        self.assertEqual({p["id"] for p in response.json()["items"]}, {self.india.id})
        response = self.client.get("/api/map-prices/", HTTP_CF_IPCOUNTRY="PG")
        self.assertEqual({p["id"] for p in response.json()["items"]}, {self.pg.id})

    def test_product_comparison_does_not_mix_countries(self):
        response = self.client.get(
            reverse("product_detail", args=[self.product.pk]), HTTP_CF_IPCOUNTRY="IN"
        )
        self.assertEqual(response.context["total_reports"], 1)
        self.assertEqual(response.context["comparison_currency"], "INR")
        self.assertEqual(response.context["cheapest_report"].pk, self.india.pk)

    def test_product_listing_shows_local_prices_only(self):
        response = self.client.get(reverse("product_list"), HTTP_CF_IPCOUNTRY="IN")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["products_page"].object_list[0].latest_report.id,
                         self.india.id)
