## Define Login and Google Authentication 
Note: style will be set after the functionality is working
### Initial Django Setup
1. Add django-allauth

```bash
uv django-allauth
uv add PyJWT
uv add cryptography
```

2. Add to urls:
```bash
2.4 URLs
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
]

```
This provides:
- /accounts/login/
- /accounts/logout/
- /accounts/password_reset/
- etc.

3. Add the following in settings.py - This is setting up some Google options, which will come in the next step.

To applications:
```bash
    "django.contrib.sites",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
```
To middleware:
```bash
    'allauth.account.middleware.AccountMiddleware',
```


```bash
SITE_ID = 1

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "SCOPE": [
            "profile",
            "email",
        ],
        "AUTH_PARAMS": {
            "access_type": "online",
        },
        "OAUTH_PKCE_ENABLED": True,
    }
}


LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

ACCOUNT_AUTHENTICATION_METHOD = "email"
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_EMAIL_VERIFICATION = "optional"

SOCIALACCOUNT_LOGIN_ON_GET = True

LOGIN_URL = '/accounts/login/' 

CSRF_TRUSTED_ORIGINS = [
    "https://jautolog.jaycurtis.org",
]
```

4. Update urls.py
```bash

from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path('accounts/', include('allauth.urls')),
    ...
]

```


### Google Cloud Configuration
1. Create OAuth Credentials


- Google Cloud Console → APIs & Services → Credentials:  https://console.cloud.google.com/apis/credentials
    - Create OAuth Client ID
    - Application type: Web
    - Authorized redirect URI:
        - Examples:
            - http://localhost:8005/accounts/google/login/callback/
            - https://jautolog.jaycurtis.org/accounts/google/login/callback/
            - http://jautolog.jaycurtis.org/accounts/google/login/callback/
    - Save values:
        - Client Id
        - Client Secret

2. Configure Google Provider in Django

2.1 Update Settings (previously done)

2.2 Database Configuration
Run migrations:
```bash
uv run manage.py migrate
```
Create a superuser:
``` bash
uv run manage.py createsuperuser
```

2.3 Register Google App in Django Admin

```bash
uv run manage.py runserver
```

Log into /admin
- Go to Social Applications
- Add a new Social App:
    - Provider: Google
    - Name: Google
    - Client ID: (from Google Cloud)
    - Secret: (from Google Cloud)
    - Sites: add your site



### Restricted Pages
The easiest and safest way to restrict access is to use a decorator on all views that need authentication.  Potentially this can
be done with middleware, but can be harder to tweak.  This is straight forward and can easily give public access to certain pages

Example of decorator:
```bash
from django.contrib.auth.decorators import login_required 


@login_required
def home(request):
    ...
```