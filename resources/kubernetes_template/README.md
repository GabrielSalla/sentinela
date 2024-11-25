# Kubernetes template
The files in this directory are a template for a Kubernetes deployment. They were tested using a `minikube` environment.

## Steps to deploy Sentinela in a local kubernetes environment
**1. Build the image and add it to `minikube`**
```bash
make build-local
minikube image load sentinela-local
```

**2. Create the config map and secrets**
```bash
kubectl apply -f config_map.yaml
kubectl apply -f secrets.yaml
```

**3. Create the PostgreSQL database**
```bash
kubectl apply -f postgres.yaml
```

**4. Run the migrations in the database**
```bash
kubectl run migration-shell --rm -i --tty --image sentinela-local:latest --image-pull-policy Never -- /bin/sh
```

When the pod starts, run the following command.
```bash
alembic upgrade head
```

**5. Create the Controller service**
```bash
kubectl apply -f controller.yaml
```

**6. Create the Executor service**
```bash
kubectl apply -f executor.yaml
```
