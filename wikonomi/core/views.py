from django.urls import reverse_lazy
from django.views.generic import CreateView, DetailView, UpdateView
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django import forms
from django.views.decorators.cache import cache_page
from .models import PriceReport, PriceHistory, Product, Business, ProductWatchlist, Notification, ShoppingList, ShoppingListItem

class PriceReportForm(forms.ModelForm):
    class Meta:
        model = PriceReport
        fields = ['price', 'currency', 'latitude', 'longitude', 'notes', 'image']
        widgets = {
            'price': forms.NumberInput(attrs={'class': 'block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm', 'step': '0.01'}),
            'currency': forms.TextInput(attrs={'class': 'block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm'}),
            'latitude': forms.HiddenInput(),
            'longitude': forms.HiddenInput(),
            'notes': forms.Textarea(attrs={'class': 'block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm', 'rows': 3}),
            'image': forms.FileInput(attrs={'class': 'hidden', 'accept': 'image/*'}),
        }

class PriceReportCreateView(CreateView):
    model = PriceReport
    form_class = PriceReportForm
    template_name = 'price_report_form.html'
    success_url = reverse_lazy('home')
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from .models import Product, Business
        context['products'] = Product.objects.all().order_by('name')
        context['businesses'] = Business.objects.all().order_by('name')
        return context
        
    def form_valid(self, form):
        from django.contrib.auth.models import User
        from .models import Product
        from django.utils.text import slugify
        
        # 1. Handle user
        if not self.request.user.is_authenticated:
            # MVP: get or create an anonymous user
            user, _ = User.objects.get_or_create(username='anonymous')
            form.instance.user = user
        else:
            form.instance.user = self.request.user

        # 2. Handle product (dynamic text input)
        product_name = self.request.POST.get('product_name', '').strip()
        if not product_name:
            form.add_error(None, "Product name is required.")
            return self.form_invalid(form)
            
        # Get or create product (using slugify for slug, ensuring uniqueness)
        product = Product.objects.filter(name__iexact=product_name).first()
        if not product:
            product_slug = slugify(product_name)
            original_slug = product_slug
            counter = 1
            while Product.objects.filter(slug=product_slug).exists():
                product_slug = f"{original_slug}-{counter}"
                counter += 1
            
            product = Product.objects.create(
                name=product_name,
                slug=product_slug,
                created_by=form.instance.user
            )

        form.instance.product = product
        
        # 2b. Handle business (optional dynamic text input)
        business_name = self.request.POST.get('business_name', '').strip()
        if business_name:
            from .models import Business
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
            form.instance.business = business
        
        # 3. Save the form to hit the DB
        response = super().form_valid(form)
        
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
        
        return response

price_report_create = PriceReportCreateView.as_view()

def _get_prices_queryset(request):
    """Helper to get and sort prices uniformly across feed and map endpoints."""
    query = request.GET.get('q', '').strip()
    sort = request.GET.get('sort', 'recent')
    user_lat = request.GET.get('lat')
    user_lng = request.GET.get('lng')
    
    qs = PriceReport.objects.select_related('product', 'business', 'user').prefetch_related('user__profile')
    
    if query:
        qs = qs.filter(
            Q(product__name__icontains=query) | 
            Q(business__name__icontains=query)
        )
    
    # Apply sorting
    if sort == 'price_asc':
        qs = qs.order_by('price', '-observed_at')
    elif sort == 'price_desc':
        qs = qs.order_by('-price', '-observed_at')
    elif sort == 'nearest' and user_lat and user_lng:
        try:
            user_lat = float(user_lat)
            user_lng = float(user_lng)
            from .utils import annotate_with_distance
            qs = annotate_with_distance(qs, user_lat, user_lng)
        except (ValueError, TypeError):
            qs = qs.order_by('-observed_at')
    else:
        qs = qs.order_by('-observed_at')
        
    return qs, sort, user_lat, user_lng

def home(request):
    latest_prices, sort, user_lat, user_lng = _get_prices_queryset(request)
    
    # Initial load - first 20 items
    latest_prices = latest_prices[:20]
    
    return render(request, 'home.html', {
        'latest_prices': latest_prices,
        'current_sort': sort,
    })

