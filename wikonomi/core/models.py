from django.db import models
from django.contrib.auth.models import User
from django.contrib.contenttypes.fields import GenericRelation
from taggit.managers import TaggableManager
import h3
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django_resized import ResizedImageField
from django.core.cache import cache
from django.core.validators import MaxValueValidator, MinValueValidator
from django.core.files.base import ContentFile
from django.utils.text import slugify
from difflib import SequenceMatcher
from io import BytesIO
import re

from PIL import Image, ImageOps

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True)

    def __str__(self):
        return self.name

class Product(models.Model):
    name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    image = ResizedImageField(upload_to='product_images/', null=True, blank=True, size=[1000, 1000], quality=75, force_format='JPEG')
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    tags = TaggableManager()
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    comments = GenericRelation('comments.Comment', related_query_name='product')

    def __str__(self):
        return self.name

class ProductAlias(models.Model):
    """
    Maps product name variations to canonical products.
    This enables normalization of user-submitted product names.
    """
    canonical_product = models.ForeignKey(
        Product, 
        on_delete=models.CASCADE, 
        related_name='aliases'
    )
    alias_name = models.CharField(max_length=255, db_index=True)
    normalized_name = models.CharField(max_length=255, db_index=True)
    signature = models.CharField(max_length=255, db_index=True, null=True, blank=True)  # For pattern-based matching
    created_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ('canonical_product', 'alias_name')
        ordering = ['alias_name']
        indexes = [
            models.Index(fields=['signature']),
        ]
    
    def __str__(self):
        return f"{self.alias_name} → {self.canonical_product.name}"
    
    def save(self, *args, **kwargs):
        # Auto-generate normalized name and signature for better matching
        self.normalized_name = self.normalize_text(self.alias_name)
        self.signature = self.create_normalized_signature(self.alias_name)
        super().save(*args, **kwargs)
    
    @staticmethod
    def normalize_text(text):
        """Normalize text for better matching by removing extra spaces, punctuation, etc."""
        # Convert to lowercase and remove extra whitespace
        text = ' '.join(text.lower().split())
        # Remove common punctuation
        text = re.sub(r'[^\w\s]', ' ', text)
        # Remove extra spaces again
        text = ' '.join(text.split())
        return text
    
    @staticmethod
    def extract_product_components(text):
        """
        Extract product name and size/quantity components from text.
        Handles patterns like "Rice 1kg", "1kg Rice", "Coca Cola 500ml", etc.
        """
        normalized = ProductAlias.normalize_text(text)
        
        # Common size patterns
        size_patterns = [
            r'(\d+(?:\.\d+)?)\s*(kg|g|l|ml|oz|lb|pcs|pc|pack|bottle|can|box|bag)',
            r'(\d+(?:\.\d+)?)\s*(kilogram|gram|liter|milliliter|ounce|pound|piece|pieces)',
            r'(\d+(?:\.\d+)?)\s*(x\s*\d+)',  # pack sizes like "6 x 250ml"
        ]
        
        size_match = None
        size_info = None
        
        for pattern in size_patterns:
            match = re.search(pattern, normalized)
            if match:
                size_match = match
                size_info = match.group(0)
                break
        
        if size_match:
            # Remove size from text to get product name
            product_name = normalized.replace(size_info, '').strip()
            return {
                'product_name': product_name,
                'size_info': size_info,
                'full_text': normalized
            }
        else:
            return {
                'product_name': normalized,
                'size_info': None,
                'full_text': normalized
            }
    
    @staticmethod
    def create_normalized_signature(text):
        """
        Create a normalized signature that handles pattern variations.
        "Rice 1kg" and "1kg Rice" will produce the same signature.
        """
        components = ProductAlias.extract_product_components(text)
        
        if components['size_info']:
            # Sort components: product name first, then size
            signature = f"{components['product_name']} {components['size_info']}"
        else:
            signature = components['product_name']
        
        return ProductAlias.normalize_text(signature)

