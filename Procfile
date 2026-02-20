web: gunicorn flask_app:app --workers 1 --threads 4 --timeout 300
worker: rq worker --url $REDIS_URL --ssl-cert-reqs none default
