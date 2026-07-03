import json
import csv
import io
import re
from decimal import Decimal, InvalidOperation
from django.db import transaction
from django.utils.text import slugify
from django.urls import reverse_lazy, reverse
from django.views.generic import CreateView, DetailView, UpdateView
from django.shortcuts import render, redirect, get_object_or_404
from django.template.loader import render_to_string
from django.db.models import Avg, Min, Max, Count, Q
from django.db.models.functions import Lower
from django.utils import timezone
from datetime import timedelta
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.core.cache import cache
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django import forms
from django.core.serializers.json import DjangoJSONEncoder
from django.views.decorators.cache import cache_page
from django.templatetags.static import static
from .models import PriceReport, PriceHistory, Product, Business, ProductWatchlist, Notification, ShoppingList, ShoppingListItem, ProductNormalizationService, ProductAlias, BusinessNormalizationService, BusinessMatcher, PriceLike, PriceReportRating, BusinessRating, create_like_threshold_notification, PriceReportPhoto
from comments.models import Comment
from .utils import annotate_with_distance
from categories.models import Category as PriceCategory, Subcategory, BusinessCategory, BusinessSubcategory


def _get_matched_product_ids(query):
    """
    Return matched product IDs for a search query.

    Uses independent ID queries instead of queryset unions so this stays
    compatible across database backends and avoids brittle compound SQL.
    """
    if not query:
        return set()

    query_signature = ProductAlias.create_normalized_signature(query)

    exact_ids = set(
        Product.objects.filter(name__icontains=query).values_list('id', flat=True)
    )
    alias_ids = set(
        Product.objects.filter(
            aliases__alias_name__icontains=query,
            aliases__is_active=True
        ).values_list('id', flat=True)
    )
    signature_ids = set(
        Product.objects.filter(
            aliases__signature=query_signature,
            aliases__is_active=True
        ).values_list('id', flat=True)
    )

    return exact_ids | alias_ids | signature_ids