class ProductMatcher:
    """
    Service class for matching and normalizing product names.
    """
    
    @staticmethod
    def find_best_match(product_name, min_similarity=0.7):
        """
        Find the best matching product for a given name.
        Returns tuple (product, similarity_score) or (None, 0)
        """
        # Create signature for pattern-based matching
        input_signature = ProductAlias.create_normalized_signature(product_name)
        normalized_input = ProductAlias.normalize_text(product_name)
        
        # First try exact signature match (handles "Rice 1kg" vs "1kg Rice")
        signature_match = ProductAlias.objects.filter(
            signature=input_signature,
            is_active=True
        ).first()
        
        if signature_match:
            return signature_match.canonical_product, 1.0
        
        # Then try exact normalized name match
        alias_match = ProductAlias.objects.filter(
            normalized_name=normalized_input,
            is_active=True
        ).first()
        
        if alias_match:
            return alias_match.canonical_product, 1.0
        
        # Try fuzzy matching with signatures (pattern-based)
        best_match = None
        best_score = 0
        
        for alias in ProductAlias.objects.filter(is_active=True):
            # Compare signatures first (pattern-based)
            signature_similarity = SequenceMatcher(
                None, 
                input_signature, 
                alias.signature
            ).ratio()
            
            # Also compare normalized names
            name_similarity = SequenceMatcher(
                None, 
                normalized_input, 
                alias.normalized_name
            ).ratio()
            
            # Use the higher of the two similarities
            similarity = max(signature_similarity, name_similarity)
            
            if similarity > best_score and similarity >= min_similarity:
                best_score = similarity
                best_match = alias.canonical_product
        
        # If no alias match, try direct product matching with signatures
        if not best_match:
            for product in Product.objects.all():
                product_signature = ProductAlias.create_normalized_signature(product.name)
                product_normalized = ProductAlias.normalize_text(product.name)
                
                signature_similarity = SequenceMatcher(
                    None, 
                    input_signature, 
                    product_signature
                ).ratio()
                
                name_similarity = SequenceMatcher(
                    None, 
                    normalized_input, 
                    product_normalized
                ).ratio()
                
                similarity = max(signature_similarity, name_similarity)
                
                if similarity > best_score and similarity >= min_similarity:
                    best_score = similarity
                    best_match = product
        
        return best_match, best_score
    
    @staticmethod
    def create_or_match_product(product_name, category=None, created_by=None):
        """
        Create a new product or find existing match.
        Returns the product object and whether it was created.
        """
        product, similarity = ProductMatcher.find_best_match(product_name)
        
        if product and similarity >= 0.8:
            return product, False
        
        # Create new product if no good match found
        slug = slugify(product_name)
        
        # Ensure unique slug
        original_slug = slug
        counter = 1
        while Product.objects.filter(slug=slug).exists():
            slug = f"{original_slug}-{counter}"
            counter += 1
        
        product = Product.objects.create(
            name=product_name,
            slug=slug,
            category=category,
            created_by=created_by
        )
        
        return product, True
    
    @staticmethod
    def add_alias(canonical_product, alias_name, created_by=None):
        """
        Add an alias for a canonical product.
        """
        alias, created = ProductAlias.objects.get_or_create(
            canonical_product=canonical_product,
            alias_name=alias_name,
            defaults={'created_by': created_by}
        )
        return alias, created


class ProductNormalizationService:
    """
    High-level service for product normalization operations.
    """
    
    @staticmethod
    def normalize_price_report_data(product_name, business_name=None, category=None):
        """
        Normalize product data for price reports.
        Returns (product, was_created) tuple.
        """
        return ProductMatcher.create_or_match_product(product_name, category)
    
    @staticmethod
    def bulk_normalize_products(product_names, created_by=None):
        """
        Normalize a list of product names.
        Returns list of (product, was_created) tuples.
        """
        results = []
        for name in product_names:
            product, was_created = ProductMatcher.create_or_match_product(
                name, created_by=created_by
            )
            results.append((product, was_created))
        return results
    
    @staticmethod
    def get_product_variations(canonical_product):
        """
        Get all known variations/aliases for a product.
        """
        return ProductAlias.objects.filter(
            canonical_product=canonical_product,
            is_active=True
        )
    
    @staticmethod
    def merge_products(source_product, target_product, created_by=None):
        """
        Merge two products, making target_product the canonical one.
        All aliases and price reports will be redirected to target_product.
        """
        # Update all aliases to point to target
        ProductAlias.objects.filter(
            canonical_product=source_product
        ).update(canonical_product=target_product)
        
        # Update all price reports to point to target
        PriceReport.objects.filter(
            product=source_product
        ).update(product=target_product)
        
        # Create an alias for the old product name
        ProductAlias.objects.get_or_create(
            canonical_product=target_product,
            alias_name=source_product.name,
            defaults={'created_by': created_by}
        )
        
        # Delete the source product
        source_product.delete()

