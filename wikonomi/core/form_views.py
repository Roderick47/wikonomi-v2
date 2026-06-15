import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.serializers.json import DjangoJSONEncoder
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils.text import slugify
from django.views.generic import CreateView

from .models import (
    Business,
    BusinessNormalizationService,
    PriceHistory,
    PriceReport,
    Product,
    ProductNormalizationService,
)
from .price_photo_models import PriceReportPhoto
from .views import PriceReportForm


MAX_PRICE_PHOTOS = 5


def _rewind(uploaded_file):
    try:
        uploaded_file.seek(0)
    except Exception:
        pass


def _add_photo_to_report(report, uploaded_file, order=0):
    _rewind(uploaded_file)
    return PriceReportPhoto.objects.create(
        price_report=report,
        image=uploaded_file,
        order=order,
    )


def _set_related_default_images(report, product, business, uploaded_file):
    if not uploaded_file:
        return

    if not report.image:
        _rewind(uploaded_file)
        report.image = uploaded_file
        report.save(update_fields=['image'])

    if product and not product.image:
        _rewind(uploaded_file)
        product.image = uploaded_file
        product.save(update_fields=['image'])

    if business and not business.image:
        _rewind(uploaded_file)
        business.image = uploaded_file
        business.save(update_fields=['image'])


def _save_new_price_photos(report, uploaded_files, product=None, business=None):
    if not uploaded_files:
        return

    current_count = report.photos.count()
    available_slots = max(0, MAX_PRICE_PHOTOS - current_count)
    photos_to_add = list(uploaded_files)[:available_slots]
    if not photos_to_add:
        return

    _set_related_default_images(report, product or report.product, business or report.business, photos_to_add[0])

    for index, uploaded_file in enumerate(photos_to_add):
        _add_photo_to_report(report, uploaded_file, current_count + index)


def _business_default_locations(businesses):
    locations = {}
    for business in businesses:
        get_default_location = getattr(business, 'get_default_location', None)
        if not callable(get_default_location):
            continue
        default_location = get_default_location()
        if not default_location:
            continue
        lat, lng = default_location
        get_source = getattr(business, 'get_default_location_source', None)
        locations[business.name] = {
            'latitude': lat,
            'longitude': lng,
            'source': get_source() if callable(get_source) else 'business default location',
        }
    return locations


def _get_or_create_product(product_name, user=None):
    product, was_created = ProductNormalizationService.normalize_price_report_data(
        product_name=product_name,
        category=None,
    )
    if was_created and user and getattr(user, 'is_authenticated', False):
        product.created_by = user
        product.save(update_fields=['created_by'])
    return product


def _get_or_create_business(business_name, business_location=''):
    if not business_name:
        return None, None
    business, branch, _ = BusinessNormalizationService.normalize_price_report_data(
        business_name=business_name,
        location=business_location,
    )
    return business, branch


def _unique_slug(model, value):
    base_slug = slugify(value) or 'item'
    slug = base_slug
    counter = 1
    while model.objects.filter(slug=slug).exists():
        slug = f'{base_slug}-{counter}'
        counter += 1
    return slug


class EnhancedPriceReportCreateView(CreateView):
    model = PriceReport
    form_class = PriceReportForm
    template_name = 'price_report_form.html'
    success_url = reverse_lazy('home')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        businesses = Business.objects.all().order_by('name')
        context['products'] = Product.objects.all().order_by('name')
        context['businesses'] = businesses
        context['business_default_locations_json'] = json.dumps(
            _business_default_locations(businesses),
            cls=DjangoJSONEncoder,
        )
        return context

    def form_valid(self, form):
        user = self.request.user
        if not user.is_authenticated:
            user, _ = User.objects.get_or_create(username='anonymous')
        form.instance.user = user

        product_name = self.request.POST.get('product_name', '').strip()
        if not product_name:
            form.add_error(None, 'Product name is required.')
            return self.form_invalid(form)

        product = _get_or_create_product(product_name, user)
        form.instance.product = product

        business = None
        business_name = self.request.POST.get('business_name', '').strip()
        business_location = self.request.POST.get('business_location', '').strip()
        if business_name:
            business, branch = _get_or_create_business(business_name, business_location)
            form.instance.business = business
            if branch:
                form.instance.business_branch = branch

        response = super().form_valid(form)

        photos = self.request.FILES.getlist('photos')
        if photos:
            _save_new_price_photos(self.object, photos, product=product, business=business)
        elif self.object.image:
            _set_related_default_images(self.object, product, business, self.object.image)

        tags_string = self.request.POST.get('tags', '').strip()
        if tags_string:
            tag_list = [tag.strip() for tag in tags_string.split(',') if tag.strip()]
            if tag_list:
                product.tags.add(*tag_list)

        return response


