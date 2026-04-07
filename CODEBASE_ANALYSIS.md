# WIKONOMI v2 - Django Project Codebase Analysis

## Project Overview
WIKONOMI v2 is a Django-based price comparison and crowdsourcing platform that allows users to report and track product prices across different businesses and locations. The project implements a comprehensive system for product normalization, business management, and price tracking with geographical features.

## Technology Stack

### Core Framework
- **Django 5.0+** - Main web framework
- **PostgreSQL** - Primary database (configured for production on Render)
- **SQLite** - Development database (db.sqlite3 present)

### Key Dependencies
- `django-allauth[socialaccount]` - Authentication with social login support
- `django-taggit` - Product tagging system
- `h3` - Geospatial indexing and hexagonal grid system
- `django-storages[s3]` + `boto3` - Cloud storage integration (Cloudflare R2)
- `Pillow` + `django-resized` - Image processing and resizing
- `whitenoise` - Static file serving
- `gunicorn` - Production WSGI server
- `psycopg2-binary` - PostgreSQL adapter
- `dj-database-url` - Database URL configuration

## Project Structure

```
WIKONOMI v2/
├── .env.example                    # Environment variables template
├── .gitignore                      # Git ignore rules
├── requirements.txt                 # Python dependencies
├── manage.py                       # Django management script (customized)
├── build.sh / start.sh             # Build and deployment scripts
├── wikonomi/                       # Main Django project directory
│   ├── manage.py                   # Django management entry point
│   ├── wikonomi/                   # Project configuration
│   │   ├── __init__.py
│   │   ├── settings.py             # Main settings (production-ready)
│   │   ├── local.py                # Development settings
│   │   ├── production.py           # Production-specific settings
│   │   ├── urls.py                 # Root URL configuration
│   │   ├── wsgi.py / asgi.py       # WSGI/ASGI entry points
│   │   └── __pycache__/
│   ├── core/                       # Core application (main business logic)
│   │   ├── models.py               # Core data models (34KB - largest file)
│   │   ├── views.py                # Main views (52KB - second largest)
│   │   ├── urls.py                 # Core URL routing
│   │   ├── admin.py                # Admin interface configuration
│   │   ├── utils.py                # Utility functions
│   │   ├── product_normalization.py # Product name normalization
│   │   ├── context_processors.py   # Template context data
│   │   ├── templatetags/           # Custom template tags
│   │   ├── templates/              # Core templates
│   │   ├── migrations/             # Database migrations (16 files)
│   │   ├── management/             # Custom management commands
│   │   └── tests/                  # Comprehensive test suite
│   ├── users/                      # User management application
│   │   ├── models.py               # User profile models
│   │   ├── views.py                # User-related views
│   │   ├── forms.py                # User forms
│   │   ├── utils.py                # User utilities
│   │   ├── templates/              # User templates
│   │   └── migrations/             # User migrations
│   └── analytics/                  # Analytics application
│       ├── models.py               # Analytics data models
│       ├── views.py                # Analytics views
│       ├── admin.py                # Analytics admin
│       └── migrations/             # Analytics migrations
├── venv/                           # Virtual environment
├── media/                          # User-uploaded media files
└── test_*.py                       # Standalone test files
```

## Application Architecture

### 1. Core Application (`core/`)
The heart of the system containing the main business logic:

#### Key Models:
- **Product** - Core product entity with tagging, categories, and images
- **ProductAlias** - Product name normalization and variant mapping
- **Business** - Business/store information
- **BusinessBranch** - Individual business locations/branches
- **PriceReport** - User-submitted price reports
- **PriceHistory** - Historical price tracking
- **Notification** - User notification system
- **ShoppingList/ShoppingListItem** - User shopping lists
- **ProductWatchlist** - Price tracking for specific products

#### Key Features:
- **Product Normalization Service** - Intelligent product name matching and normalization
- **Business Normalization Service** - Business name and location normalization
- **Geospatial Integration** - H3 hexagonal indexing for location-based queries
- **Image Processing** - Automatic image resizing and optimization
- **Comprehensive Search** - Advanced product and business search functionality

### 2. Users Application (`users/`)
Handles user authentication, profiles, and user-specific features:
- Extended user profiles
- User preferences and settings
- User-specific data management