class Business(models.Model):
    name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(unique=True)
    details = models.TextField(blank=True, null=True, help_text="Additional information about the business")
    image = ResizedImageField(upload_to='business_images/', null=True, blank=True, size=[1000, 1000], quality=75, force_format='JPEG')
    created_at = models.DateTimeField(auto_now_add=True)
    comments = GenericRelation('comments.Comment', related_query_name='business')
    business_subcategory = models.ForeignKey(
        'categories.BusinessSubcategory',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='businesses',
    )

    def __str__(self):
        return self.name

    def get_default_location(self):
        """Return this business's default ``(latitude, longitude)`` when known.

        An explicitly selected main branch location is preferred. If no branch
        has coordinates yet, the first reported price with coordinates becomes
        the implicit default location for the business.
        """
        main_branch = self.branches.filter(
            is_active=True,
            is_main_branch=True,
            latitude__isnull=False,
            longitude__isnull=False,
        ).first()
        if main_branch:
            return (main_branch.latitude, main_branch.longitude)

        branch = self.branches.filter(
            is_active=True,
            latitude__isnull=False,
            longitude__isnull=False,
        ).order_by('-is_main_branch', 'created_at', 'id').first()
        if branch:
            return (branch.latitude, branch.longitude)

        first_located_price = self.price_reports.filter(
            latitude__isnull=False,
            longitude__isnull=False,
        ).order_by('observed_at', 'id').first()
        if first_located_price:
            return (first_located_price.latitude, first_located_price.longitude)

        return None

    def get_default_location_source(self):
        """Return a human-readable source for the default location."""
        main_branch = self.branches.filter(
            is_active=True,
            is_main_branch=True,
            latitude__isnull=False,
            longitude__isnull=False,
        ).first()
        if main_branch:
            return main_branch.get_full_name()

        branch = self.branches.filter(
            is_active=True,
            latitude__isnull=False,
            longitude__isnull=False,
        ).order_by('-is_main_branch', 'created_at', 'id').first()
        if branch:
            return branch.get_full_name()

        first_located_price = self.price_reports.filter(
            latitude__isnull=False,
            longitude__isnull=False,
        ).select_related('product').order_by('observed_at', 'id').first()
        if first_located_price:
            return f"first reported price ({first_located_price.product.name})"

        return None