def about_view(request):
    return render(request, 'about.html')

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

@cache_page(60 * 2)
def load_more_prices(request):
    page = int(request.GET.get('page', 1))
    latest_prices, sort, user_lat, user_lng = _get_prices_queryset(request)
    
    # Use paginator for infinite scroll
    paginator = Paginator(latest_prices, 20)
    
    try:
        prices_page = paginator.page(page)
    except PageNotAnInteger:
        return JsonResponse({'error': 'Invalid page number.'}, status=400)
    except EmptyPage:
        return JsonResponse({'has_more': False})
    
    from django.utils.timesince import timesince

    # Prepare data for JSON response
    items_data = []
    for price in prices_page:
        item_data = {
            'id': price.id,
            'product_name': price.product.name,
            'price': str(price.price),
            'currency': price.currency,
            'business_name': price.business.name if price.business else None,
            'username': price.user.username,
            'profile_picture_url': price.user.profile.profile_picture.url if hasattr(price.user, 'profile') and price.user.profile.profile_picture else None,
            'observed_at': price.observed_at.strftime('%Y-%m-%d %H:%M'),
            'has_location': bool(price.latitude and price.longitude),
            'timesince': f"{timesince(price.observed_at)} ago"
        }
        # Add distance if available
        if hasattr(price, 'distance_km'):
            item_data['distance_km'] = round(price.distance_km, 1)
        items_data.append(item_data)
    
    return JsonResponse({
        'items': items_data,
        'has_more': prices_page.has_next(),
        'current_page': page,
        'total_pages': paginator.num_pages
    })

class PriceReportDetailView(DetailView):
    model = PriceReport
    template_name = 'price_report_detail.html'
    context_object_name = 'report'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from .utils import get_nearby_prices
        report = self.get_object()
        
        # Get nearby prices if the report has coordinates
        if report.latitude and report.longitude:
            # Exclude the current report from the nearby list
            nearby = get_nearby_prices(
                product=report.product,
                lat=report.latitude,
                lng=report.longitude
            ).exclude(id=report.id)[:5] # Show up to 5 nearby prices
            context['nearby_prices'] = nearby
        else:
            context['nearby_prices'] = None
            
        if self.request.user.is_authenticated:
            context['is_watching'] = ProductWatchlist.objects.filter(
                user=self.request.user,
                product=report.product
            ).exists()
            # Deletion permission context
            if report.marked_for_deletion:
                context['can_vote_delete'] = report.can_vote_delete(self.request.user)
                context['can_delete'] = report.can_delete(self.request.user)
            else:
                context['can_vote_delete'] = False
                context['can_delete'] = False
        else:
            context['is_watching'] = False
            context['can_vote_delete'] = False
            context['can_delete'] = False
            
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
        ).select_related('product', 'user').prefetch_related('product__tags').order_by('-observed_at')
        
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
            latest_price = product.price_reports.filter(business=business).first()
            products_data.append({
                'product': product,
                'latest_price': latest_price
            })
        
        context['price_reports'] = price_reports
        context['reports_with_location'] = reports_with_location
        context['products_data'] = products_data
        context['total_reports'] = price_reports.count()
        context['reports_with_location_count'] = reports_with_location.count()
        
        return context