### 3. Analytics Application (`analytics/`)
Provides data analysis and reporting capabilities:
- Price trend analysis
- Business performance metrics
- User activity tracking

## Configuration Highlights

### Database Configuration
- **Production**: PostgreSQL on Render with connection pooling
- **Development**: SQLite for local development
- **Environment-aware** configuration via `manage.py`

### Storage Configuration
- **Production**: Cloudflare R2 via S3-compatible API
- **Development**: Local filesystem storage
- **CDN Integration**: `media.wikonomi.com` for production media

### Authentication System
- Django-allauth with social login (Google OAuth2 configured)
- Email verification system
- Anonymous user support for price reporting

### Security Features
- CSRF protection
- Security headers middleware
- Environment-based secret key management
- SSL/HTTPS enforcement in production

## Key Technical Features

### 1. Product Normalization System
- **Intelligent Matching**: Uses text normalization, pattern matching, and similarity algorithms
- **Component Extraction**: Separates product names from sizes/quantities
- **Alias Management**: Maps product variants to canonical products
- **Signature-based Matching**: Pattern-based product identification

### 2. Geospatial Capabilities
- **H3 Integration**: Hexagonal grid system for efficient spatial queries
- **Location-based Search**: Find prices by geographic area
- **Business Branching**: Multi-location business support

### 3. Advanced Search
- **Full-text Search**: Product and business search with relevance ranking
- **Filter System**: Category, price range, location filtering
- **Autocomplete**: Real-time search suggestions

### 4. Performance Optimizations
- **Database Indexing**: Strategic indexes on frequently queried fields
- **Caching**: Django cache framework implementation
- **Image Optimization**: Automatic resizing and compression
- **Pagination**: Efficient data pagination for large datasets

## Testing Infrastructure

### Comprehensive Test Suite
- **Unit Tests**: Model and utility function testing
- **Integration Tests**: View and workflow testing
- **Performance Tests**: Load and performance testing
- **Security Tests**: Security vulnerability testing
- **Normalization Tests**: Product/business normalization testing

### Standalone Test Files
- `test_normalization_suite.py` - Comprehensive normalization testing
- `test_search_functionality.py` - Search system testing
- `test_business_branches.py` - Business branching tests
- `test_product_normalization.py` - Product normalization tests

## Deployment Configuration

### Production Ready Features
- **Render Deployment**: Pre-configured for Render platform
- **Environment Variables**: Comprehensive environment-based configuration
- **Static File Handling**: WhiteNoise middleware for efficient static serving
- **Media Storage**: Cloudflare R2 integration for scalable media storage
- **Database Migration**: Automated migration support

### Development Setup
- **Local Development**: SQLite database with local settings
- **Virtual Environment**: Isolated Python environment
- **Debug Mode**: Enhanced debugging and error reporting

## Areas for Code Review

### 1. Security Considerations
- Secret key management (currently hardcoded in settings)
- Google OAuth credentials visibility
- Database connection string exposure
- Input validation and sanitization

### 2. Performance Optimization
- Database query optimization opportunities
- Caching strategy enhancement
- Large file handling (models.py, views.py are quite large)
- Memory usage optimization

### 3. Code Organization
- File size considerations (some files exceed 20KB)
- Potential for further modularization
- Utility function organization
- Template structure optimization

### 4. Testing Coverage
- Test coverage analysis
- Integration test completeness
- Edge case handling
- Performance test adequacy

## Recommendations for Claude AI Analysis

When analyzing this codebase, focus on:

1. **Architecture Patterns**: Evaluate the Django app structure and separation of concerns
2. **Database Design**: Review the relational model and indexing strategy
3. **Security Assessment**: Analyze authentication, authorization, and data protection
4. **Performance Review**: Identify bottlenecks and optimization opportunities
5. **Code Quality**: Assess maintainability, readability, and best practices
6. **Testing Strategy**: Evaluate test coverage and quality
7. **Scalability Considerations**: Review how the system handles growth
8. **Deployment Readiness**: Assess production configuration and deployment strategy

This codebase represents a mature, production-ready Django application with sophisticated features for price tracking, normalization, and geospatial analysis. The architecture demonstrates good separation of concerns and comprehensive functionality for a crowdsourcing price comparison platform.
