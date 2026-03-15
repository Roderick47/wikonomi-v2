"""
Product normalization system for standardizing product names and variations.
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify
from difflib import SequenceMatcher
import re


class ProductAlias(models.Model):
    """
    Maps product name variations to canonical products.
    This enables normalization of user-submitted product names.
    """
    canonical_product = models.ForeignKey(
        'Product', 
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
        unique_together = ('canonical_product', 'alias_name')
        ordering = ['alias_name']
    
    def __str__(self):
        return f"{self.alias_name} → {self.canonical_product.name}"
    
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
        normalized_input = ProductAlias.normalize_text(product_name)
        
        # First try exact alias match
        alias_match = ProductAlias.objects.filter(
            normalized_name=normalized_input,
            is_active=True
        ).first()
        
        if alias_match:
            return alias_match.canonical_product, 1.0
        
        # Try fuzzy matching with existing aliases
        best_match = None
        best_score = 0
        
        for alias in ProductAlias.objects.filter(is_active=True):
            similarity = SequenceMatcher(
                None, 
                normalized_input, 
                alias.normalized_name
            ).ratio()
            
            if similarity > best_score and similarity >= min_similarity:
                best_score = similarity
                best_match = alias.canonical_product
        
        # If no alias match, try direct product matching
        if not best_match:
            from .models import Product
            for product in Product.objects.all():
                product_normalized = ProductAlias.normalize_text(product.name)
                similarity = SequenceMatcher(
                    None, 
                    normalized_input, 
                    product_normalized
                ).ratio()
                
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
        from .models import Product
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
        from .models import PriceReport
        
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
