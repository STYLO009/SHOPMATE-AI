# Public deployment

This deployment serves the website and API on one HTTPS origin. Caddy obtains and renews the TLS certificate; Postgres and Redis stay on the private Compose network. Only ports 80 and 443 are exposed publicly.

## Before starting

1. Provision a Linux VPS with Docker Engine and the Docker Compose plugin.
2. Point the domain's DNS A/AAAA records to the VPS and allow inbound TCP 80/443 (UDP 443 is optional for HTTP/3).
3. Copy `.env.public.example` to `.env` on the VPS. Set `PUBLIC_DOMAIN`, `PUBLIC_BASE_URL`, and `CORS_ORIGINS` to the actual domain, and replace both database passwords and `SECRET_KEY`. Keep the database URL password URL-encoded if it contains reserved characters.
4. Add approved Amazon Creators API and/or Flipkart Affiliate credentials to `.env` if available. Keep `.env` private and out of source control.

## Start

From the project root:

```sh
docker compose --env-file .env -f docker-compose.public.yml up -d --build
```

Check service health and logs:

```sh
docker compose --env-file .env -f docker-compose.public.yml ps
docker compose --env-file .env -f docker-compose.public.yml logs -f backend caddy
```

The public site is `PUBLIC_BASE_URL`; the public read-only API routes are `/api/offers/search?query=...` and `/api/offers/featured`. There is no need to expose the backend port directly. The public Deals page reports an empty feed until at least one retailer integration is configured and authorized.

For Google sign-in, add the deployed callback URL to the Google OAuth client. For ongoing operation, back up the Postgres volume and keep the affiliate feeds and website compliant with their current program terms.
