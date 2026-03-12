# Scaling Guide — 1000+ Concurrent Users

## Quick Start (Production)

### 1. Install Redis
```bash
sudo apt install redis-server
sudo systemctl enable redis-server
```

### 2. Install production dependencies
```bash
pip install -r requirements-prod.txt
```

### 3. Set environment variables
```bash
export DJANGO_SECRET_KEY="your-real-secret-key-here"
export DJANGO_DEBUG="False"
export REDIS_URL="redis://127.0.0.1:6379/1"
export CHANNEL_LAYER_BACKEND="channels_redis.core.RedisChannelLayer"
export REDIS_HOST="127.0.0.1"
export REDIS_PORT="6379"
export DB_CONN_MAX_AGE="60"
```

### 4. Run migrations (for new DB indexes)
```bash
python manage.py makemigrations dashboard
python manage.py migrate
```

### 5. Deploy
```bash
# HTTP (Gunicorn — 4 workers)
gunicorn abacus_site.wsgi:application --workers 4 --bind 0.0.0.0:8000

# WebSocket (Daphne)
daphne -b 0.0.0.0 -p 8001 abacus_site.asgi:application
```

## What Changed
- Redis caching for dashboard metrics and sessions
- Redis channel layer for WebSocket notifications (env-controlled)
- Database indexes on frequently queried fields
- UUID-based roll numbers (no more DB loops)
- Cached default teacher lookup
- DB connection pooling (CONN_MAX_AGE)
- Optimized dashboard metric queries (Exists subquery)

## Dev Mode
Without setting any env variables, everything works exactly like before (InMemory channels, local cache, same SECRET_KEY). No breaking changes.
