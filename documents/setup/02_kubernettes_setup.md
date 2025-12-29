## 2. Dockerize the App

### Lock the packages

```bash
uv lock
```
This creates
pyproject.toml
uv.lock

### Dockerfile

```dockerfile
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && \
    apt-get install -y curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

ADD https://astral.sh/uv/install.sh /install.sh
RUN sh /install.sh && rm /install.sh
ENV PATH="/root/.local/bin:${PATH}"

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY . .

EXPOSE 8000

# This is the correct module name for your layout
CMD ["uv", "run", "gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]
```

ADD gunicorn TO pyproject.toml as a dependency


### Build & Push Multi-Architecture Docker Image

```bash
docker buildx build --platform linux/amd64,linux/arm64 -t jaysuzi5/jautolog:latest --push .
```

---

## 3. Deploy to Kubernetes

### Kubernetes Deployment + LoadBalancer Service

`deployment.yaml`

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: jautolog
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: jautolog
  namespace: jautolog
  labels:
    app: jautolog
spec:
  replicas: 1
  selector:
    matchLabels:
      app: jautolog
  template:
    metadata:
      labels:
        app: jautolog
    spec:
      containers:
        - name: jautolog
          image: jaysuzi5/jautolog:latest
          imagePullPolicy: Always
          ports:
            - containerPort: 8000
---
apiVersion: v1
kind: Service
metadata:
  name: jautolog
  namespace: jautolog
spec:
  type: LoadBalancer
  selector:
    app: jautolog
  ports:
    - port: 80
      targetPort: 8000

```

### Apply the manifest

```bash
kubectl apply -f deployment.yaml
```

### Verify LoadBalancer IP

```bash
kubectl get all -n jautolog
```

Access the app at the `EXTERNAL-IP` provided by MetalLB:

```
http://<EXTERNAL-IP>/
```

### Redeploy
```bash
kubectl rollout restart deployment jautolog -n jautolog
```


## 4. Expose via CloudFlare
CloudFlare Zero Trust setup:
1. https://one.dash.cloudflare.com/
2. Networks -> Connectors : Click on Existing Tunnel -> Edit
3. Published application routes -> "Add a published appllication route"
	
      Subdomain: jautolog
  	  
      Domain: jaycurtis.org
	    
      Type: HTTP
  	  
      URL: jautolog.jautolog.svc.cluster.local:80	

4. Test Site: https://jautolog.jaycurtis.org/