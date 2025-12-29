## Setup
This describes the setup for an Django application that will proper logging, running on my local Kubernettes cluster, and being exposed to the internet


### [01: Initial creation of a Django project with applications](01_django_setup.md)
Details on how to setup Django with uv, including multiple applications

### [02. Deployment to Kubernetes cluster](02_kubernettes_setup.md)
Details the steps of building the Docker image and deploying the a local Kubernettes cluster.  Includes step for exposing via Cloudflare

### [03. Enable Open Telememetry traces, metrics and logs](03_otel_setup.md)
Details on how to setup Open Telemetry.  This will assume that a collector is already in place.

### 04. Enable PostgreSQL Database
Define a postgress database instance instead of the sqlite.  Also defines backups when running on the Kubernettes cluster

### 05. Enable Super User on Kubernettes
Define the steps to setup the Super User when pushed to the Kubernettes cluster