class BusinessBranch(models.Model):
    """
    Represents a specific branch/location of a business.
    This allows businesses like "TST" to have multiple locations.
    """
    canonical_business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name='branches'
    )
    name = models.CharField(max_length=255, help_text="Branch name (e.g., 'Port Moresby Main', 'Waigani Branch')")
    slug = models.SlugField(max_length=255)
    address = models.TextField(blank=True, null=True, help_text="Full address of this branch")
    latitude = models.FloatField(null=True, blank=True, help_text="Branch latitude for mapping")
    longitude = models.FloatField(null=True, blank=True, help_text="Branch longitude for mapping")
    phone = models.CharField(max_length=50, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    is_main_branch = models.BooleanField(default=False, help_text="Mark as the main/head office branch")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    class Meta:
        unique_together = ('canonical_business', 'slug')
        ordering = ['is_main_branch', 'name']
        indexes = [
            models.Index(fields=['canonical_business', 'is_active']),
            models.Index(fields=['latitude', 'longitude']),
        ]

    def __str__(self):
        return f"{self.canonical_business.name} - {self.name}"

    def get_full_name(self):
        """Get the full business name including branch"""
        if self.name.lower() in ['main', 'head office', 'hq']:
            return self.canonical_business.name
        return f"{self.canonical_business.name} {self.name}"

class BusinessAlias(models.Model):
    """
    Maps business name variations to canonical businesses.
    This enables normalization of user-submitted business names.
    """
    canonical_business = models.ForeignKey(
        Business, 
        on_delete=models.CASCADE, 
        related_name='aliases'
    )
    alias_name = models.CharField(max_length=255, db_index=True)
    normalized_name = models.CharField(max_length=255, db_index=True)
    created_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ('canonical_business', 'alias_name')
        ordering = ['alias_name']
        indexes = [
            models.Index(fields=['normalized_name']),
        ]
    
    def __str__(self):
        return f"{self.alias_name} → {self.canonical_business.name}"
    
    def save(self, *args, **kwargs):
        # Auto-generate normalized name for better matching
        self.normalized_name = self.normalize_text(self.alias_name)
        super().save(*args, **kwargs)
    
    @staticmethod
    def normalize_text(text):
        """Normalize text for better matching by removing extra spaces, punctuation, etc."""
        # Convert to lowercase and remove extra whitespace
        text = ' '.join(text.lower().split())
        # Remove common punctuation
        text = re.sub(r'[^\w\s]', ' ', text)
        # Remove extra spaces again
        text = ' '.join(text.split())
        return text

class BusinessMatcher:
    """
    Service class for matching and normalizing business names with branch support.
    """
    
    @staticmethod
    def find_best_match(business_name, min_similarity=0.7):
        """
        Find the best matching business for a given name.
        Returns tuple (business, branch, similarity_score) or (None, None, 0)
        """
        normalized_input = BusinessAlias.normalize_text(business_name)
        
        # First try exact branch match
        branch_match = BusinessBranch.objects.filter(
            name__icontains=business_name
        ).select_related('canonical_business').first()
        
        if branch_match:
            return branch_match.canonical_business, branch_match, 1.0
        
        # Try business alias matches
        alias_match = BusinessAlias.objects.filter(
            normalized_name=normalized_input,
            is_active=True
        ).first()
        
        if alias_match:
            # Find the main branch for this business
            main_branch = BusinessBranch.objects.filter(
                canonical_business=alias_match.canonical_business,
                is_main_branch=True
            ).first()
            return alias_match.canonical_business, main_branch, 1.0
        
        # Try fuzzy matching with existing aliases
        best_match = None
        best_branch = None
        best_score = 0
        
        for alias in BusinessAlias.objects.filter(is_active=True):
            similarity = SequenceMatcher(
                None, 
                normalized_input, 
                alias.normalized_name
            ).ratio()
            
            if similarity > best_score and similarity >= min_similarity:
                best_score = similarity
                best_match = alias.canonical_business
                # Find main branch for this business
                main_branch = BusinessBranch.objects.filter(
                    canonical_business=alias.canonical_business,
                    is_main_branch=True
                ).first()
                best_branch = main_branch
        
        # If no alias match, try direct business matching
        if not best_match:
            for business in Business.objects.all():
                business_normalized = BusinessAlias.normalize_text(business.name)
                similarity = SequenceMatcher(
                    None, 
                    normalized_input, 
                    business_normalized
                ).ratio()
                
                if similarity > best_score and similarity >= min_similarity:
                    best_score = similarity
                    best_match = business
                    # Find main branch for this business
                    main_branch = BusinessBranch.objects.filter(
                        canonical_business=business,
                        is_main_branch=True
                    ).first()
                    best_branch = main_branch
        
        return best_match, best_branch, best_score
    
    @staticmethod
    def create_or_match_business_with_location(business_name, location=None, created_by=None):
        """
        Create a new business or find existing match, optionally creating a branch.
        Returns the (business, branch, was_created) tuple.
        """
        business, branch, similarity = BusinessMatcher.find_best_match(business_name)
        
        if business and similarity >= 0.8:
            # If we have location info and it's different from main branch, create new branch
            if location and location.strip():
                existing_branch = BusinessBranch.objects.filter(
                    canonical_business=business,
                    name__icontains=location
                ).first()
                
                if not existing_branch:
                    # Create new branch
                    branch = BusinessBranch.objects.create(
                        canonical_business=business,
                        name=location,
                        slug=f"{business.slug}-{slugify(location)}",
                        created_by=created_by
                    )
                    return business, branch, True
                else:
                    return business, existing_branch, False
            
            return business, branch, False
        
        # Create new business if no good match found
        slug = slugify(business_name)
        
        # Ensure unique slug
        original_slug = slug
        counter = 1
        while Business.objects.filter(slug=slug).exists():
            slug = f"{original_slug}-{counter}"
            counter += 1
        
        business = Business.objects.create(
            name=business_name,
            slug=slug
        )
        
        # Create main branch if location provided
        branch = None
        if location and location.strip():
            branch = BusinessBranch.objects.create(
                canonical_business=business,
                name=location if location.strip() else "Main Branch",
                slug=f"{business.slug}-main",
                is_main_branch=True,
                created_by=created_by
            )
        
        return business, branch, True
    
    @staticmethod
    def add_alias(canonical_business, alias_name, created_by=None):
        """
        Add an alias for a canonical business.
        """
        alias, created = BusinessAlias.objects.get_or_create(
            canonical_business=canonical_business,
            alias_name=alias_name,
            defaults={'created_by': created_by}
        )
        return alias, created


class BusinessNormalizationService:
    """
    High-level service for business normalization operations with branch support.
    """
    
    @staticmethod
    def normalize_price_report_data(business_name, location=None):
        """
        Normalize business data for price reports with location support.
        Returns (business, branch, was_created) tuple.
        """
        return BusinessMatcher.create_or_match_business_with_location(
            business_name, location=location
        )
    
    @staticmethod
    def bulk_normalize_businesses(business_data, created_by=None):
        """
        Normalize a list of business names with optional locations.
        business_data should be list of (name, location) tuples.
        Returns list of (business, branch, was_created) tuples.
        """
        results = []
        for name, location in business_data:
            business, branch, was_created = BusinessMatcher.create_or_match_business_with_location(
                name, location=location, created_by=created_by
            )
            results.append((business, branch, was_created))
        return results
    
    @staticmethod
    def get_business_variations(canonical_business):
        """
        Get all known variations/aliases for a business.
        """
        return BusinessAlias.objects.filter(
            canonical_business=canonical_business,
            is_active=True
        )
    
    @staticmethod
    def get_business_branches(canonical_business):
        """
        Get all branches for a business.
        """
        return BusinessBranch.objects.filter(
            canonical_business=canonical_business,
            is_active=True
        ).select_related('canonical_business')
    
    @staticmethod
    def merge_businesses(source_business, target_business, created_by=None):
        """
        Merge two businesses, making target_business the canonical one.
        All aliases and branches will be redirected to target_business.
        """
        # Update all aliases to point to target
        BusinessAlias.objects.filter(
            canonical_business=source_business
        ).update(canonical_business=target_business)
        
        # Update all branches to point to target
        BusinessBranch.objects.filter(
            canonical_business=source_business
        ).update(canonical_business=target_business)
        
        # Update all price reports to point to target
        PriceReport.objects.filter(
            business=source_business
        ).update(business=target_business)
        
        # Create an alias for the old business name
        BusinessAlias.objects.get_or_create(
            canonical_business=target_business,
            alias_name=source_business.name,
            defaults={'created_by': created_by}
        )
        
        # Delete the source business
        source_business.delete()

class PriceReport(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='price_reports')
    business = models.ForeignKey(Business, on_delete=models.SET_NULL, null=True, blank=True, related_name='price_reports')
    business_branch = models.ForeignKey('BusinessBranch', on_delete=models.SET_NULL, null=True, blank=True, related_name='price_reports')
    subcategory = models.ForeignKey(
        'categories.Subcategory',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='price_reports',
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='price_reports')
    last_edited_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='edited_price_reports')
    
    price = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default='PGK')
    
    image = ResizedImageField(upload_to='price_report_images/', null=True, blank=True, size=[1000, 1000], quality=75, force_format='JPEG')
    comments = GenericRelation('comments.Comment', related_query_name='price_report')
    
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    
    observed_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)
    notes = models.TextField(blank=True)

    # H3 for fast "same vicinity" comparison
    h3_res9 = models.CharField(max_length=16, null=True, blank=True, db_index=True)
    h3_res8 = models.CharField(max_length=16, null=True, blank=True, db_index=True)

    duplicated_from = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='duplicates')
    duplicate_trust_votes = models.ManyToManyField(User, related_name='trusted_duplicate_reports', blank=True)
    duplicate_verify_votes = models.ManyToManyField(User, related_name='verified_duplicate_reports', blank=True)

    # Deletion request fields
    marked_for_deletion = models.BooleanField(default=False)
    marked_for_deletion_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='marked_for_deletion_reports')
    marked_for_deletion_at = models.DateTimeField(null=True, blank=True)
    deletion_reason = models.TextField(blank=True)
    deletion_votes = models.ManyToManyField(User, related_name='deletion_voted_reports', blank=True)
    
    # OCR processing field
    ocr_processed = models.BooleanField(default=True)

    class Meta:
        ordering = ['-updated_at', '-observed_at']

    @property
    def is_updated(self):
        """Check if report has been updated after initial creation."""
        # Use 1 minute threshold to account for slight differences in auto_now/auto_now_add on creation
        if self.updated_at and self.observed_at:
            from datetime import timedelta
            return self.updated_at > (self.observed_at + timedelta(minutes=1))
        return False

    def __str__(self):
        return f"{self.price} {self.currency} — {self.product}"

    def get_business_display(self):
        """Get the best business name for display (branch preferred over main)"""
        if self.business_branch:
            return self.business_branch.get_full_name()
        elif self.business:
            return self.business.name
        return "Unknown Business"

    def get_lat_lng(self):
        """Get coordinates from branch first, then from report"""
        if self.business_branch and self.business_branch.latitude and self.business_branch.longitude:
            return (self.business_branch.latitude, self.business_branch.longitude)
        return (self.latitude, self.longitude) if self.latitude and self.longitude else None

    def can_delete(self, user):
        """Check if user can delete this report (owner, admin, or after community vote)"""
        if user.is_staff or user.is_superuser:
            return True
        if user == self.user:
            return True
        if self.marked_for_deletion and self.deletion_votes.count() >= 1:
            return True
        return False

    def can_vote_delete(self, user):
        """Check if user can vote to delete (not the marker, not already voted)"""
        if user == self.marked_for_deletion_by:
            return False
        if self.deletion_votes.filter(pk=user.pk).exists():
            return False
        return True

    @property
    def primary_photo(self):
        first_photo = self.photos.first()
        if first_photo:
            return first_photo
        # Wrap the legacy image in a simple object so the template can always call .image.url
        if self.image:
            from types import SimpleNamespace
            return SimpleNamespace(image=self.image)
        return None

    def can_add_more_photos(self):
        """Check if more photos can be added (max 5)"""
        return self.photos.count() < 5

    def get_photo_count(self):
        """Get the total number of photos"""
        count = self.photos.count()
        if self.image and not self.photos.exists():
            # Count legacy image as 1 if no new photos exist
            return 1
        return count