price_report_create = EnhancedPriceReportCreateView.as_view()


@login_required
def edit_price_report(request, pk):
    report = get_object_or_404(PriceReport, pk=pk)

    def context(form):
        return {
            'form': form,
            'report': report,
            'products': Product.objects.all().order_by('name'),
            'businesses': Business.objects.all().order_by('name'),
            'photos': report.photos.all(),
        }

    if request.method == 'POST':
        old_report = PriceReport.objects.get(pk=report.pk)
        old_price = old_report.price
        old_currency = old_report.currency
        form = PriceReportForm(request.POST, request.FILES, instance=report)

        if not form.is_valid():
            return render(request, 'price_report_edit.html', context(form))

        updated_report = form.save(commit=False)
        updated_report.last_edited_by = request.user

        product_name = request.POST.get('product_name', '').strip()
        if product_name:
            product = Product.objects.filter(name__iexact=product_name).first()
            if not product:
                product = Product.objects.create(
                    name=product_name,
                    slug=_unique_slug(Product, product_name),
                    created_by=request.user,
                )
            updated_report.product = product
        else:
            product = updated_report.product

        business_name = request.POST.get('business_name', '').strip()
        if business_name:
            business = Business.objects.filter(name__iexact=business_name).first()
            if not business:
                business = Business.objects.create(
                    name=business_name,
                    slug=_unique_slug(Business, business_name),
                )
            updated_report.business = business
        elif 'business_name' in request.POST:
            business = None
            updated_report.business = None
            updated_report.business_branch = None
        else:
            business = updated_report.business

        lat = request.POST.get('latitude')
        lng = request.POST.get('longitude')
        if lat and lng:
            try:
                updated_report.latitude = float(lat)
                updated_report.longitude = float(lng)
            except ValueError:
                messages.warning(request, 'Invalid coordinates provided. Location not updated.')
        elif lat == '' or lng == '':
            updated_report.latitude = None
            updated_report.longitude = None

        clear_image = request.POST.get('clear_image')
        if clear_image in ('1', 'true', 'True', 'on'):
            if updated_report.image:
                updated_report.image.delete(save=False)
            updated_report.image = None

        if 'image' in request.FILES:
            updated_report.image = request.FILES['image']

        updated_report.save()

        # Delete selected existing photos first so slots become available.
        delete_photo_ids = request.POST.getlist('delete_photos')
        if delete_photo_ids:
            for photo in report.photos.filter(id__in=delete_photo_ids):
                photo.image.delete(save=False)
                photo.delete()

        # Replace any single existing photo selected by the user.
        for photo in report.photos.all():
            replacement = request.FILES.get(f'update_photo_{photo.id}')
            if replacement:
                if photo.image:
                    photo.image.delete(save=False)
                _rewind(replacement)
                photo.image = replacement
                photo.save(update_fields=['image'])

        # Add new photos selected in the same form.
        new_photos = request.FILES.getlist('photos')
        if new_photos:
            _save_new_price_photos(updated_report, new_photos, product=updated_report.product, business=updated_report.business)

        # Keep legacy report/product/business images useful for feed cards and sharing.
        first_photo = updated_report.photos.first()
        if first_photo and not updated_report.image:
            updated_report.image = first_photo.image
            updated_report.save(update_fields=['image'])
        if updated_report.image:
            _set_related_default_images(updated_report, updated_report.product, updated_report.business, updated_report.image)

        if 'tags' in request.POST:
            updated_report.product.tags.clear()
            tags_string = request.POST.get('tags', '').strip()
            if tags_string:
                tag_list = [tag.strip() for tag in tags_string.split(',') if tag.strip()]
                if tag_list:
                    updated_report.product.tags.add(*tag_list)

        if old_price != updated_report.price or old_currency != updated_report.currency:
            PriceHistory.objects.create(
                price_report=updated_report,
                old_price=old_price,
                new_price=updated_report.price,
                old_currency=old_currency,
                new_currency=updated_report.currency,
                changed_by=request.user,
                notes=f'Price updated from {old_price} {old_currency} to {updated_report.price} {updated_report.currency}',
            )

        messages.success(request, 'Price report updated successfully!')
        return redirect('price_detail', pk=updated_report.pk)

    form = PriceReportForm(instance=report)
    return render(request, 'price_report_edit.html', context(form))
