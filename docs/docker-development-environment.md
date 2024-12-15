# Docker Development Environment

Copy the environment configuration file:

```sh
cp .env.example .env
```

Edit `.env` and set your passwords and API keys:

```
POSTGRES_PASSWORD=your_password_here
STRIPE_SECRET_KEY=your_key_here
STRIPE_PUBLISHABLE_KEY=your_key_here
MAILGUN_API_KEY=your_key_here
```

Run:

```sh
docker compose up --build
```

This will boot up everything that Modernomad needs to run, and stay running in the terminal.

In another console, run these commands to set up the database and set up a user:

```sh
docker compose run django ./manage.py migrate
```

Your docker image is now running with your local development code. Browse to
`http://localhost:8000/` to access your running image. You can run any of the other
`manage.py` commands in the same way. E.g., to run the test suite:

```sh
docker compose run django ./manage.py test
```

The first time you get this going, you will want to generate some test data:

```sh
docker compose run django ./manage.py generate_test_data
```

This will create a superuser with the credentials `admin` and `password`.

You only need to run these commands once. Wen you want to work on the development
environment in the future, just run `docker compose up --build`. (Note: `--build` is
optional, but means that the Python and Node dependencies will always remain up-to-date.)

## Configuration

You can configure environment variables using the `.env.example` file.

Copy the example:

```sh
cp .env.example .env
```

And then edit `.env` at will.

To learn about what can be configured, see the [configuration documentation](configuration.md).

## Shell access

You can access a Django shell using:

```sh
docker compose run --rm django python manage.py shell
```

`--rm` means that the container will be deleted after exit.

## Debugging

You can add a `breakpoint()` in your Python code and step into the code. To do this
you need to attach to the django docker container.

Run this and get the first column, the container ID:

```sh
docker ps|grep modernomad-django
```

Then, run this in a separate terminal:

```sh
docker attach <container-id>
# eg. docker attach ee8e1887e766
```

Now, this new terminal will give you input if the code encounters a breakpoint.

## Reset docker setup

If you want to reset everything (and delete all local database data), run:

```sh
# stop containers
docker compose stop

# remove containers
docker compose down

# remove volume -- THIS WILL DELETE ALL LOCAL DATA
docker volume rm modernomad_pgdata
```
