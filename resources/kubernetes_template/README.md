# Kubernetes template
The files in this directory are a template for a Kubernetes deployment. They were tested using a `minikube` environment.

## Steps to deploy Sentinela in a local kubernetes environment
**1. Build the image and add it to `minikube`**
```bash
make build-local
minikube image load sentinela-local
```

**2. Create the config map and secrets**
Fill the missing secrets in the `secrets.yaml` file before applying it.

```bash
kubectl apply -f config_map.yaml
kubectl apply -f secrets.yaml
```

**3. Create the Motoserver AWS mock**
```bash
kubectl apply -f motoserver.yaml
```

**4. Create the PostgreSQL database**
```bash
kubectl apply -f postgres.yaml
```

**5. Run the migrations in the database**
The pod must have the environment variable `DATABASE_APPLICATION` defined to be able to run the migrations.

```bash
kubectl run migration-shell --rm -i --tty --image sentinela-local:latest --image-pull-policy Never -- /bin/sh
```

When the pod starts, run the following command.
```bash
alembic upgrade head
```

**6. Create the Controller service**
```bash
kubectl apply -f controller.yaml
```

**7. Create the Executor service**
```bash
kubectl apply -f executor.yaml
```

**8. Cleaning up**
```bash
kubectl delete -f controller.yaml
kubectl delete -f executor.yaml
kubectl delete -f motoserver.yaml
kubectl delete -f postgres.yaml
kubectl delete -f secrets.yaml
kubectl delete -f config_map.yaml
```
