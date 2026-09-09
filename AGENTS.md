# GEMINI.md

This file provides guidance to Gemini Code (gemini.ai/code) when working with code in this repository.

## Project Overview

Django Template is a comprehensive template for Django projects with the following features:
- Multi-language support
- Advanced text editing
- Background processing
- Testing and quality
- Code quality
- Development rules and standards

## Architecture Overview

### Django App Structure
- **apps/core/** - Base models, utilities, and shared functionality
- **apps/authentication/** - Custom user authentication and signup flows
- **apps/users/** - User management with custom user model
- **apps/dashboard/** - Analytics and dashboard views

### Settings Configuration

Environment-specific settings in `config/settings/`:
- `base.py` - Shared configuration
- `development.py` - Local development (SQLite)
- `production.py` - Production (PostgreSQL, Cloudinary, Sentry)
- `testing.py` - Test environment

## Key Features

### Advanced Text Editing
- **Multi-language support**: English/Spanish interface

## Development Notes

### API Layer
Django REST Framework endpoints available, primarily for internal AJAX operations.

### Internationalization
Basic i18n support configured with locale files in `locale/`.

### Testing
Comprehensive test suite with Factory Boy for test data generation. Coverage reports available in `htmlcov/` directory.

### Database

- PostgreSQL in production (psycopg-binary)
- SQLite for development (fallback)
- Migrations stored in each app's migrations/ directory

### Background Tasks

- Celery for asynchronous tasks
- Redis as message broker
- Django Celery Beat for scheduled tasks

### Code Quality

- Pre-commit hooks with Ruff linter and formatter
- Coverage reporting for tests
- Django extensions for development utilities

## Development Rules and Standards

### Python Development Principles

#### Code Quality and Best Practices
- **Code in English**: Write all code comments, documentation, and variable names in English to ensure consistency and clarity.
- **Code Reviews**: Conduct regular code reviews to ensure adherence to coding standards and best practices
- **DRY Principle**: Avoid code duplication by abstracting repeated logic into reusable functions or components
- **SOLID Principles**:
  - **Single Responsibility**: Each function or class should have only one reason to change
  - **Open/Closed**: Code should be open for extension but closed for modification
  - **Liskov Substitution**: Subtypes should be substitutable for their base types without altering correctness
  - **Interface Segregation**: Prefer small, specific interfaces over large, general ones
  - **Dependency Inversion**: Depend on abstractions, not concretions

#### Programming Paradigms
- **Functional Programming**: Use pure functions and avoid side effects where possible
- **Object-Oriented Programming**: Encapsulate behavior and data within classes, adhering to SOLID principles

#### Semantic Naming and Abstractions
- **Descriptive Names**: Use meaningful names for variables, functions, and classes to improve readability
- **Abstraction**: Create abstractions to hide complex logic and expose only necessary details

### Python Coding Standards

#### Type Annotations and Documentation
- **ALWAYS** add typing annotations to each function or class
- Include return types when necessary
- Add descriptive docstrings to all Python functions and classes using **PEP 257** convention
- Update existing docstrings when modifying code
- Keep any existing comments in files

#### Project Structure
- Modular design with distinct files for models, views, forms and others.
- Configuration management using environment variables, constants or django-constance by case
- Robust error handling and logging, including context capture

#### Testing Requirements
- **Use Django's built-in unittest framework** for this project
- All tests should have typing annotations
- All tests should be in `apps/*/tests/` directories
- Create all necessary files and folders, including `__init__.py` files
- All tests should be fully annotated and contain docstrings
- Comprehensive testing with Django TestCase classes
- Coverage requirement: 85% minimum
- Use factories for test data generation
- Apply user authentication and permission logic in tests

#### Development Tools
- Dependency management via pip and virtual environments
- Code style consistency using Ruff
- AI-friendly coding practices for clarity and AI-assisted development

### Django-Specific Guidelines

#### Core Principles
- Write clear, technical responses with precise Django examples
- Use Django's built-in features and tools wherever possible
- Prioritize readability and maintainability following Django's coding style guide (PEP 8 compliance)
- Use descriptive variable and function names with proper naming conventions
- Structure project in a modular way using Django apps for reusability and separation of concerns

#### Views and Architecture
- Use Django's class-based views (CBVs) for complex views
- Prefer function-based views (FBVs) for simpler logic
- Follow the MVT (Model-View-Template) pattern strictly for clear separation of concerns
- Keep business logic in models and forms; keep views light and focused on request handling
- **Use custom mixins**: When generating new class-based views, ALWAYS consider and use the reusable mixins defined in `apps/core/mixins/` (e.g., `BaseCreateView`, `BaseUpdateView`, `BaseListView` from `apps/core/mixins/views.py`) to avoid redundant view logic.

#### Service Layer (Business Logic)

- **Encapsulate business logic in service modules**, never in views or models directly
- Services live in `apps/*/services.py` (or `apps/*/services/` for complex modules)
- Services are plain Python classes or functions — no Django view/model inheritance
- Views are responsible only for HTTP handling; they delegate to services
- Services receive and return Python objects/dataclasses, not HTTP request/response

**Naming convention**:
- Classes: `{Entity}Service` → `OrderService`, `InvoiceService`
- Methods: verb + noun → `create_order()`, `calculate_total()`, `send_notification()`

**Structure example**:
```python
# apps/orders/services.py
from apps.users import models as users_models
from apps.orders import models

