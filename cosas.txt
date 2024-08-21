web: gunicorn LetsTourTec.wsgi:application --log-file - --bind 0.0.0.0:$PORT --worker-class=gevent --workers=2 --timeout 600
worker: celery -A LetsTourTec worker --loglevel=info --concurrency=2 --max-tasks-per-child=100

