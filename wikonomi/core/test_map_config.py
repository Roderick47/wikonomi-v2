from django.test import SimpleTestCase, override_settings
from core.context_processors import map_config


class MapConfigTests(SimpleTestCase):
    @override_settings(MAPBOX_PUBLIC_TOKEN=' pk.test ', MAPBOX_STYLE_URL='mapbox://styles/example/style')
    def test_public_token_and_custom_style(self):
        self.assertEqual(map_config(None)['wikonomi_map_config'], {
            'accessToken': 'pk.test', 'style': 'mapbox://styles/example/style',
        })

    @override_settings(MAPBOX_PUBLIC_TOKEN='sk.never-expose')
    def test_secret_token_is_not_exposed(self):
        self.assertEqual(map_config(None)['wikonomi_map_config']['accessToken'], '')

    @override_settings(MAPBOX_PUBLIC_TOKEN='')
    def test_blank_token_allows_fallback(self):
        self.assertEqual(map_config(None)['wikonomi_map_config']['accessToken'], '')
