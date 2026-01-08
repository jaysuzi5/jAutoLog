## PostgreSQL Setup
There are a number of ways to setup Postgres between development and production.  For small databases, I am going to go with a shared Postgresql
instance.  I have Postgresql running locally on my development machine and will have one decicated instance on my Kubernettes cluster.  I have
other applications that will have their own stand-alone instance of Postgresql, but for these, for this, it will just have a new database within
a shared instance.


### Local Postgresql Instructions:
1. Install Posgresql if not already installed
```bash
brew install postgresql
```

2. If installed but services are not running, restart them
```bash
brew services restart postgresql
```

3. Create the database:
```bash
CREATE DATABASE jautolog;
```

4. List the databases
```bash
\l
```

5. Connecte with pgAdmin
Register -> Server
- Name: local
- Host: localhost
- Port: 5432
- Database: postgres
- Username: <<username>>
- Password: <<password>>



### Setup Django
1. Add Postgres Library
```bash
uv add psycopg2-binary
uv add django-environ
```

2. Define the environment variables:
```bash
POSTGRES_DB=jautolog
POSTGRES_USER=<<user>>
POSTGRES_PASSWORD=<<password>>
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
```

3. Update settings.py
```bash
import environ
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env()
environ.Env.read_env(os.path.join(BASE_DIR, '.env'))

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': env('POSTGRES_DB'),
        'USER': env('POSTGRES_USER'),
        'PASSWORD': env('POSTGRES_PASSWORD'),
        'HOST': env('POSTGRES_HOST'),
        'PORT': env('POSTGRES_PORT'),
    }
}
```

4. Delete the existing db.sqlite3
* IMPORTANT: This will remove all data that you have entered so far *

5. Rerun the migrate:
```bash
uv run python manage.py migrate
```

6. You can check that tables were created by reviewing the database in pgAdmin

7. You will need recreate the superuser
``` bash
uv run manage.py createsuperuser
```

Note: If done out of order, you will need to recreate the Google Authentication
8. Register Google App in Django Admin

```bash
uv run manage.py runserver localhost:8005 
```

Log into /admin
- Go to Social Applications
- Add a new Social App:
    - Provider: Google
    - Name: Google
    - Client ID: (from Google Cloud)
    - Secret: (from Google Cloud)
    - Sites: add your site


### Kubernettes Postgresql Instructions:

1. See homelab for details instructions on how this was created in Kubernettes
https://github.com/jaysuzi5/home-lab/tree/main/cluster/infrastructure/databases/postgresql/postgresql

2. Exec into the pod
```bash
k exec -it postgresql-1 -n postgresql -- bash
```

3. Create the database:
```bash
CREATE DATABASE jautolog;
```

4. List the databases
```bash
\l
```

5. Need a new secret as Kubernettes can not have cross namespace secrets


5.1 temp.yaml for the secret in the format:
```bash
apiVersion: v1
data:
  password: <base64-encoded-password>
  username: <base64-encoded-username>
kind: Secret
metadata:
  creationTimestamp: "2026-01-01T14:20:41Z"
  name: jautolog
  namespace: jautolog
type: Opaque
```


5.2 encoded the values with:
```bash
echo -n "<actual value>" | base64 
```

5.3 Then sealed the secret with:
```bash
kubeseal -f temp.yaml -o yaml > secrets.yaml  
```

5.4 Apply the secret with:
```bash
k apply -f secrets.yaml  
```

6. Update the environment variables for the K8s deployment
```bash
            # Database
            - name: POSTGRES_DB
              value: "jautolog"
            - name: POSTGRES_HOST
              value: "postgresql-rw.postgresql.svc.cluster.local"
            - name: POSTGRES_PORT
              value: "5432"
            - name: POSTGRES_USER
              valueFrom:
                secretKeyRef:
                  name: postgresql
                  key: username
            - name: POSTGRES_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: postgresql
                  key: password

```

7. Rebuild the Docker image with all of the changes:
```bash
docker buildx build --platform linux/amd64,linux/arm64 -t jaysuzi5/jautolog:latest --push .
```

8. Apply the new manifest
```bash
k apply -f deployment.yaml
```


### Migrate, Superuser, Static Files, and Google Authentication
Since we are starting from a clean database, we need to reapply some settings

1. Connect to the pod
```bash
kubectl exec -n jautolog -it jautolog-659dc656df-fcr4v -- /bin/sh
```

2. Run the migrate
```bash
python manage.py migrate
```

3. Create a super user
```bash
python manage.py createsuperuser
```

4. At this point, it was observerved that the admin screens did not have the static files.  Therefore the following needed to be done:

4.1  Add whitenoise
```bash
uv add whitenoise
```

4.2 Update settings
Middleware... the order is important
```bash
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    ...
]
```

Optionally, but can add compression:
```bash
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
```

4.3 Build image and restart
```bash
docker buildx build --platform linux/amd64,linux/arm64 -t jaysuzi5/jautolog:latest --push .
kubectl rollout restart deployment jautolog -n jautolog
```


Note: Need to re-register the Google Authentication as the database is new in production
5. Register Google App in Django Admin

Log into /admin
- Go to Social Applications
- Add a new Social App:
    - Provider: Google
    - Name: Google
    - Client ID: (from Google Cloud)
    - Secret: (from Google Cloud)
    - Sites: add your site

### Logging Authenticated User
Now that all authentication and logging are in place, the logging can be updated to include the authenticated user.  These
changes are made to the middleware.py 

Add new method:
```bash
    def _get_user_context(self, request):
        user = getattr(request, "user", None)

        if user and user.is_authenticated:
            return {
                "user_id": user.id,
                "username": user.get_username(),
                "is_authenticated": True,
            }

        return {
            "user_id": None,
            "username": None,
            "is_authenticated": False,
        }
```

Update __call__ to call the new method
```bash
    def __call__(self, request):
        ...
        user_context = self._get_user_context(request)

        # Log request
        logger.info(json.dumps({
            ...
            "user": user_context,
            ...
        }))

        try:
            response = self.get_response(request)
            status_code = response.status_code
            response_body = self._get_response_body(response)
        except Exception as e:
            # Log exception
            stack_trace = traceback.format_exc()
            logger.error(json.dumps({
                ...
                "user": user_context,
                ...
            }))
            raise

        # Log response
        elapsed_time = time.time() - start_time
        logger.info(json.dumps({
            ...
            "user": user_context,
            ...
        }))

        return response
```


### Backup
There will be two levels of backup: On to the local NAS and daily to S3.  There will be a generic S3 bucket and user for the S3 connectivity, however the secrets will need to be added to the secrets in the current namespace.

1. Seal the secrets:
1.1 temp.yaml for the secret in the format:
```bash
apiVersion: v1
data:
  password: <base64-encoded-password>
  username: <base64-encoded-username>
  AWS_ACCESS_KEY_ID: <base64-encoded-username>
  AWS_SECRET_ACCESS_KEY: <base64-encoded-username>
  AWS_STORAGE_BUCKET_NAME: <base64-encoded-username> 
kind: Secret
metadata:
  creationTimestamp: "2026-01-01T14:20:41Z"
  name: jautolog
  namespace: jautolog
type: Opaque
```


1.2 encoded the values with:
```bash
echo -n "<actual value>" | base64 
```

1.3 Then sealed the secret with:
```bash
kubeseal -f temp.yaml -o yaml > secrets.yaml  
```

1.4 Apply the secret with:
```bash
k apply -f secrets.yaml  
```

2. Create and apply the backup-pvc.yaml

3. Create and apply the cronjob-backup.yaml