def _rating_from_request(request):
    """Return a validated 1-5 integer rating from form data or a JSON body."""
    rating_value = request.POST.get('rating')

    if rating_value is None and request.body:
        try:
            payload = json.loads(request.body.decode(request.encoding or 'utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            payload = {}
        if isinstance(payload, dict):
            rating_value = payload.get('rating')

    if isinstance(rating_value, bool):
        return None

    if isinstance(rating_value, int):
        rating = rating_value
    elif isinstance(rating_value, str) and re.fullmatch(r'\s*[+-]?\d+\s*', rating_value):
        rating = int(rating_value)
    else:
        return None

    if rating < 1 or rating > 5:
        return None

    return rating


def _rating_summary(ratings_manager):
    summary = ratings_manager.aggregate(
        average_rating=Avg('rating'),
        rating_count=Count('id'),
    )
    average_rating = summary['average_rating']
    return {
        'average_rating': float(average_rating) if average_rating is not None else None,
        'rating_count': summary['rating_count'],
    }

class PriceReportForm(forms.ModelForm):
    category = forms.ModelChoiceField(
        queryset=PriceCategory.objects.all(),
        required=False,
        empty_label="Select a category",
        widget=forms.Select(attrs={'id': 'id_category', 'class': 'block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-brand-purple/50 focus:border-brand-blue sm:text-sm'}),
    )
    subcategory = forms.ModelChoiceField(
        queryset=Subcategory.objects.none(),
        required=False,
        empty_label="Select a subcategory",
        widget=forms.Select(attrs={'id': 'id_subcategory', 'class': 'block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-brand-purple/50 focus:border-brand-blue sm:text-sm'}),
    )

    class Meta:
        model = PriceReport
        fields = ['category', 'subcategory', 'price', 'currency', 'latitude', 'longitude', 'notes', 'image']
        widgets = {
            'price': forms.NumberInput(attrs={'class': 'block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm', 'step': '0.01'}),
            'currency': forms.TextInput(attrs={'class': 'block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm'}),
            'latitude': forms.HiddenInput(),
            'longitude': forms.HiddenInput(),
            'notes': forms.Textarea(attrs={'class': 'block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm', 'rows': 3}),
            'image': forms.FileInput(attrs={'class': 'hidden', 'accept': 'image/*'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'category' in self.data:
            try:
                cat_id = int(self.data.get('category'))
                self.fields['subcategory'].queryset = Subcategory.objects.filter(category_id=cat_id)
            except (ValueError, TypeError):
                pass
        elif self.initial.get('subcategory'):
            subcategory = self.initial['subcategory']
            self.fields['subcategory'].queryset = Subcategory.objects.filter(category=subcategory.category)
            self.fields['category'].initial = subcategory.category
        elif self.instance.pk and self.instance.subcategory:
            self.fields['subcategory'].queryset = Subcategory.objects.filter(
                category=self.instance.subcategory.category
            )
            self.fields['category'].initial = self.instance.subcategory.category

class BusinessForm(forms.ModelForm):
    business_category = forms.ModelChoiceField(
        queryset=BusinessCategory.objects.all(),
        required=False,
        empty_label="Select your industry",
        widget=forms.Select(attrs={'id': 'id_business_category', 'class': 'block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-brand-purple/50 focus:border-brand-blue sm:text-sm'}),
    )
    business_subcategory = forms.ModelChoiceField(
        queryset=BusinessSubcategory.objects.none(),
        required=False,
        empty_label="Select a subcategory",
        widget=forms.Select(attrs={'id': 'id_business_subcategory', 'class': 'block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-brand-purple/50 focus:border-brand-blue sm:text-sm'}),
    )

    class Meta:
        model = Business
        fields = ['name', 'business_category', 'business_subcategory', 'details', 'image']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm'}),
            'details': forms.Textarea(attrs={'class': 'block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm', 'rows': 4, 'placeholder': 'Add any additional information about this business...'}),
            'image': forms.FileInput(attrs={'class': 'hidden', 'accept': 'image/*'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'business_category' in self.data:
            try:
                cat_id = int(self.data.get('business_category'))
                self.fields['business_subcategory'].queryset = BusinessSubcategory.objects.filter(category_id=cat_id)
            except (ValueError, TypeError):
                pass
        elif self.instance.pk and self.instance.business_subcategory:
            self.fields['business_subcategory'].queryset = BusinessSubcategory.objects.filter(
                category=self.instance.business_subcategory.category
            )
            self.fields['business_category'].initial = self.instance.business_subcategory.category

class PriceReportCreateView(CreateView):
    model = PriceReport
    form_class = PriceReportForm
    template_name = 'price_report_form.html'
    success_url = reverse_lazy('home')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from .models import Product, Business
        businesses = Business.objects.all().order_by('name')
        context['products'] = Product.objects.all().order_by('name')
        context['businesses'] = businesses
        context['business_default_locations_json'] = json.dumps(
            self._get_business_default_locations(businesses),
            cls=DjangoJSONEncoder,
        )
        context.setdefault('form_title', 'Add a New Price')
        context.setdefault('form_intro', 'Help the community by sharing the price you found.')
        context.setdefault('submit_label', 'Save')
        context.setdefault('cancel_url', reverse('home'))
        context.setdefault('initial_product_name', self.request.GET.get('product_name', ''))
        context.setdefault('initial_business_name', self.request.GET.get('business_name', ''))
        return context

    def _get_business_default_locations(self, businesses):
        locations = {}
        for business in businesses:
            default_location = business.get_default_location()
            if default_location:
                lat, lng = default_location
                locations[business.name] = {
                    'latitude': lat,
                    'longitude': lng,
                    'source': business.get_default_location_source() or 'business default location',
                }
        return locations

    def _apply_business_default_location(self, form, business):
        default_location = business.get_default_location()
        if default_location:
            form.instance.latitude, form.instance.longitude = default_location
            return True

        if form.instance.latitude is None or form.instance.longitude is None:
            form.add_error(None, "Please set a location for this price so it can become this business's default location.")
            return False

        return True
        
    def form_valid(self, form):
        from django.contrib.auth.models import User
        
        try:
            # 1. Handle user
            if not self.request.user.is_authenticated:
                # MVP: get or create an anonymous user
                user, _ = User.objects.get_or_create(username='anonymous')
                form.instance.user = user
            else:
                form.instance.user = self.request.user

            # 2. Handle product (using normalization service)
            product_name = self.request.POST.get('product_name', '').strip()
            if not product_name:
                form.add_error(None, "Product name is required.")
                return self.form_invalid(form)
                
            # Use normalization service to find or create product
            product, was_created = ProductNormalizationService.normalize_price_report_data(
                product_name=product_name,
                category=None,
            )
            
            # If this is a newly created product, set the creator
            if was_created:
                product.created_by = form.instance.user
                product.save()

            form.instance.product = product
            
            # 2b. Handle business (using normalization service with branch support)
            business_name = self.request.POST.get('business_name', '').strip()
            business_location = self.request.POST.get('business_location', '').strip()
            
            if business_name:
                # Use normalization service to find or create business with branch
                business, branch, was_created = BusinessNormalizationService.normalize_price_report_data(
                    business_name=business_name,
                    location=business_location
                )
                
                # Set the branch on price report if we have one
                if branch:
                    form.instance.business_branch = branch
                    # Also set the main business for compatibility
                    form.instance.business = business
                
                form.instance.business = business

                # Prefer the business default location over any location selected
                # on the price form. If the business has no default yet, require
                # this first located price to seed future defaults.
                if not self._apply_business_default_location(form, business):
                    return self.form_invalid(form)

            # 3. Save form to hit the DB
            response = super().form_valid(form)

            # 3b. Handle multiple photo uploads
            from .models import PriceReportPhoto
            photos_files = self.request.FILES.getlist('photos')
            if photos_files:
                current_count = form.instance.photos.count()
                max_photos = 5
                available_slots = max_photos - current_count
                photos_to_add = photos_files[:available_slots]

                for i, photo_file in enumerate(photos_to_add):
                    PriceReportPhoto.objects.create(
                        price_report=form.instance,
                        image=photo_file,
                        order=current_count + i
                    )

                # Apply first photo to product/business if they don't have one
                if photos_to_add and not product.image:
                    product.image = photos_to_add[0]
                    product.save()
                if photos_to_add and hasattr(form.instance, 'business') and form.instance.business and not form.instance.business.image:
                    form.instance.business.image = photos_to_add[0]
                    form.instance.business.save()
            else:
                # Fallback to legacy single image field
                # Apply image to product/business if they don't have one and one was uploaded
                if form.instance.image:
                    if not product.image:
                        product.image = form.instance.image
                        product.save()
                    if hasattr(form.instance, 'business') and form.instance.business and not form.instance.business.image:
                        form.instance.business.image = form.instance.image
                        form.instance.business.save()

            # 4. Handle Tags (comma separated string)
            tags_string = self.request.POST.get('tags', '').strip()
            if tags_string:
                # taggit manages these automatically when we add them
                tag_list = [tag.strip() for tag in tags_string.split(',') if tag.strip()]
                if tag_list:
                    product.tags.add(*tag_list)

            duplicate_source_id = self.request.POST.get('duplicated_from')
            if duplicate_source_id:
                try:
                    source_report = PriceReport.objects.get(pk=duplicate_source_id)
                    if form.instance.duplicated_from_id != source_report.pk:
                        form.instance.duplicated_from = source_report
                        form.instance.save(update_fields=['duplicated_from'])
                except PriceReport.DoesNotExist:
                    pass

            return response
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error in price report creation: {str(e)}")
            form.add_error(None, f"An error occurred: {str(e)}")
            return self.form_invalid(form)

price_report_create = PriceReportCreateView.as_view()

class PriceReportDuplicateView(PriceReportCreateView):
    """Create a new report from an existing one, excluding store/location/photos."""

    def dispatch(self, request, *args, **kwargs):
        self.source_report = get_object_or_404(
            PriceReport.objects.select_related('product', 'business', 'business_branch', 'subcategory__category'),
            pk=kwargs['pk'],
        )
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        initial = super().get_initial()
        initial.update({
            'price': self.source_report.price,
            'currency': self.source_report.currency,
            'notes': self.source_report.notes,
            'subcategory': self.source_report.subcategory,
        })
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'form_title': 'Duplicate price report',
            'form_intro': 'The product, price, category, tags, and notes are copied. Choose the new store/location and add fresh photos for this report.',
            'submit_label': 'Save duplicate report',
            'cancel_url': reverse('price_detail', args=[self.source_report.pk]),
            'duplicate_source': self.source_report,
            'initial_product_name': self.source_report.product.name,
            'initial_business_name': '',
            'initial_tags': ', '.join(self.source_report.product.tags.names()),
        })
        return context

    def form_valid(self, form):
        form.instance.duplicated_from = self.source_report
        return super().form_valid(form)


price_report_duplicate = PriceReportDuplicateView.as_view()


def _get_prices_queryset(request):
    """Helper to get and sort prices uniformly across feed and map endpoints."""
    query = request.GET.get('q', '').strip()
    sort = request.GET.get('sort', 'recent')
    user_lat = request.GET.get('lat')
    user_lng = request.GET.get('lng')
    
    qs = PriceReport.objects.select_related('product', 'business', 'user').prefetch_related('user__profile').annotate(
        average_rating=Avg('ratings__rating'),
        rating_count=Count('ratings'),
    )
    
    if query:
        # Enhanced search using product normalization
        matched_product_ids = _get_matched_product_ids(query)
        
        # Build search query
        search_query = Q()
        
        if matched_product_ids:
            search_query |= Q(product_id__in=matched_product_ids)
        
        # Also search business names
        search_query |= Q(business__name__icontains=query)
        
        # If no products matched, fall back to basic text search
        if not matched_product_ids:
            search_query |= Q(product__name__icontains=query)
        
        qs = qs.filter(search_query)
    
    # Apply sorting
    if sort == 'price_asc':
        qs = qs.order_by('price', '-observed_at')
    elif sort == 'price_desc':
        qs = qs.order_by('-price', '-observed_at')
    elif sort == 'nearest' and user_lat and user_lng:
        try:
            user_lat = float(user_lat)
            user_lng = float(user_lng)
            qs = annotate_with_distance(qs, user_lat, user_lng)
        except (ValueError, TypeError):
            qs = qs.order_by('-observed_at')
    else:
        qs = qs.order_by('-updated_at', '-observed_at')
        
    return qs, sort, user_lat, user_lng

def _get_business_queryset(request):
    """Helper to get businesses matching search query."""
    query = request.GET.get('q', '').strip()
    
    if query:
        # Enhanced business search
        businesses = set(Business.objects.filter(name__icontains=query))
        
        # Also return businesses that have products matching the search
        if query:
            # Find products matching the query (using same logic as price search)
            matched_product_ids = _get_matched_product_ids(query)
            
            # Get businesses that have price reports for these products
            if matched_product_ids:
                businesses_with_matched_products = set(Business.objects.filter(
                    price_reports__product_id__in=matched_product_ids
                ).distinct())
                
                # Combine and deduplicate
                businesses = businesses.union(businesses_with_matched_products)
        
        # Convert back to queryset and order
        business_ids = [b.id for b in businesses]
        return Business.objects.filter(id__in=business_ids).annotate(
            avg_rating=Avg('ratings__rating'),
            rating_count=Count('ratings')
        ).order_by('name')
    
    return Business.objects.none().annotate(
        avg_rating=Avg('ratings__rating'),
        rating_count=Count('ratings')
    )

def home(request):
    query = request.GET.get('q', '').strip()
    sort = request.GET.get('sort', 'recent')
    user_lat = request.GET.get('lat')
    user_lng = request.GET.get('lng')
    
    # Get price reports
    latest_prices, sort, user_lat, user_lng = _get_prices_queryset(request)
    latest_prices = latest_prices[:20]
    if request.user.is_authenticated:
        liked_ids = set(PriceLike.objects.filter(user=request.user, price_report__in=latest_prices).values_list('price_report_id', flat=True))
        for report in latest_prices:
            report.is_liked_by_user = report.id in liked_ids
    
    # Get businesses if there's a search query
    businesses = []
    if query:
        businesses = _get_business_queryset(request)[:10]  # Limit to 10 businesses
    
    # Get cheapest recent fuel prices
    fuel_keywords = ['petrol', 'diesel', 'zoom']
    fuel_summary = []
    thirty_days_ago = timezone.now() - timedelta(days=30)
    
    for keyword in fuel_keywords:
        cheapest_report = PriceReport.objects.filter(
            product__name__icontains=keyword,
            observed_at__gte=thirty_days_ago
        ).select_related('product', 'business', 'business_branch').order_by('price', '-observed_at').first()
        
        if cheapest_report:
            fuel_summary.append({
                'type': keyword.capitalize(),
                'report': cheapest_report
            })
    
    return render(request, 'home.html', {
        'latest_prices': latest_prices,
        'businesses': businesses,
        'current_sort': sort,
        'search_query': query,
        'fuel_summary': fuel_summary,
    })

def about_view(request):
    return render(request, 'about.html')

def how_to_use_view(request):
    return render(request, 'how_to_use.html')

@cache_page(60 * 5)
def api_map_prices(request):
    """Stateless JSON endpoint specifically for the map frontend."""
    latest_prices, sort, user_lat, user_lng = _get_prices_queryset(request)
    
    # Require coords, limit to 150 points for browser performance
    latest_prices = latest_prices.filter(latitude__isnull=False, longitude__isnull=False)[:150]
    
    from django.urls import reverse
    import math
    
    items_data = []
    for p in latest_prices:
        # Check against pure math.isnan or db issues
        if p.latitude is None or p.longitude is None:
            continue
        # Use proper formatting cleanly isolating python dict
        items_data.append({
            'lat': float(p.latitude),
            'lng': float(p.longitude),
            'product': p.product.name,
            'price': f"{p.currency} {p.price:,.2f}",
            'rawPrice': float(p.price),
            'business': p.business.name if p.business else '',
            'date': p.observed_at.strftime('%b %d, %Y'),
            'url': reverse('price_detail', args=[p.id]),
        })
        
    return JsonResponse({'items': items_data})

def load_more_prices(request):
    page = request.GET.get('page', 1)
    query = request.GET.get('q', '').strip()
    sort = request.GET.get('sort', 'recent')
    user_lat = request.GET.get('lat')
    user_lng = request.GET.get('lng')
    
    latest_prices, sort, user_lat, user_lng = _get_prices_queryset(request)
    
    # Use paginator for infinite scroll
    paginator = Paginator(latest_prices, 20)
    
    try:
        prices_page = paginator.page(page)
    except PageNotAnInteger:
        return JsonResponse({'error': 'Invalid page number.'}, status=400)
    except EmptyPage:
        return JsonResponse({'has_more': False})
    
    liked_ids = set()
    user_ratings = {}
    if request.user.is_authenticated:
        page_price_ids = [price.id for price in prices_page.object_list]
        liked_ids = set(PriceLike.objects.filter(
            user=request.user,
            price_report_id__in=page_price_ids,
        ).values_list('price_report_id', flat=True))
        user_ratings = dict(PriceReportRating.objects.filter(
            user=request.user,
            price_report_id__in=page_price_ids,
        ).values_list('price_report_id', 'rating'))

    # Render the same card partial used by the initial home feed so infinite-scroll
    # results stay in lockstep with data attributes, quick-rating controls, and
    # rating summaries.
    items_data = []
    for price in prices_page:
        price.is_liked_by_user = price.id in liked_ids
        items_data.append(render_to_string(
            'partials/_price_report_card.html',
            {
                'report': price,
                'show_like_button': True,
                'price_card_current_user_rating': user_ratings.get(price.id),
                'default_profile_picture_url': static('img/default-profile.svg'),
            },
            request=request,
        ))
    
    response_data = {
        'items': items_data,
        'has_more': prices_page.has_next(),
        'current_page': prices_page.number,
        'total_pages': paginator.num_pages
    }
    
    # Add business results for page 1 searches
    if prices_page.number == 1 and query:
        businesses = _get_business_queryset(request)[:10]
        businesses_data = []
        for business in businesses:
            businesses_data.append({
                'id': business.id,
                'name': business.name,
                'image_url': business.image.url if business.image else static('img/default-business.svg'),
                'price_reports_count': business.price_reports.count(),
                'avg_rating': float(business.avg_rating) if business.avg_rating is not None else None,
                'rating_count': business.rating_count,
            })
        response_data['businesses'] = businesses_data
    
    return JsonResponse(response_data)

class PriceReportDetailView(DetailView):
    model = PriceReport
    template_name = 'price_report_detail.html'
    context_object_name = 'report'

    def get_queryset(self):
        return PriceReport.objects.select_related(
            'product',
            'business',
            'business_branch',
            'user',
            'user__profile',
            'last_edited_by',
        ).prefetch_related('likes')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from .utils import get_nearby_prices
        report = self.get_object()

        price_analysis = None
        try:
            alias_names = list(ProductAlias.objects.filter(
                canonical_product=report.product
            ).values_list('alias_name', flat=True))

            name_variants = set([report.product.name])
            for n in alias_names:
                if n:
                    name_variants.add(n)

            variant_products_qs = Product.objects.filter(name__in=list(name_variants))
            if report.product_id:
                variant_products_qs = variant_products_qs | Product.objects.filter(id=report.product_id)

            variant_product_ids = list(variant_products_qs.values_list('id', flat=True).distinct())

            reports_qs = PriceReport.objects.filter(
                product_id__in=variant_product_ids,
                currency=report.currency,
                price__isnull=False,
            ).order_by('-observed_at')

            total_count = reports_qs.count()
            if total_count > 1:
                agg = reports_qs.aggregate(
                    min_price=Min('price'),
                    max_price=Max('price'),
                    avg_price=Avg('price'),
                )

                last_two = list(reports_qs.values_list('price', flat=True)[:2])
                latest_price = float(last_two[0]) if len(last_two) >= 1 else None
                previous_price = float(last_two[1]) if len(last_two) >= 2 else None

                change_value = None
                change_pct = None
                if latest_price is not None and previous_price not in (None, 0):
                    change_value = latest_price - previous_price
                    change_pct = (change_value / previous_price) * 100

                now = timezone.now()
                week_ago = now - timedelta(days=7)
                two_weeks_ago = now - timedelta(days=14)

                current_week_avg = reports_qs.filter(observed_at__gte=week_ago).aggregate(a=Avg('price'))['a']
                prev_week_avg = reports_qs.filter(observed_at__gte=two_weeks_ago, observed_at__lt=week_ago).aggregate(a=Avg('price'))['a']

                trend = None
                if current_week_avg is not None and prev_week_avg not in (None, 0):
                    diff = float(current_week_avg) - float(prev_week_avg)
                    pct = (diff / float(prev_week_avg)) * 100
                    trend = {
                        'direction': 'up' if diff > 0 else 'down' if diff < 0 else 'flat',
                        'diff': diff,
                        'pct': pct,
                        'current_week_avg': float(current_week_avg),
                        'prev_week_avg': float(prev_week_avg),
                    }

                price_analysis = {
                    'currency': report.currency,
                    'count': total_count,
                    'min_price': float(agg['min_price']) if agg['min_price'] is not None else None,
                    'max_price': float(agg['max_price']) if agg['max_price'] is not None else None,
                    'avg_price': float(agg['avg_price']) if agg['avg_price'] is not None else None,
                    'latest_price': latest_price,
                    'previous_price': previous_price,
                    'change_value': change_value,
                    'change_pct': change_pct,
                    'trend_7d': trend,
                }
        except Exception:
            price_analysis = None

        rating_summary = report.ratings.aggregate(
            average_rating=Avg('rating'),
            rating_count=Count('id'),
        )
        context['average_rating'] = rating_summary['average_rating']
        context['rating_count'] = rating_summary['rating_count']
        context['current_user_rating'] = None

        context['price_analysis'] = price_analysis
        context['price'] = report
        
        # Keep same-product nearby prices off this detail page; they now live on
        # the dedicated product detail page. Show different products reported in
        # the same vicinity here instead.
        if report.latitude and report.longitude and report.h3_res9:
            other_nearby = PriceReport.objects.filter(
                h3_res9=report.h3_res9,
            ).exclude(id=report.id).exclude(product=report.product).select_related(
                'product', 'business', 'business_branch', 'user'
            ).prefetch_related('product__tags', 'likes').annotate(
                average_rating=Avg('ratings__rating'),
                rating_count=Count('ratings'),
            ).order_by('-observed_at')[:6]
            context['other_nearby_products'] = other_nearby
        else:
            context['other_nearby_products'] = None
            
        if self.request.user.is_authenticated:
            context['is_watching'] = ProductWatchlist.objects.filter(
                user=self.request.user,
                product=report.product
            ).exists()
            context['is_liked'] = PriceLike.objects.filter(user=self.request.user, price_report=report).exists()
            context['current_user_rating'] = PriceReportRating.objects.filter(
                user=self.request.user,
                price_report=report,
            ).values_list('rating', flat=True).first()
            # Deletion permission context
            if report.marked_for_deletion:
                context['can_vote_delete'] = report.can_vote_delete(self.request.user)
                context['can_delete'] = report.can_delete(self.request.user)
            else:
                context['can_vote_delete'] = False
                context['can_delete'] = False
        else:
            context['is_watching'] = False
            context['is_liked'] = False
            context['can_vote_delete'] = False
            context['can_delete'] = False
        context['comments'] = report.comments.filter(parent__isnull=True).select_related('user').prefetch_related('replies__user')
        context['comment_content_type_id'] = ContentType.objects.get_for_model(report).id
        context['photos'] = report.photos.all()

        if report.business_branch and report.business_branch.address:
            context['branch_address'] = report.business_branch.address
        else:
            context['branch_address'] = None

        if report.latitude is not None and report.longitude is not None:
            context['directions_url'] = (
                f'https://www.google.com/maps/dir/?api=1&destination={report.latitude},{report.longitude}'
            )
        else:
            context['directions_url'] = None

        from urllib.parse import urlencode
        add_price_params = {'product_name': report.product.name}
        if report.business:
            add_price_params['business_name'] = report.business.name
        context['add_price_query'] = urlencode(add_price_params)

        return context

price_report_detail = PriceReportDetailView.as_view()

class BusinessDetailView(DetailView):
    model = Business
    template_name = 'business_detail.html'
    context_object_name = 'business'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        business = self.get_object()
        
        # Get all price reports for this business with location data
        price_reports = PriceReport.objects.filter(
            business=business
        ).select_related('product', 'user').prefetch_related('product__tags').annotate(
            average_rating=Avg('ratings__rating'),
            rating_count=Count('ratings'),
        ).order_by('-observed_at')
        
        # Filter reports with valid coordinates for the map
        reports_with_location = price_reports.filter(
            latitude__isnull=False,
            longitude__isnull=False
        )
        
        # Get unique products for this business with their latest prices
        products_data = []
        for product in Product.objects.filter(
            price_reports__business=business
        ).distinct().order_by('name'):
            latest_price = product.price_reports.filter(business=business).select_related(
                'product', 'business', 'user'
            ).prefetch_related('user__profile', 'product__tags').annotate(
                average_rating=Avg('ratings__rating'),
                rating_count=Count('ratings'),
            ).first()
            products_data.append({
                'product': product,
                'latest_price': latest_price
            })
        
        context['price_reports'] = price_reports
        context['reports_with_location'] = reports_with_location
        context['products_data'] = products_data
        context['total_reports'] = price_reports.count()
        rating_summary = business.ratings.aggregate(
            average_rating=Avg('rating'),
            rating_count=Count('id'),
        )
        context['average_rating'] = rating_summary['average_rating']
        context['rating_count'] = rating_summary['rating_count']
        context['current_user_rating'] = None
        if self.request.user.is_authenticated:
            context['current_user_rating'] = BusinessRating.objects.filter(
                user=self.request.user,
                business=business,
            ).values_list('rating', flat=True).first()
        context['reports_with_location_count'] = reports_with_location.count()
        context['comments'] = business.comments.filter(parent__isnull=True).select_related('user').prefetch_related('replies__user')
        context['comment_content_type_id'] = ContentType.objects.get_for_model(business).id
        
        return context

business_detail = BusinessDetailView.as_view()

class BusinessEditView(UpdateView):
    model = Business
    form_class = BusinessForm
    template_name = 'business_edit.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['products'] = Product.objects.all().order_by('name')
        return context
    
    def get_success_url(self):
        return reverse_lazy('business_detail', kwargs={'pk': self.object.pk})
    
    def form_valid(self, form):
        clear_image = self.request.POST.get('clear_image')
        if clear_image in ('1', 'true', 'True', 'on') and 'image' not in self.request.FILES:
            if self.object.image:
                self.object.image.delete(save=False)
            form.instance.image = None

        messages.success(self.request, 'Business updated successfully!')
        return super().form_valid(form)

business_edit = BusinessEditView.as_view()

class NearbyPricesDetailView(DetailView):
    model = PriceReport
    template_name = 'nearby_prices_detail.html'
    context_object_name = 'reference_report'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        reference_report = self.get_object()
        
        # Get nearby prices using the existing utility function
        from .utils import get_nearby_prices
        nearby_prices = get_nearby_prices(
            product=reference_report.product,
            lat=reference_report.latitude,
            lng=reference_report.longitude,
            radius_hexes=3  # Larger radius for detail view
        ).exclude(id=reference_report.id).select_related('product', 'business', 'user').prefetch_related('product__tags')
        
        # Filter reports with valid coordinates for the map
        reports_with_location = nearby_prices.filter(
            latitude__isnull=False,
            longitude__isnull=False
        )
        
        context['nearby_prices'] = nearby_prices
        context['reports_with_location'] = reports_with_location
        context['total_nearby'] = nearby_prices.count()
        context['reports_with_location_count'] = reports_with_location.count()
        
        return context

nearby_prices_detail = NearbyPricesDetailView.as_view()

class PriceReportEditView(UpdateView):
    model = PriceReport
    form_class = PriceReportForm
    template_name = 'price_report_edit.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['products'] = Product.objects.all().order_by('name')
        context['businesses'] = Business.objects.all().order_by('name')
        context['photos'] = self.object.photos.all()
        return context
    
    def form_valid(self, form):
        # Store old values for history
        old_price = self.get_object().price
        old_currency = self.get_object().currency
        
        # Update last_edited_by
        if self.request.user.is_authenticated:
            form.instance.last_edited_by = self.request.user
        
        # Save the form
        response = super().form_valid(form)
        
        # Create history record if price or currency changed
        if old_price != form.instance.price or old_currency != form.instance.currency:
            PriceHistory.objects.create(
                price_report=self.get_object(),
                old_price=old_price,
                new_price=form.instance.price,
                old_currency=old_currency,
                new_currency=form.instance.currency,
                changed_by=self.request.user if self.request.user.is_authenticated else None,
                notes=f"Price updated from {old_price} {old_currency} to {form.instance.price} {form.instance.currency}"
            )
        
        messages.success(self.request, 'Price report updated successfully!')
        return response

@login_required
def edit_price_report(request, pk):
    report = get_object_or_404(PriceReport, pk=pk)
    
    if request.method == 'POST':
        form = PriceReportForm(request.POST, request.FILES, instance=report)
        if form.is_valid():
            # Store old values from the database because ModelForm validation mutates the instance.
            old_report = PriceReport.objects.get(pk=report.pk)
            old_price = old_report.price
            old_currency = old_report.currency
            
            # Save the form but don't commit yet
            form.instance.last_edited_by = request.user
            updated_report = form.save()
            
            # Handle product updates
            product_name = request.POST.get('product_name', '').strip()
            if product_name and product_name.lower() != report.product.name.lower():
                product = Product.objects.filter(name__iexact=product_name).first()
                if not product:
                    from django.utils.text import slugify
                    product_slug = slugify(product_name)
                    original_slug = product_slug
                    counter = 1
                    while Product.objects.filter(slug=product_slug).exists():
                        product_slug = f"{original_slug}-{counter}"
                        counter += 1
                    product = Product.objects.create(
                        name=product_name,
                        slug=product_slug,
                        created_by=request.user
                    )
                updated_report.product = product

            # Handle business updates
            business_name = request.POST.get('business_name', '').strip()
            if business_name:
                if not updated_report.business or business_name.lower() != updated_report.business.name.lower():
                    business = Business.objects.filter(name__iexact=business_name).first()
                    if not business:
                        from django.utils.text import slugify
                        business_slug = slugify(business_name)
                        original_slug = business_slug
                        counter = 1
                        while Business.objects.filter(slug=business_slug).exists():
                            business_slug = f"{original_slug}-{counter}"
                            counter += 1
                        business = Business.objects.create(
                            name=business_name,
                            slug=business_slug
                        )
                    updated_report.business = business
            elif 'business_name' in request.POST:
                # If the field is submitted but empty, the user wants to remove the business
                updated_report.business = None
            
            # Handle multiple photo uploads
            from .models import PriceReportPhoto

            # Handle specific photo replacements
            for photo in updated_report.photos.all():
                file_key = f'update_photo_{photo.id}'
                if file_key in request.FILES:
                    photo.image = request.FILES[file_key]
                    photo.save()
            
            photos_files = request.FILES.getlist('photos')
            if photos_files:
                current_count = updated_report.photos.count()
                max_photos = 5
                available_slots = max_photos - current_count
                photos_to_add = photos_files[:available_slots]

                for i, photo_file in enumerate(photos_to_add):
                    PriceReportPhoto.objects.create(
                        price_report=updated_report,
                        image=photo_file,
                        order=current_count + i
                    )

                # Apply first photo to product/business if they don't have one
                if photos_to_add and not updated_report.product.image:
                    updated_report.product.image = photos_to_add[0]
                    updated_report.product.save()
                if photos_to_add and updated_report.business and not updated_report.business.image:
                    updated_report.business.image = photos_to_add[0]
                    updated_report.business.save()

            # Handle photo deletions
            delete_photo_ids = request.POST.getlist('delete_photos')
            if delete_photo_ids:
                PriceReportPhoto.objects.filter(
                    id__in=delete_photo_ids,
                    price_report=updated_report
                ).delete()

            # Handle legacy single image field (for backward compatibility)
            clear_image = request.POST.get('clear_image')
            if clear_image in ('1', 'true', 'True', 'on'):
                if updated_report.image:
                    updated_report.image.delete(save=False)
                updated_report.image = None

            if 'image' in request.FILES:
                updated_report.image = request.FILES['image']

                # Optionally update product or business if they don't have an image
                if not updated_report.product.image:
                    updated_report.product.image = updated_report.image
                    updated_report.product.save()
                if updated_report.business and not updated_report.business.image:
                    updated_report.business.image = updated_report.image
                    updated_report.business.save()
            
            # Handle location updates from form
            lat = request.POST.get('latitude')
            lng = request.POST.get('longitude')
            
            if lat and lng:
                try:
                    updated_report.latitude = float(lat)
                    updated_report.longitude = float(lng)
                except ValueError:
                    messages.warning(request, 'Invalid coordinates provided. Location not updated.')
            elif lat == '' or lng == '':
                # Clear location if both fields are empty
                updated_report.latitude = None
                updated_report.longitude = None
            
            # Save all updates
            updated_report.save()
            
            # Handle tags
            tags_string = request.POST.get('tags', '').strip()
            if tags_string:
                # Clear existing tags
                updated_report.product.tags.clear()
                # Add new tags
                tag_list = [tag.strip() for tag in tags_string.split(',') if tag.strip()]
                if tag_list:
                    updated_report.product.tags.add(*tag_list)
            
            # Create history record if price changed
            if old_price != updated_report.price or old_currency != updated_report.currency:
                PriceHistory.objects.create(
                    price_report=updated_report,
                    old_price=old_price,
                    new_price=updated_report.price,
                    old_currency=old_currency,
                    new_currency=updated_report.currency,
                    changed_by=request.user,
                    notes=f"Price updated from {old_price} {old_currency} to {updated_report.price} {updated_report.currency}"
                )
            
            messages.success(request, 'Price report updated successfully!')
            return redirect('price_detail', pk=updated_report.pk)
        else:
            # Form is invalid, continue with the form containing errors
            products = Product.objects.all().order_by('name')
            businesses = Business.objects.all().order_by('name')
            return render(request, 'price_report_edit.html', {
                'form': form,
                'report': report,
                'products': products,
                'businesses': businesses,
                'photos': report.photos.all()
            })
    else:
        # GET request - create form with existing report data
        form = PriceReportForm(instance=report)
        products = Product.objects.all().order_by('name')
        businesses = Business.objects.all().order_by('name')
        return render(request, 'price_report_edit.html', {
            'form': form,
            'report': report,
            'products': products,
            'businesses': businesses,
            'photos': report.photos.all()
        })

@login_required
@require_POST
def toggle_watchlist(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    watch, created = ProductWatchlist.objects.get_or_create(user=request.user, product=product)

    if not created:
        # User is already watching, so unwatch
        watch.delete()
        watching = False
    else:
        watching = True

    return JsonResponse({'watching': watching})

@login_required
def notifications_view(request):
    notifications = request.user.notifications.all()
    # Mark as read after fetching them
    unread_count = notifications.filter(is_read=False).count()
    notifications.filter(is_read=False).update(is_read=True)
    return render(request, 'notifications.html', {'notifications': notifications, 'unread_count': unread_count})


@login_required
@require_POST
def toggle_price_like(request, pk):
    report = get_object_or_404(PriceReport, pk=pk)
    like, created = PriceLike.objects.get_or_create(user=request.user, price_report=report)
    liked = created
    if not created:
        like.delete()
        liked = False

    likes_count = report.likes.count()
    if liked and request.user != report.user and likes_count in PriceLike.LIKE_NOTIFICATION_THRESHOLDS:
        create_like_threshold_notification(report, likes_count)
    return JsonResponse({'liked': liked, 'likes_count': likes_count})


@login_required
@require_POST
def rate_price_report(request, pk):
    report = get_object_or_404(PriceReport, pk=pk)
    rating = _rating_from_request(request)
    if rating is None:
        return JsonResponse({'ok': False, 'error': 'Rating must be an integer from 1 to 5.'}, status=400)

    PriceReportRating.objects.update_or_create(
        user=request.user,
        price_report=report,
        defaults={'rating': rating},
    )
    summary = _rating_summary(report.ratings)
    return JsonResponse({
        'ok': True,
        'rating': rating,
        'average_rating': summary['average_rating'],
        'rating_count': summary['rating_count'],
    })


@login_required
@require_POST
def vote_duplicate_report(request, pk):
    report = get_object_or_404(PriceReport, pk=pk, duplicated_from__isnull=False)
    vote = request.POST.get('vote')
    if vote == 'trust':
        report.duplicate_verify_votes.remove(request.user)
        report.duplicate_trust_votes.add(request.user)
        messages.success(request, 'Thanks — your trust vote was recorded.')
    elif vote == 'verify':
        report.duplicate_trust_votes.remove(request.user)
        report.duplicate_verify_votes.add(request.user)
        messages.success(request, 'Thanks — your verification request was recorded.')
    else:
        messages.error(request, 'Choose whether you trust or want to verify this duplicate report.')
    return redirect('price_detail', pk=report.pk)


@login_required
@require_POST
def rate_business(request, pk):
    business = get_object_or_404(Business, pk=pk)
    rating = _rating_from_request(request)
    if rating is None:
        return JsonResponse({'ok': False, 'error': 'Rating must be an integer from 1 to 5.'}, status=400)

    BusinessRating.objects.update_or_create(
        user=request.user,
        business=business,
        defaults={'rating': rating},
    )
    summary = _rating_summary(business.ratings)
    return JsonResponse({
        'ok': True,
        'rating': rating,
        'average_rating': summary['average_rating'],
        'rating_count': summary['rating_count'],
    })


@login_required
@require_POST
def mute_notification(request, pk):
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    notification.muted = True
    notification.save(update_fields=['muted'])
    return JsonResponse({'status': 'ok'})

@login_required
def shopping_lists_view(request):
    # Get or create a default list for the user if they don't have one
    lists = request.user.shopping_lists.all()
    if not lists.exists():
        ShoppingList.objects.create(user=request.user, name="My Shopping List")
        lists = request.user.shopping_lists.all()
    
    active_list = lists.first()
    items = active_list.items.all() if active_list else []
    
    # Calculate estimated total 
    estimated_total = 0
    currency = "PGK" # Default
    
    for item in items:
        if item.product:
            latest_price = item.product.price_reports.order_by('-observed_at').first()
            if latest_price:
                item.estimated_price = latest_price.price
                item.currency = latest_price.currency
                currency = item.currency # Pick up the first currency we see
                if not item.is_checked:
                    estimated_total += latest_price.price * item.quantity
    
    return render(request, 'shopping_list.html', {
        'shopping_lists': lists,
        'active_list': active_list,
        'items': items,
        'estimated_total': estimated_total,
        'currency': currency
    })

@login_required
@require_POST
def add_to_shopping_list(request):
    import json
    data = json.loads(request.body)
    product_id = data.get('product_id')
    item_name = data.get('item_name', '').strip()
    
    shopping_list = request.user.shopping_lists.first()
    if not shopping_list:
        shopping_list = ShoppingList.objects.create(user=request.user, name="My Shopping List")
        
    if product_id:
        product = get_object_or_404(Product, pk=product_id)
        # check if item already exists
        item, created = ShoppingListItem.objects.get_or_create(shopping_list=shopping_list, product=product)
        if not created:
            item.quantity += 1
            item.save()
        return JsonResponse({'status': 'added', 'item_name': product.name})
    elif item_name:
        ShoppingListItem.objects.create(shopping_list=shopping_list, item_name=item_name)
        return JsonResponse({'status': 'added', 'item_name': item_name})
        
    return JsonResponse({'status': 'error', 'message': 'Invalid input'}, status=400)

@login_required
@require_POST
def toggle_shopping_item(request, item_id):
    item = get_object_or_404(ShoppingListItem, pk=item_id, shopping_list__user=request.user)
    item.is_checked = not item.is_checked
    item.save()
    return JsonResponse({'status': 'success', 'is_checked': item.is_checked})

@login_required
@require_POST
def delete_shopping_item(request, item_id):
    item = get_object_or_404(ShoppingListItem, pk=item_id, shopping_list__user=request.user)
    item.delete()
    return JsonResponse({'status': 'deleted'})


# Deletion request views
@login_required
@require_POST
def mark_for_deletion(request, pk):
    """Mark a price report for deletion with a reason"""
    report = get_object_or_404(PriceReport, pk=pk)
    reason = request.POST.get('reason', '').strip()
    
    report.marked_for_deletion = True
    report.marked_for_deletion_by = request.user
    report.marked_for_deletion_at = timezone.now()
    report.deletion_reason = reason
    report.save()
    recipients = User.objects.exclude(pk=request.user.pk).exclude(pk=report.user_id)
    for recipient in recipients:
        if hasattr(recipient, 'profile') and recipient.profile.deletion_notifications_enabled:
            Notification.objects.create(
                user=recipient,
                product=report.product,
                price_report=report,
                notification_type=Notification.TYPE_DELETION_MARK,
                message=f"{request.user.username} marked a price report for deletion: {report.product.name}."
            )
    
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'ok': True,
            'marked_for_deletion': True,
            'reason': reason,
            'message': 'Price report marked for deletion. Another user must confirm to delete it.',
        })

    messages.success(request, 'Price report marked for deletion. Another user must confirm to delete it.')
    return redirect('price_detail', pk=pk)


@login_required
@require_POST
def add_comment(request):
    data = json.loads(request.body)
    target = data.get('target')
    target_id = data.get('target_id')
    body = (data.get('body') or '').strip()
    parent_id = data.get('parent_id')
    if not body or len(body) > 1200:
        return JsonResponse({'status': 'error'}, status=400)

    comment = Comment(user=request.user, body=body)
    if target == 'price':
        target_obj = get_object_or_404(PriceReport, pk=target_id)
    elif target == 'business':
        target_obj = get_object_or_404(Business, pk=target_id)
    else:
        return JsonResponse({'status': 'error'}, status=400)

    comment.content_type = ContentType.objects.get_for_model(target_obj.__class__)
    comment.object_id = target_obj.id

    if parent_id:
        parent = get_object_or_404(Comment, pk=parent_id)
        if parent.parent_id:
            return JsonResponse({'status': 'error', 'message': 'Maximum nesting depth is 1'}, status=400)
        if parent.content_type_id != comment.content_type_id or parent.object_id != comment.object_id:
            return JsonResponse({'status': 'error', 'message': 'Parent mismatch'}, status=400)
        comment.parent = parent
    comment.save()
    return JsonResponse({'status': 'ok', 'id': comment.id, 'body': comment.body, 'username': comment.user.username})

@login_required
@require_POST
def unmark_for_deletion(request, pk):
    """Unmark a price report from deletion (only by the marker or admin)"""
    report = get_object_or_404(PriceReport, pk=pk)
    
    if request.user != report.marked_for_deletion_by and not request.user.is_staff and not request.user.is_superuser:
        messages.error(request, 'You can only unmark deletion requests you created.')
        return redirect('price_detail', pk=pk)
    
    report.marked_for_deletion = False
    report.marked_for_deletion_by = None
    report.marked_for_deletion_at = None
    report.deletion_reason = ''
    report.deletion_votes.clear()
    report.save()
    
    messages.success(request, 'Deletion request cancelled.')
    return redirect('price_detail', pk=pk)

@login_required
@require_POST
def vote_delete_price(request, pk):
    """Vote to delete a marked price report"""
    report = get_object_or_404(PriceReport, pk=pk)
    
    if not report.marked_for_deletion:
        messages.error(request, 'This price report is not marked for deletion.')
        return redirect('price_detail', pk=pk)
    
    if request.user == report.marked_for_deletion_by:
        messages.error(request, 'You cannot vote on your own deletion request.')
        return redirect('price_detail', pk=pk)
    
    if report.deletion_votes.filter(pk=request.user.pk).exists():
        messages.error(request, 'You have already voted to delete this report.')
        return redirect('price_detail', pk=pk)
    
    report.deletion_votes.add(request.user)
    messages.success(request, 'Your vote to delete has been recorded. An admin or staff member can now delete this report.')
    return redirect('price_detail', pk=pk)

@login_required
@require_POST
def delete_price_report(request, pk):
    """Actually delete the price report (admin/staff or after votes)"""
    report = get_object_or_404(PriceReport, pk=pk)
    
    # Check if user can delete
    if not report.can_delete(request.user):
        messages.error(request, 'You do not have permission to delete this report.')
        return redirect('price_detail', pk=pk)
    
    report.delete()
    messages.success(request, 'Price report has been deleted.')
    return redirect('home')


# ── Bulk CSV Upload ──────────────────────────────────────────────────────────

import csv
import io
import re
from decimal import Decimal, InvalidOperation
from django.http import HttpResponse
from django.db import transaction
from django.utils.text import slugify

# Security constants
BULK_MAX_FILE_SIZE = 2 * 1024 * 1024  # 2 MB
BULK_MAX_ROWS = 500
BULK_ALLOWED_EXTENSIONS = {'.csv'}
BULK_ALLOWED_MIMES = {'text/csv', 'text/plain', 'application/csv', 'application/vnd.ms-excel'}


def _sanitize_cell(value):
    """
    Prevent CSV formula injection.
    Strips leading characters that spreadsheet apps interpret as formulas.
    """
    if not value:
        return value
    value = value.strip()
    # Strip leading formula-trigger characters
    while value and value[0] in ('=', '+', '-', '@', '\t', '\r'):
        value = value[1:].strip()
    return value


def _validate_csv_file(uploaded_file):
    """Validate the uploaded file for security. Returns (is_valid, error_message)."""
    import os
    
    # 1. Check file size
    if uploaded_file.size > BULK_MAX_FILE_SIZE:
        return False, f'File too large. Maximum allowed size is {BULK_MAX_FILE_SIZE // (1024*1024)}MB.'
    
    # 2. Check file extension
    _, ext = os.path.splitext(uploaded_file.name)
    if ext.lower() not in BULK_ALLOWED_EXTENSIONS:
        return False, f'Invalid file type "{ext}". Only .csv files are allowed.'
    
    # 3. Check MIME type
    if uploaded_file.content_type not in BULK_ALLOWED_MIMES:
        return False, f'Invalid content type "{uploaded_file.content_type}". Only CSV files are allowed.'
    
    return True, None


def _parse_csv(uploaded_file):
    """
    Parse the CSV file in-memory. Returns (rows, errors).
    The file is never saved to disk.
    """
    try:
        raw = uploaded_file.read()
        # Try UTF-8 first, fall back to latin-1
        try:
            text = raw.decode('utf-8-sig')  # handles BOM
        except UnicodeDecodeError:
            try:
                text = raw.decode('latin-1')
            except UnicodeDecodeError:
                return [], [{'row': 0, 'error': 'File encoding not supported. Please save as UTF-8.'}]
    except Exception:
        return [], [{'row': 0, 'error': 'Could not read file.'}]
    
    reader = csv.DictReader(io.StringIO(text))
    
    # Validate headers
    required_headers = {'product_name', 'price'}
    if not reader.fieldnames:
        return [], [{'row': 0, 'error': 'CSV file appears to be empty or has no headers.'}]
    
    actual_headers = {h.strip().lower() for h in reader.fieldnames if h}
    missing = required_headers - actual_headers
    if missing:
        return [], [{'row': 0, 'error': f'Missing required columns: {", ".join(missing)}. Required: product_name, price'}]
    
    rows = []
    errors = []
    
    for i, raw_row in enumerate(reader, start=2):  # start=2 because row 1 is header
        if i - 1 > BULK_MAX_ROWS:
            errors.append({'row': i, 'error': f'Maximum {BULK_MAX_ROWS} rows allowed. Remaining rows skipped.'})
            break
        
        # Normalize keys and sanitize values
        row = {}
        for key, val in raw_row.items():
            if key:
                row[key.strip().lower()] = _sanitize_cell(val or '')
        
        # Skip completely empty rows
        if not any(row.values()):
            continue
        
        # Validate required fields
        product_name = row.get('product_name', '').strip()
        price_str = row.get('price', '').strip()
        
        if not product_name:
            errors.append({'row': i, 'error': 'Missing product name.'})
            continue
        
        if len(product_name) > 255:
            errors.append({'row': i, 'error': f'Product name too long (max 255 chars): "{product_name[:30]}..."'})
            continue
        
        if not price_str:
            errors.append({'row': i, 'error': f'Missing price for "{product_name}".'})
            continue
        
        # Clean price (remove currency symbols, commas, spaces)
        price_str = re.sub(r'[^\d.]', '', price_str)
        
        try:
            price = Decimal(price_str)
            if price <= 0:
                errors.append({'row': i, 'error': f'Price must be positive for "{product_name}".'})
                continue
            if price > 9999999999:
                errors.append({'row': i, 'error': f'Price too large for "{product_name}".'})
                continue
        except (InvalidOperation, ValueError):
            errors.append({'row': i, 'error': f'Invalid price "{row.get("price", "")}" for "{product_name}".'})
            continue
        
        # Validate currency
        currency = row.get('currency', '').strip().upper()
        if currency and (len(currency) != 3 or not currency.isalpha()):
            errors.append({'row': i, 'error': f'Invalid currency "{currency}" for "{product_name}". Use a 3-letter code like PGK.'})
            continue
        if not currency:
            currency = 'PGK'
        
        # Validate notes length
        notes = row.get('notes', '').strip()
        if len(notes) > 1000:
            notes = notes[:1000]
        
        # Tags
        tags = row.get('tags', '').strip()
        
        rows.append({
            'row_num': i,
            'product_name': product_name,
            'price': price,
            'currency': currency,
            'notes': notes,
            'tags': tags,
        })
    
    return rows, errors


@login_required
def bulk_upload(request):
    """Handle bulk CSV upload with preview and confirmation."""
    
    context = {
        'products': Product.objects.all().order_by('name'),
        'businesses': Business.objects.all().order_by('name'),
    }
    
    if request.method == 'POST':
        action = request.POST.get('action', '')
        
        # Fallback for existing tests that don't send 'action' explicitly
        if not action and request.FILES.get('csv_file'):
            action = 'preview'
        
        if action == 'preview':
            # Step 1: Parse and validate the CSV
            csv_file = request.FILES.get('csv_file')
            if not csv_file:
                messages.error(request, 'Please select a CSV file to upload.')
                return render(request, 'bulk_upload.html', context)
            
            # Require business name
            business_name = request.POST.get('business_name', '').strip()
            if not business_name:
                messages.error(request, 'Business / Store Name is required.')
                return render(request, 'bulk_upload.html', context)
            
            # Security validation
            is_valid, error_msg = _validate_csv_file(csv_file)
            if not is_valid:
                messages.error(request, error_msg)
                return render(request, 'bulk_upload.html', context)
            
            rows, errors = _parse_csv(csv_file)
            
            if not rows and errors:
                for err in errors:
                    messages.error(request, f"Row {err['row']}: {err['error']}")
                return render(request, 'bulk_upload.html', context)
            
            # Store parsed data in session for confirmation step
            # Convert Decimal to string for JSON serialization
            session_rows = []
            for row in rows:
                session_rows.append({
                    **row,
                    'price': str(row['price']),
                })
            
            request.session['bulk_upload_data'] = session_rows
            request.session['bulk_upload_errors'] = errors
            request.session['bulk_upload_business'] = request.POST.get('business_name', '').strip()
            request.session['bulk_upload_latitude'] = request.POST.get('latitude', '')
            request.session['bulk_upload_longitude'] = request.POST.get('longitude', '')
            
            context.update({
                'preview_rows': session_rows,
                'preview_rows_json': json.dumps(session_rows),
                'preview_errors': errors,
                'total_valid': len(rows),
                'total_errors': len(errors),
                'business_name': request.POST.get('business_name', '').strip(),
                'latitude': request.POST.get('latitude', ''),
                'longitude': request.POST.get('longitude', ''),
                'show_preview': True,
            })
            return render(request, 'bulk_upload.html', context)
        
        elif action == 'confirm':
            # Step 2: Create all records from session data
            session_rows = request.session.get('bulk_upload_data')
            if not session_rows:
                messages.error(request, 'Upload session expired. Please upload the file again.')
                return render(request, 'bulk_upload.html', context)
            
            # Check for inline edited data from frontend JS
            edited_data_json = request.POST.get('edited_data')
            if edited_data_json:
                try:
                    edited_rows = json.loads(edited_data_json)
                    if isinstance(edited_rows, list) and edited_rows:
                        # Simple structural check to grab keys
                        session_rows = edited_rows
                except Exception as e:
                    pass
            
            business_name = request.session.get('bulk_upload_business', '')
            lat_str = request.session.get('bulk_upload_latitude', '')
            lng_str = request.session.get('bulk_upload_longitude', '')
            
            # Parse location
            latitude = None
            longitude = None
            if lat_str and lng_str:
                try:
                    latitude = float(lat_str)
                    longitude = float(lng_str)
                except (ValueError, TypeError):
                    pass
            
            # Get or create business
            business = None
            if business_name:
                business = Business.objects.filter(name__iexact=business_name).first()
                if not business:
                    business_slug = slugify(business_name)
                    original_slug = business_slug
                    counter = 1
                    while Business.objects.filter(slug=business_slug).exists():
                        business_slug = f"{original_slug}-{counter}"
                        counter += 1
                    business = Business.objects.create(
                        name=business_name,
                        slug=business_slug
                    )
            
            created_count = 0
            error_count = 0
            row_errors = []
            failed_rows = []
            
            # --- Pass 1: validate & sanitize every row up front, no DB queries yet ---
            validated = []
            for idx, row in enumerate(session_rows):
                row_num = row.get('row_num', idx + 1)
                
                # Re-validate/sanitize here too — this data may have just come
                # straight from the edit-in-preview table, so it hasn't been
                # through _parse_csv's cleanup (currency symbols, commas, etc.)
                product_name = str(row.get('product_name', '')).strip()
                if not product_name:
                    row_errors.append({'row': row_num, 'error': 'Product name is required.'})
                    failed_rows.append(row)
                    error_count += 1
                    continue
                
                price_str = re.sub(r'[^\d.]', '', str(row.get('price', '')))
                try:
                    price = Decimal(price_str)
                    if price <= 0:
                        raise InvalidOperation('non-positive price')
                except (InvalidOperation, ValueError):
                    row_errors.append({'row': row_num, 'error': f'Invalid price "{row.get("price", "")}" for "{product_name}".'})
                    failed_rows.append(row)
                    error_count += 1
                    continue
                
                currency = str(row.get('currency', '')).strip().upper() or 'PGK'
                if len(currency) != 3 or not currency.isalpha():
                    row_errors.append({'row': row_num, 'error': f'Invalid currency "{currency}" for "{product_name}" — used PGK instead.'})
                    currency = 'PGK'
                
                validated.append({
                    'row_num': row_num,
                    'product_name': product_name,
                    'price': price,
                    'currency': currency,
                    'notes': str(row.get('notes', ''))[:1000],
                    'tags_str': str(row.get('tags', '')).strip(),
                    'original': row,
                })
            
            try:
                with transaction.atomic():
                    # --- Pass 2: resolve products in bulk. At a few hundred rows,
                    # looking each one up (plus a slug-uniqueness while-loop) individually
                    # means 1000+ queries before a single price even gets created — slow
                    # enough to risk hitting the request timeout. Product has no signals
                    # tied to it, so it's safe to batch this part.
                    unique_names = {v['product_name'] for v in validated}
                    existing_products = {}
                    if unique_names:
                        matches = Product.objects.annotate(name_lower=Lower('name')).filter(
                            name_lower__in=[n.lower() for n in unique_names]
                        )
                        for p in matches:
                            existing_products[p.name.lower()] = p
                    
                    missing_names = [n for n in unique_names if n.lower() not in existing_products]
                    if missing_names:
                        existing_slugs = set(Product.objects.values_list('slug', flat=True))
                        new_products = []
                        for name in missing_names:
                            base_slug = slugify(name)
                            slug = base_slug
                            counter = 1
                            while slug in existing_slugs:
                                slug = f'{base_slug}-{counter}'
                                counter += 1
                            existing_slugs.add(slug)  # reserve it against the rest of this batch
                            new_products.append(Product(name=name, slug=slug, created_by=request.user))
                        created_products = Product.objects.bulk_create(new_products)
                        for p in created_products:
                            existing_products[p.name.lower()] = p
                    
                    # --- Pass 3: create price reports one at a time. This is NOT
                    # switched to bulk_create — PriceReport has a pre_save signal that
                    # computes the h3 geospatial index used for map clustering, and a
                    # post_save signal handling watchlist notifications and cache
                    # invalidation. bulk_create() skips both silently, which would leave
                    # bulk-uploaded prices with a location invisible on the map. Plain
                    # .create() at a few hundred rows is comfortably fast once the
                    # product lookups above aren't also doing hundreds of queries.
                    for v in validated:
                        try:
                            product = existing_products[v['product_name'].lower()]
                            report = PriceReport.objects.create(
                                product=product,
                                business=business,
                                user=request.user,
                                price=v['price'],
                                currency=v['currency'],
                                latitude=latitude,
                                longitude=longitude,
                                notes=v['notes'],
                            )
                            
                            if v['tags_str']:
                                tag_list = [t.strip() for t in v['tags_str'].split(',') if t.strip()]
                                if tag_list:
                                    product.tags.add(*tag_list)
                            
                            created_count += 1
                        except Exception as row_exc:
                            row_errors.append({'row': v['row_num'], 'error': str(row_exc)})
                            failed_rows.append(v['original'])
                            error_count += 1
                            continue
            except Exception as e:
                messages.error(request, f'An error occurred during bulk creation: {str(e)}')
                return render(request, 'bulk_upload.html', context)
            
            if created_count:
                messages.success(request, f'{created_count} price(s) created successfully.')
            
            if error_count:
                # Don't discard the successfully-created rows' progress or bounce the
                # person away from what they were doing — keep the failed rows (with
                # whatever they'd already typed) in the same editable preview so they
                # can fix just those and resubmit, instead of starting the whole
                # upload over from scratch.
                messages.warning(request, f'{error_count} row(s) need fixing before they can be saved — see below.')
                
                request.session['bulk_upload_data'] = failed_rows
                request.session['bulk_upload_errors'] = row_errors
                # business/latitude/longitude stay as-is in the session for the retry
                
                context.update({
                    'preview_rows': failed_rows,
                    'preview_rows_json': json.dumps(failed_rows),
                    'preview_errors': row_errors,
                    'total_valid': len(failed_rows),
                    'total_errors': len(row_errors),
                    'business_name': business_name,
                    'latitude': lat_str,
                    'longitude': lng_str,
                    'show_preview': True,
                    'retry_mode': True,
                })
                return render(request, 'bulk_upload.html', context)
            
            # Everything saved cleanly — clean up session and head to a dedicated
            # success page rather than a toast that's easy to miss on the home feed,
            # especially useful at a few hundred rows per upload.
            for key in ['bulk_upload_data', 'bulk_upload_errors', 'bulk_upload_business',
                        'bulk_upload_latitude', 'bulk_upload_longitude']:
                request.session.pop(key, None)
            
            request.session['bulk_upload_summary'] = {
                'created_count': created_count,
                'business_name': business.name if business else business_name,
                'business_id': business.id if business else None,
            }
            return redirect('bulk_upload_success')
    
    return render(request, 'bulk_upload.html', context)


@login_required
def bulk_upload_success(request):
    summary = request.session.pop('bulk_upload_summary', None)
    if not summary:
        # Nothing to show (e.g. a direct visit or a page refresh after the
        # one-time summary was already consumed) — send them back to start over.
        return redirect('bulk_upload')
    
    return render(request, 'bulk_upload_success.html', {
        'created_count': summary.get('created_count', 0),
        'business_name': summary.get('business_name', ''),
        'business_id': summary.get('business_id'),
    })


class BusinessCreateView(CreateView):
    model = Business
    form_class = BusinessForm
    template_name = 'business_create.html'
    
    def get_success_url(self):
        return reverse('business_detail', kwargs={'pk': self.object.pk})
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['businesses'] = Business.objects.all().order_by('name')
        return context
        
    def form_valid(self, form):
        # Use business normalization service to avoid duplicates
        business_name = form.cleaned_data['name']
        existing_business, _, similarity = BusinessMatcher.find_best_match(business_name)
        
        if existing_business and similarity >= 0.8:
            form.add_error('name', f'A business with a similar name already exists: "{existing_business.name}". Please use a different name or edit the existing business.')
            return self.form_invalid(form)
        
        # Generate unique slug
        slug = slugify(business_name)
        original_slug = slug
        counter = 1
        while Business.objects.filter(slug=slug).exists():
            slug = f"{original_slug}-{counter}"
            counter += 1
        form.instance.slug = slug
        
        # Save the business
        response = super().form_valid(form)
        
        return response

business_create = BusinessCreateView.as_view()


@login_required
def download_csv_template(request):
    """Serve a downloadable CSV template file."""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="wikonomi_bulk_upload_template.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['product_name', 'price', 'currency', 'notes', 'tags'])
    writer.writerow(['Rice 10kg', '45.00', 'PGK', 'White rice bag', 'staple,grain'])
    writer.writerow(['Cooking Oil 1L', '18.50', 'PGK', '', 'cooking'])
    writer.writerow(['Sugar 1kg', '8.00', 'PGK', 'Brown sugar', 'staple'])
    
    return response