class PriceHistory(models.Model):
    price_report = models.ForeignKey(PriceReport, on_delete=models.CASCADE, related_name='price_history')
    old_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    new_price = models.DecimalField(max_digits=12, decimal_places=2)
    old_currency = models.CharField(max_length=3, null=True, blank=True)
    new_currency = models.CharField(max_length=3, default='PGK')
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    changed_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-changed_at']

    def __str__(self):
        return f"Price change for {self.price_report.product}: {self.old_price} → {self.new_price}"

class PriceReportPhoto(models.Model):
    """Multiple photos for a price report (max 5)"""
    price_report = models.ForeignKey(PriceReport, on_delete=models.CASCADE, related_name='photos')
    image = ResizedImageField(upload_to='price_report_images/', size=[1000, 1000], quality=75, force_format='JPEG')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'uploaded_at']
        verbose_name = 'Price Report Photo'
        verbose_name_plural = 'Price Report Photos'

    def __str__(self):
        return f"Photo for {self.price_report}"

# Auto H3 population


def _normalize_uploaded_image_orientation(instance, field_name):
    """Normalize image orientation based on EXIF so rendered images are upright."""
    image_field = getattr(instance, field_name, None)
    if not image_field:
        return

    try:
        image_field.open('rb')
        image = Image.open(image_field)
        normalized = ImageOps.exif_transpose(image)

        if normalized.mode not in ('RGB', 'L'):
            normalized = normalized.convert('RGB')

        buffer = BytesIO()
        normalized.save(buffer, format='JPEG', quality=75, optimize=True)
        buffer.seek(0)

        original_name = getattr(image_field, 'name', 'image.jpg') or 'image.jpg'
        normalized_name = original_name.rsplit('.', 1)[0] + '.jpg'
        getattr(instance, field_name).save(normalized_name, ContentFile(buffer.read()), save=False)
    except Exception:
        # Keep original image if processing fails for any reason.
        return

