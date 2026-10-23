# QUICK START - Production Deployment

## Prerequisites
- Docker and Docker Compose installed
- Git

## 1. Clone & Configure (2 minutes)

```bash
git clone <repository-url>
cd AI-AUTOMATER
cp .env.docker.example .env.docker
```

Edit `.env.docker` and set:
```bash
SECRET_KEY=<generate-with-django>
DB_PASSWORD=<secure-password>
ALLOWED_HOSTS=yourdomain.com,localhost
TEXT_API_KEY=<openai-api-key>
```

Generate SECRET_KEY:
```bash
python3 -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

## 2. Deploy (1 minute)

```bash
docker-compose --env-file .env.docker up -d
```

Wait for services to start (~30 seconds).

## 3. Initialize Database (1 minute)

```bash
# Run migrations
docker-compose exec web python manage.py migrate

# Create admin user
docker-compose exec web python manage.py createsuperuser
```

## 4. Verify (30 seconds)

```bash
# Check all services are running
docker-compose ps

# Test web server
curl http://localhost:8000/

# Check logs
docker-compose logs -f web
```

## 5. Access Application

- **Web Interface:** http://localhost:8000
- **Admin Panel:** http://localhost:8000/admin

## Service Management

```bash
# Stop all services
docker-compose down

# View logs
docker-compose logs -f [web|worker|beat|db|redis]

# Restart a service
docker-compose restart web

# Check service status
docker-compose ps

# Shell access
docker-compose exec web bash
```

## Background Tasks

Campaign execution happens automatically via Celery Beat:
- **Frequency:** Checks every 60 seconds for due campaigns
- **Worker:** Processes generation tasks asynchronously
- **Beat:** Schedules periodic tasks

View worker logs:
```bash
docker-compose logs -f worker
docker-compose logs -f beat
```

## Troubleshooting

**Services won't start:**
```bash
docker-compose logs
# Check for port conflicts or missing env vars
```

**Database connection failed:**
```bash
docker-compose exec db psql -U postgres -d ai_content_automater_prod
# Verify database exists
```

**Worker not processing:**
```bash
docker-compose exec web celery -A content_automater inspect active
# Check worker status
```

**Reset everything:**
```bash
docker-compose down -v  # WARNING: Deletes all data
docker-compose up -d
docker-compose exec web python manage.py migrate
```

## Production Checklist

- [ ] SECRET_KEY is randomly generated (50+ characters)
- [ ] DB_PASSWORD is secure and unique
- [ ] ALLOWED_HOSTS includes your domain
- [ ] TEXT_API_KEY is set for AI generation
- [ ] SSL/TLS certificate configured (if exposed to internet)
- [ ] Regular database backups scheduled
- [ ] Firewall configured (only ports 80/443 exposed)
- [ ] Environment variables stored securely (not in git)

## Backup & Restore

**Backup database:**
```bash
docker-compose exec db pg_dump -U postgres ai_content_automater_prod > backup.sql
```

**Restore database:**
```bash
cat backup.sql | docker-compose exec -T db psql -U postgres ai_content_automater_prod
```

## Updating

```bash
git pull origin main
docker-compose build
docker-compose up -d
docker-compose exec web python manage.py migrate
```

## Support

- **Documentation:** `docs/development/`
- **Completion Report:** `docs/development/V1-100-PERCENT-COMPLETION-REPORT.md`
- **README:** `README.md`

---

**Total Setup Time:** ~5 minutes  
**Status:** Production Ready ✅