business_detail = BusinessDetailView.as_view()

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
        # Store old values
        old_price = report.price
        old_currency = report.currency
        
        # Update fields
        report.price = request.POST.get('price')
        report.currency = request.POST.get('currency', 'PGK')
        report.notes = request.POST.get('notes', '')
        report.last_edited_by = request.user
        
        from django.utils.text import slugify
        
        # Handle product updates
        product_name = request.POST.get('product_name', '').strip()
        if product_name and product_name.lower() != report.product.name.lower():
            product = Product.objects.filter(name__iexact=product_name).first()
            if not product:
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
            report.product = product

        # Handle business updates
        business_name = request.POST.get('business_name', '').strip()
        if business_name:
            if not report.business or business_name.lower() != report.business.name.lower():
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
                report.business = business
        elif 'business_name' in request.POST:
            # If the field is submitted but empty, the user wants to remove the business
            report.business = None
        
        # Handle image
        if 'image' in request.FILES:
            report.image = request.FILES['image']
            
            # Optionally update product or business if they don't have an image
            if not report.product.image:
                report.product.image = report.image
                report.product.save()
            if report.business and not report.business.image:
                report.business.image = report.image
                report.business.save()
        
        # Handle location updates
        lat = request.POST.get('latitude')
        lng = request.POST.get('longitude')
        
        if lat and lng:
            try:
                report.latitude = float(lat)
                report.longitude = float(lng)
            except ValueError:
                messages.warning(request, 'Invalid coordinates provided. Location not updated.')
        elif lat == '' or lng == '':
            # Clear location if both fields are empty
            report.latitude = None
            report.longitude = None
        
        report.save()
        
        # Handle tags
        tags_string = request.POST.get('tags', '').strip()
        if tags_string:
            # Clear existing tags
            report.product.tags.clear()
            # Add new tags
            tag_list = [tag.strip() for tag in tags_string.split(',') if tag.strip()]
            if tag_list:
                report.product.tags.add(*tag_list)
        
        # Create history record if price changed
        if old_price != report.price or old_currency != report.currency:
            PriceHistory.objects.create(
                price_report=report,
                old_price=old_price,
                new_price=report.price,
                old_currency=old_currency,
                new_currency=report.currency,
                changed_by=request.user,
                notes=f"Price updated from {old_price} {old_currency} to {report.price} {report.currency}"
            )
        
        messages.success(request, 'Price report updated successfully!')
        return redirect('price_detail', pk=report.pk)
    
    products = Product.objects.all().order_by('name')
    businesses = Business.objects.all().order_by('name')
    return render(request, 'price_report_edit.html', {'report': report, 'products': products, 'businesses': businesses})

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
    
    messages.success(request, 'Price report marked for deletion. Another user must confirm to delete it.')
    return redirect('price_detail', pk=pk)

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
        
        if action == 'preview':
            # Step 1: Parse and validate the CSV
            csv_file = request.FILES.get('csv_file')
            if not csv_file:
                messages.error(request, 'Please select a CSV file to upload.')
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
                'preview_rows': rows,
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
            
            try:
                with transaction.atomic():
                    for row in session_rows:
                        try:
                            # Get or create product
                            product = Product.objects.filter(name__iexact=row['product_name']).first()
                            if not product:
                                product_slug = slugify(row['product_name'])
                                original_slug = product_slug
                                counter = 1
                                while Product.objects.filter(slug=product_slug).exists():
                                    product_slug = f"{original_slug}-{counter}"
                                    counter += 1
                                product = Product.objects.create(
                                    name=row['product_name'],
                                    slug=product_slug,
                                    created_by=request.user
                                )
                            
                            # Create price report
                            report = PriceReport.objects.create(
                                product=product,
                                business=business,
                                user=request.user,
                                price=Decimal(row['price']),
                                currency=row['currency'],
                                latitude=latitude,
                                longitude=longitude,
                                notes=row.get('notes', ''),
                            )
                            
                            # Handle tags
                            tags_str = row.get('tags', '').strip()
                            if tags_str:
                                tag_list = [t.strip() for t in tags_str.split(',') if t.strip()]
                                if tag_list:
                                    product.tags.add(*tag_list)
                            
                            created_count += 1
                        except Exception:
                            error_count += 1
                            continue
            except Exception as e:
                messages.error(request, f'An error occurred during bulk creation: {str(e)}')
                return render(request, 'bulk_upload.html', context)
            
            # Clean up session
            for key in ['bulk_upload_data', 'bulk_upload_errors', 'bulk_upload_business',
                        'bulk_upload_latitude', 'bulk_upload_longitude']:
                request.session.pop(key, None)
            
            messages.success(request, f'Bulk upload complete! {created_count} price(s) created successfully.')
            if error_count:
                messages.warning(request, f'{error_count} row(s) failed during creation.')
            
            return redirect('home')
    
    return render(request, 'bulk_upload.html', context)


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