@receiver(pre_save, sender=PriceReport)
def populate_h3_index(sender, instance, **kwargs):
    _normalize_uploaded_image_orientation(instance, "image")

    lat = getattr(instance, 'latitude', None)
    lng = getattr(instance, 'longitude', None)
    if lat is not None and lng is not None:
        try:
            instance.h3_res9 = h3.latlng_to_cell(lat, lng, 9)
            instance.h3_res8 = h3.latlng_to_cell(lat, lng, 8)
        except Exception:
            instance.h3_res9 = None
            instance.h3_res8 = None

@receiver(pre_save, sender=PriceReportPhoto)
def normalize_photo_orientation(sender, instance, **kwargs):
    _normalize_uploaded_image_orientation(instance, "image")

class ProductWatchlist(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='watched_products')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='watchers')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'product')

    def __str__(self):
        return f"{self.user.username} watching {self.product.name}"

# Signal to track watchlist additions
@receiver(post_save, sender=ProductWatchlist)
def track_watchlist_analytics(sender, instance, created, **kwargs):
    if created:
        try:
            from wikonomi.analytics.models import track_watchlist_addition
            track_watchlist_addition(instance.user, instance.product)
        except ImportError:
            pass  # Analytics app not yet installed

class Notification(models.Model):
    TYPE_GENERAL = 'general'
    TYPE_COMMENT = 'comment'
    TYPE_REPLY = 'reply'
    TYPE_COMMENT_LIKE = 'comment_like'
    TYPE_DELETION_MARK = 'deletion_mark'
    TYPE_CHOICES = [
        (TYPE_GENERAL, 'General'),
        (TYPE_COMMENT, 'Comment'),
        (TYPE_REPLY, 'Reply'),
        (TYPE_COMMENT_LIKE, 'Comment Like'),
        (TYPE_DELETION_MARK, 'Deletion Mark'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='notifications', null=True, blank=True)
    price_report = models.ForeignKey(PriceReport, on_delete=models.CASCADE, null=True, blank=True)
    business = models.ForeignKey(Business, on_delete=models.CASCADE, null=True, blank=True, related_name='notifications')
    notification_type = models.CharField(max_length=32, choices=TYPE_CHOICES, default=TYPE_GENERAL)
    message = models.CharField(max_length=255)
    is_read = models.BooleanField(default=False)
    muted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Notification for {self.user.username}: {self.message}"


class PriceReportRating(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='price_report_ratings')
    price_report = models.ForeignKey(PriceReport, on_delete=models.CASCADE, related_name='ratings')
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'price_report'],
                name='unique_price_report_rating_per_user',
            ),
        ]
        ordering = ['-updated_at', '-created_at']

    def __str__(self):
        return f"{self.user.username} rated price report #{self.price_report_id}: {self.rating}"


