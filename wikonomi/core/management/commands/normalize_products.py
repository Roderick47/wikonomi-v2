from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from core.models import Product, ProductAlias, ProductNormalizationService, ProductMatcher
from difflib import SequenceMatcher
import sys

class Command(BaseCommand):
    help = 'Normalize existing products by identifying duplicates and creating aliases'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes',
        )
        parser.add_argument(
            '--min-similarity',
            type=float,
            default=0.8,
            help='Minimum similarity threshold for matching (default: 0.8)',
        )
        parser.add_argument(
            '--interactive',
            action='store_true',
            help='Ask for confirmation before each merge',
        )
    
    def handle(self, *args, **options):
        dry_run = options['dry_run']
        min_similarity = options['min_similarity']
        interactive = options['interactive']
        
        self.stdout.write(self.style.SUCCESS('Starting product normalization...'))
        
        # Get all products
        products = list(Product.objects.all())
        self.stdout.write(f'Found {len(products)} products to analyze')
        
        if not products:
            self.stdout.write(self.style.WARNING('No products found'))
            return
        
        # Group similar products
        product_groups = self.find_similar_products(products, min_similarity)
        
        if not product_groups:
            self.stdout.write(self.style.SUCCESS('No similar products found'))
            return
        
        self.stdout.write(f'Found {len(product_groups)} groups of similar products')
        
        # Process each group
        for group in product_groups:
            self.process_product_group(group, dry_run, interactive)
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - No changes made'))
        else:
            self.stdout.write(self.style.SUCCESS('Product normalization completed'))
    
    def find_similar_products(self, products, min_similarity):
        """Find groups of similar products"""
        processed = set()
        groups = []
        
        for i, product1 in enumerate(products):
            if product1.id in processed:
                continue
                
            current_group = [product1]
            processed.add(product1.id)
            
            for j, product2 in enumerate(products[i+1:], i+1):
                if product2.id in processed:
                    continue
                    
                # Calculate similarity
                similarity = SequenceMatcher(
                    None, 
                    ProductAlias.normalize_text(product1.name),
                    ProductAlias.normalize_text(product2.name)
                ).ratio()
                
                if similarity >= min_similarity:
                    current_group.append(product2)
                    processed.add(product2.id)
            
            if len(current_group) > 1:
                groups.append(current_group)
        
        return groups
    
    def process_product_group(self, group, dry_run, interactive):
        """Process a group of similar products"""
        self.stdout.write(f'\n--- Group of {len(group)} similar products ---')
        
        # Display products in the group
        for i, product in enumerate(group, 1):
            price_count = product.price_reports.count()
            alias_count = product.aliases.count()
            self.stdout.write(f'{i}. "{product.name}" (ID: {product.id}) - {price_count} price reports, {alias_count} aliases')
        
        # Find the best candidate for canonical product
        canonical = self.select_canonical_product(group)
        self.stdout.write(f'Selected canonical: "{canonical.name}" (ID: {canonical.id})')
        
        if interactive or dry_run:
            action = 'MERGE' if not dry_run else 'WOULD MERGE'
            self.stdout.write(f'{action}: The following products would become aliases of "{canonical.name}":')
            
            for product in group:
                if product != canonical:
                    self.stdout.write(f'  - "{product.name}" → "{canonical.name}"')
            
            if interactive:
                response = input(f'Proceed with merge? (y/N): ').strip().lower()
                if response != 'y':
                    self.stdout.write('Skipped')
                    return
        
        if not dry_run:
            self.merge_products(group, canonical)
            self.stdout.write(self.style.SUCCESS(f'Merged {len(group)-1} products into "{canonical.name}"'))
    
    def select_canonical_product(self, group):
        """Select the best canonical product from a group"""
        # Prefer the product with:
        # 1. Most price reports
        # 2. Shortest name (more canonical)
        # 3. Oldest creation date
        
        best_product = None
        best_score = -1
        
        for product in group:
            price_count = product.price_reports.count()
            name_length = len(product.name)
            
            # Score: more price reports is better, shorter name is better
            score = price_count * 100 - name_length
            
            if score > best_score:
                best_score = score
                best_product = product
        
        return best_product
    
    def merge_products(self, group, canonical):
        """Merge a group of products, keeping canonical as the main one"""
        # Get or create a user for system operations
        system_user, _ = User.objects.get_or_create(
            username='system',
            defaults={'is_staff': True}
        )
        
        for product in group:
            if product == canonical:
                continue
            
            # Create alias for the merged product
            ProductAlias.objects.get_or_create(
                canonical_product=canonical,
                alias_name=product.name,
                defaults={'created_by': system_user}
            )
            
            # Move any existing aliases
            ProductAlias.objects.filter(
                canonical_product=product
            ).update(canonical_product=canonical)
            
            # Update price reports
            from core.models import PriceReport
            PriceReport.objects.filter(
                product=product
            ).update(product=canonical)
            
            # Delete the merged product
            product.delete()
        
        self.stdout.write(f'Successfully merged {len(group)-1} products into "{canonical.name}"')
