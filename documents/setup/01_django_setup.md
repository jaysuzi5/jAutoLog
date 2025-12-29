### 1. Create a new project directory
```bash
mkdir myproject
cd myproject
```

### 2. Initialize a uv project (creates pyproject.toml)
```bash
uv init
```

This creates:
pyproject.toml

A default virtual environment under .venv/

### 3. Add Django using uv
Instead of pip install django, use:
```bash
uv add django
```

This writes Django to your pyproject.toml and installs it into .venv.
To verify:
uv pip list | grep Django

### 4. Create a Django project
Use uv to run the Django admin tool from your env:

```bash
uv run django-admin startproject config .
```

This creates the standard Django folder structure:

config/
    settings.py
    urls.py
    wsgi.py
manage.py

### 5. Run the development server
```bash
uv run python manage.py migrate
uv run python manage.py runserver
```


### 6. Add an application
```bash
uv run manage.py startapp autolog
uv run manage.py startapp conversion
```

### Project structure

```
jautolog/
├─ manage.py
├─ config/
│  ├─ settings.py
│  ├─ urls.py
│  └─ wsgi.py
└─ autlog/
   ├─ views.py
   └─ templates/autolog/home.html
└─ conversion/
   ├─ views.py
   └─ templates/conversion/conversion.html
```

### Add `autolog` to `INSTALLED_APPS` in `settings.py`

```python
INSTALLED_APPS = [
    ...
    'autolog',
    'conversion',
]
```

### Create a simple view

`autolog/views.py`

```python
from django.shortcuts import render

def home(request):
    return render(request, "autolog/home.html")
```

### Template

`autolog/templates/autolog/home.html`

```html
<!DOCTYPE html>
<html>
<head>
    <title>My Simple Page</title>
</head>
<body>
    <h1>Hello from Django!</h1>
    <p>This is a single-page app.</p>
</body>
</html>
```

### URLs

`autolog/urls.py`

```python
from django.urls import path
from .views import home

urlpatterns = [
    path("", home, name="autlog"),
]
```

Link app URLs in `config/urls.py`:

```python
from django.contrib import admin
from django.urls import path
from autolog.views import home
from conversion.views import conversion

urlpatterns = [
    path("", home, name="home"),
    path("conversion/", conversion, name="conversion"),
    path("admin/", admin.site.urls),
]
```