class BusinessRating(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='business_ratings')
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='ratings')
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'business'],
                name='unique_business_rating_per_user',
            ),
        ]
        ordering = ['-updated_at', '-created_at']

    def __str__(self):
        return f"{self.user.username} rated {self.business.name}: {self.rating}"


class PriceLike(models.Model):
    LIKE_NOTIFICATION_THRESHOLDS = [1, 5, 10, 50, 100, 200, 500, 1000]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='price_likes')
    price_report = models.ForeignKey(PriceReport, on_delete=models.CASCADE, related_name='likes')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'price_report')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} liked price report #{self.price_report_id}"


def create_like_threshold_notification(price_report, threshold):
    owner = price_report.user
    template = f"Your price post for {price_report.product.name} reached {threshold} like{'s' if threshold != 1 else ''}."
    if Notification.objects.filter(
        user=owner,
        price_report=price_report,
        muted=True,
        message__startswith=f"Your price post for {price_report.product.name} reached"
    ).exists():
        return
    Notification.objects.get_or_create(
        user=owner,
        product=price_report.product,
        price_report=price_report,
        message=template,
    )

@receiver(post_save, sender=PriceHistory)
def create_price_change_notification(sender, instance, created, **kwargs):
    if created:
        product = instance.price_report.product
        # Temporarily removing .exclude(user=instance.changed_by) so you can test with your own account
        watchers = ProductWatchlist.objects.filter(product=product)
        
        for watch in watchers:
            message = f"Price change alert: {product.name} changed from {instance.old_price} to {instance.new_price} at {instance.price_report.business.name if instance.price_report.business else 'a location'}."
            Notification.objects.create(
                user=watch.user,
                product=product,
                price_report=instance.price_report,
                message=message
            )
        
        # Invalidate relevant caches
        cache.delete(f'nearby_prices_section_{instance.price_report.id}')
        cache.delete(f'price_history_section_{instance.price_report.id}')

