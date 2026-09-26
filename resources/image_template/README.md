# Image template
The `Dockerfile` file in this directory is a template for a recipe to build a production ready image of Sentinela.

## Example repository structure
To have a personalized image to your deployment, create a repository of your own and use the [Dockerfile](./Dockerfile) to build the image. It downloads the requested Sentinela release using the specified tag from GitHub and installs the dependencies your configuration defines.

A typical repository looks like this:

```
your-repo/
├── Dockerfile        # Use `resources/image_template/Dockerfile` as a reference
├── configs.yaml      # Your configuration
├── monitors/         # Your monitors
│   ├── my_monitor
│   │   └── my_monitor.py
│   └── ...
└── README.md
```

With a custom config name, the argument `USER_CONFIG` must be changed to match:

```
your-repo/
├── Dockerfile
├── my-configs.yaml
└── ...
```

## Steps to build the image without cloning Sentinela and push it to ECR
The `Dockerfile` in this directory downloads Sentinela from GitHub at build time.
Build it from your repository, not from a Sentinela checkout.

**1. Prepare the build context in your repository**
Copy this `Dockerfile` into your repo alongside your own config file (see structure above).

**2. Build the image**
```bash
docker build -t sentinela:0.8.8 .
```

To use a config file with a different name:
```bash
docker build --build-arg USER_CONFIG=my-configs.yaml -t sentinela:0.8.8 .
```

**3. Push the image**
After building the image it can be used in a production environment. The previous example built the image with the tag `sentinela:0.8.8` that can be used directly or pushed to a cloud registry.

## Running migrations
Migrate DB before first start and after updates. Same image contains `alembic` + `migrations/`. The `DATABASE_APPLICATION` variable must be available.

```bash
docker run --rm sentinela:0.8.8 alembic upgrade head
```
