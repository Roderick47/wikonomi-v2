from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from core.models import Business, PriceReport, Product
from guides.models import Guide


class StaticSitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.7

    def items(self):
        return ['home', 'product_list', 'business_list', 'guides:list', 'about']

    def location(self, item):
        return reverse(item)


class ProductSitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.8

    def items(self):
        return Product.objects.order_by('id')

    def location(self, product):
        return reverse('product_detail', args=[product.pk])

    def lastmod(self, product):
        return product.created_at


class BusinessSitemap(Sitemap):
    changefreq = 'monthly'
    priority = 0.7

    def items(self):
        return Business.objects.order_by('id')

    def location(self, business):
        return reverse('business_detail', args=[business.pk])

    def lastmod(self, business):
        return business.created_at


class PriceReportSitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.7

    def items(self):
        return PriceReport.objects.filter(marked_for_deletion=False).order_by('id')

    def location(self, report):
        return reverse('price_detail', args=[report.pk])

    def lastmod(self, report):
        return report.updated_at


class GuideSitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.9

    def items(self):
        return Guide.objects.filter(
            current_version__status='published',
            marked_for_deletion=False,
        ).select_related('current_version').order_by('id')

    def location(self, guide):
        return reverse('guides:detail', args=[guide.slug])

    def lastmod(self, guide):
        return guide.current_version.created_at


sitemaps = {
    'static': StaticSitemap,
    'products': ProductSitemap,
    'businesses': BusinessSitemap,
    'prices': PriceReportSitemap,
    'guides': GuideSitemap,
}