class OrderService:
    """Handles all business logic related to orders."""

    def create_order(self, user: users_models.User, items: list[dict]) -> models.Order:
        """
        Creates a new order and calculates totals.

        Args:
            user: The authenticated user placing the order.
            items: List of item dicts with 'product_id' and 'quantity'.

        Returns:
            OrderResult with the created order and computed total.
        """
        # business logic here
        ...
```

**Integration with views**:
```python
# apps/orders/views.py
from apps.orders import services

class OrderCreateView(LoginRequiredMixin, View):
    def post(self, request):
        service = services.OrderService()
        result = service.create_order(request.user, items=request.POST)
        ...
```

#### Database and ORM
- Leverage Django's ORM for database interactions
- Avoid raw SQL queries unless necessary for performance
- Use Django's built-in user model and authentication framework
- Optimize query performance using `select_related` and `prefetch_related`
- Implement database indexing and query optimization techniques

#### Forms and Validation
- Utilize Django's form and model form classes for form handling and validation
- Use Django's validation framework to validate form and model data
- Implement error handling at the view level using Django's built-in mechanisms
- Prefer try-except blocks for handling exceptions in business logic and views

#### Security and Best Practices
- Apply Django's security best practices (CSRF protection, SQL injection protection, XSS prevention)
- Use Django signals to decouple error handling and logging from core business logic
- Use middleware judiciously for cross-cutting concerns (authentication, logging, caching)
- Follow Django's "Convention Over Configuration" principle

#### Performance Optimization
- Use Django's cache framework with backend support (Redis)
- Implement asynchronous views and background tasks (via Celery) for I/O-bound operations
- Optimize static file handling with Django's static file management system
- Leverage Django's caching framework for frequently accessed data

#### Testing and Quality
- Use Django's built-in testing framework (unittest-based TestCase classes)
- Ensure code quality and reliability through comprehensive testing
- Use factory_boy for test data generation in each module
- Test categories: models, views, forms, API, tasks, reports
- Include user authentication and permission testing scenarios

## Frontend and UI Guidelines

### Theme and Styling
- **Theme**: Using TailAdmin with Tailwind CSS in vanilla HTML, CSS, and JavaScript
- **Templates**: Django templates with Jinja syntax
- **Icons**: Use Font Awesome for consistent iconography
- **Form Styling**: Display form fields using Django form variables and apply styles via `add_class` from `widget_tweaks` library

### Form Handling Example
```python
# In templates, use widget_tweaks to apply styling if not applied in the form settings.
{{ form.field_name|add_class:"form-control" }}
{{ form.email|add_class:"form-control form-control-lg" }}
```

## Import Standards and Module Organization

### Internal Module Imports
- **Same Module**: Import directly from module components
```python
from apps.xxx import choices, factories, models, views
```

- **Different Modules**: Use aliases to avoid naming conflicts
```python
from apps.xxx import models as xxx_models
from apps.yyy import forms as yyy_forms
```

### Date and Time Handling
- **Always use Django's timezone module** for date and time logic
```python
from django.utils import timezone

# Get current time
now = timezone.now()

# Make timezone aware
aware_datetime = timezone.make_aware(naive_datetime)
```

### Factory Usage in Tests
- **Each module should have its own factories** for test data generation
- Use factories consistently across all test files
```python
# apps/xxx/factories.py
import factory
from django.contrib.auth import get_user_model
from apps.xxx import models

class XxxFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = models.Xxx

    nombre = factory.Faker('name')
    email = factory.Faker('email')
```

### User Authentication and Permissions in Tests
- **User Login Setup**: Use factory-created users with forced login
```python
from apps.users import factories
from django.test import TestCase

class MyTestCase(TestCase):
    def setUp(self):
        self.user = factories.UserFactory()
        self.client.force_login(self.user)
```

- **Permission Management**: Apply specific permissions for testing user interactions
```python
from django.contrib.auth.models import Permission
from django.test import TestCase

class PermissionTestCase(TestCase):
    def setUp(self):
        self.user = factories.UserFactory()
        # Add specific permissions
        permissions = Permission.objects.filter(
            codename__in=["view_empleado", "add_empleado", "change_empleado", "delete_empleado"]
        )
        self.user.user_permissions.add(*permissions)
        self.client.force_login(self.user)

    def test_user_can_access_with_permissions(self):
        response = self.client.get('/nomina/empleados/')
        self.assertEqual(response.status_code, 200)
```
