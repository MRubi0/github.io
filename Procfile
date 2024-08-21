web: gunicorn LetsTourTec.wsgi:application --log-file - --bind 0.0.0.0:$PORT --timeout 600
worker: celery -A LetsTourTec worker --loglevel=info 

