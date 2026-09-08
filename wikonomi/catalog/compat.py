from .models import ProductIdentity
from .services import create_or_match_product, find_best_product


def install_core_product_matching_adapter():
    """Keep existing core callers working while routing them through catalog identity."""
    from core.models import ProductMatcher, ProductNormalizationService

    def find_best_match(product_name, min_similarity=0.7):
        match = find_best_product(product_name, min_similarity=min_similarity)
        return match.product, match.score

    def create_or_match(product_name, category=None, created_by=None):
        product, created, _match = create_or_match_product(
            product_name,
            category=category,
            created_by=created_by,
            source=ProductIdentity.Source.WEB,
            created_via='web',
        )
        return product, created

    def normalize_price_report_data(product_name, business_name=None, category=None):
        return create_or_match(product_name, category=category)

    ProductMatcher.find_best_match = staticmethod(find_best_match)
    ProductMatcher.create_or_match_product = staticmethod(create_or_match)
    ProductNormalizationService.normalize_price_report_data = staticmethod(normalize_price_report_data)
