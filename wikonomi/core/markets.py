"""Country-aware discovery metadata, without automatic currency conversion.

Use ISO 3166-1 alpha-2 for locations and ISO 4217 for money. All names
remain in English while Wikonomi develops its international translations.
"""
from functools import lru_cache

import pycountry
from babel import Locale
from babel.numbers import get_currency_symbol, get_territory_currencies

DEFAULT_COUNTRY = "PG"
COUNTRY_COOKIE = "wk_country"
# Highest-discovery markets are kept at the top of the selector. Every other
# ISO country/territory is available in the alphabetical section.
FEATURED_COUNTRIES = (
    "PG", "AU", "NZ", "FJ", "SB", "VU", "WS", "TO", "KI", "TV",
    "NR", "FM", "MH", "PW", "CK", "NU", "NC", "PF", "GU", "MP",
    "AS", "WF", "TK", "IN", "ID", "PH", "MY", "SG", "TH", "VN",
    "JP", "CN", "KR", "BD", "PK", "LK", "NP", "MM", "KH", "LA",
    "BN", "TL", "TW", "HK", "MO", "MN", "MV", "BT", "AE", "SA",
    "QA", "KW", "OM", "BH", "TR", "IL", "GB", "US", "CA",
    "DE", "FR", "IT", "ES", "NL", "CH", "SE", "NO", "DK",
    "ZA", "NG", "KE", "GH", "BR", "MX", "AR",
)
# Country-specific variations of English naming.
DISPLAY_NAMES = {"PG": "Papua New Guinea", "KR": "South Korea",
                 "FM": "Micronesia", "TW": "Taiwan", "US": "United States"}
# In jurisdictions where CLDR has no current fiat tender, don't suggest USD
# as if it were the local currency. Currency can remain unset.
FALLBACK_CURRENCIES = {"AQ": None}


@lru_cache(maxsize=1)
def country_options():
    en = Locale.parse("en")
    results = {}
    for country in pycountry.countries:
        code = country.alpha_2
        currency_codes = get_territory_currencies(code, tender=True)
        currency = currency_codes[0] if currency_codes else FALLBACK_CURRENCIES.get(code)
        name = DISPLAY_NAMES.get(code) or en.territories.get(code) or country.name
        symbol = get_currency_symbol(currency, locale="en") if currency else ""
        results[code] = {"code": code, "name": str(name),
                         "currency": currency or "", "symbol": symbol}
    featured = [results[c] for c in FEATURED_COUNTRIES if c in results]
    rest = sorted((v for k, v in results.items() if k not in FEATURED_COUNTRIES),
                  key=lambda item: item["name"])
    return tuple(featured + rest)


@lru_cache(maxsize=1)
def country_lookup():
    return {country["code"]: country for country in country_options()}


def valid_country(code):
    return isinstance(code, str) and code.upper() in country_lookup()


def country_info(code):
    return country_lookup().get(str(code or "").upper(), country_lookup()[DEFAULT_COUNTRY])


def resolve_country(request):
    # Explicit profile choice takes priority across devices. A cookie supports
    # anonymous browsing. Detection is only a suggestion, never access control.
    if request.user.is_authenticated:
        profile = getattr(request.user, "profile", None)
        preferred = getattr(profile, "preferred_country_code", "")
        if valid_country(preferred):
            return preferred.upper()
    cookie = request.COOKIES.get(COUNTRY_COOKIE, "")
    if valid_country(cookie):
        return cookie.upper()
    detected = request.META.get("HTTP_CF_IPCOUNTRY", "").upper()
    if valid_country(detected):
        return detected
    return DEFAULT_COUNTRY


class CountryMarketMiddleware:
    """Attach the current browsing market after AuthenticationMiddleware."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.market = country_info(resolve_country(request))
        request.market_country_code = request.market["code"]
        request.market_currency = request.market["currency"]
        return self.get_response(request)


def market_context(request):
    return {"market": getattr(request, "market", country_info(DEFAULT_COUNTRY)),
            "market_countries": country_options()}


def choose_market(request):
    from django.http import HttpResponseBadRequest
    from django.shortcuts import redirect
    from django.urls import reverse
    from django.utils.http import url_has_allowed_host_and_scheme
    from django.views.decorators.http import require_POST

    @require_POST
    def apply(request):
        selection = (request.POST.get("country") or "").strip().upper()
        if selection != "AUTO" and not valid_country(selection):
            return HttpResponseBadRequest("Select a valid country.")
        if request.user.is_authenticated:
            from users.models import Profile
            profile, _ = Profile.objects.get_or_create(user=request.user)
            profile.preferred_country_code = "" if selection == "AUTO" else selection
            profile.save(update_fields=["preferred_country_code"])
        destination = request.POST.get("next") or reverse("home")
        if not url_has_allowed_host_and_scheme(
            destination, allowed_hosts={request.get_host()}, require_https=request.is_secure()
        ):
            destination = reverse("home")
        response = redirect(destination)
        if selection == "AUTO":
            response.delete_cookie(COUNTRY_COOKIE, samesite="Lax")
        else:
            response.set_cookie(
                COUNTRY_COOKIE, selection, max_age=365 * 24 * 60 * 60,
                httponly=True, secure=not request.is_secure() is False or not __debug__,
                samesite="Lax",
            )
        return response

    return apply(request)
