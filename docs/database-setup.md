# Local PostgreSQL setup

GridSight runs PostgreSQL 17 in Docker Compose. Docker provides the database
runtime only; Python, SQL, Power BI, and Excel remain the project's main tools.

## Configure local credentials

Create the ignored local environment file once:

```powershell
Copy-Item .env.example .env
notepad .env
```

Replace `replace_with_a_local_password` with a local password. Keep `.env`
outside Git and never add the real password to documentation or screenshots.

## Start PostgreSQL

From the repository root:

```powershell
docker compose config --quiet
docker compose up -d postgres
docker compose ps
```

The first start downloads the image. Continue only when the service status is
`healthy`.

## Verify PostgreSQL inside the container

```powershell
docker compose exec postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT current_database(), current_user;"'
docker compose exec postgres postgres --version
```

The query must show the `gridsight` database and user. The second command must
show a PostgreSQL 17 server version.

## Stop and restart

Stop the database without deleting its data:

```powershell
docker compose stop postgres
```

Start it again:

```powershell
docker compose up -d postgres
```

`docker compose down` removes the container and network but preserves the named
volume. Do not use `docker compose down --volumes` unless the local database is
intentionally being destroyed.