@receiver(post_save, sender=PriceReport)
def create_new_price_notification(sender, instance, created, **kwargs):
    if created:
        product = instance.product
        # Temporarily removing .exclude(user=instance.user) so you can test with your own account
        watchers = ProductWatchlist.objects.filter(product=product)
        
        for watch in watchers:
            message = f"New price alert: {product.name} is now {instance.price} at {instance.business.name if instance.business else 'a new location'}."
            Notification.objects.create(
                user=watch.user,
                product=product,
                price_report=instance,
                message=message
            )
        
        # Track price report for analytics
        try:
            from wikonomi.analytics.models import track_price_report
            track_price_report(instance.user)
        except ImportError:
            pass  # Analytics app not yet installed
        
        # Invalidate home feed cache (generic invalidation since it's global)
        # Note: In a production environment with Redis, we'd use a more targeted invalidation
        # For LocMemCache, we can clear common keys
        cache.delete_pattern('home_feed_content_*') if hasattr(cache, 'delete_pattern') else cache.clear()

class ShoppingList(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='shopping_lists')
    name = models.CharField(max_length=255, default="My Shopping List")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.name} ({self.user.username})"

# Signal to track shopping list creation
@receiver(post_save, sender=ShoppingList)
def track_shopping_list_analytics(sender, instance, created, **kwargs):
    if created:
        try:
            from wikonomi.analytics.models import track_shopping_list_creation
            track_shopping_list_creation(instance.user)
        except ImportError:
            pass  # Analytics app not yet installed

class ShoppingListItem(models.Model):
    shopping_list = models.ForeignKey(ShoppingList, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)
    item_name = models.CharField(max_length=255, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    is_checked = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['is_checked', '-created_at']

    def __str__(self):
        return self.item_name or (self.product.name if self.product else "Unknown Item")


class Comment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='legacy_comments')
    price_report = models.ForeignKey(PriceReport, on_delete=models.CASCADE, null=True, blank=True, related_name='comments')
    business = models.ForeignKey(Business, on_delete=models.CASCADE, null=True, blank=True, related_name='comments')
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')
    body = models.TextField(max_length=1200)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Comment by {self.user.username}"
