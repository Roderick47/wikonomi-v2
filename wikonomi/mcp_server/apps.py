from django.apps import AppConfig


class MCPServerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'mcp_server'
    verbose_name = 'Wikonomi MCP'

    def ready(self):
        from .current_price_services import install_service_upgrades
        from .identity_services import install_identity_service_upgrades
        from .smart_search_services import install_smart_search_upgrades

        install_service_upgrades()
        install_identity_service_upgrades()
        install_smart_search_upgrades()
