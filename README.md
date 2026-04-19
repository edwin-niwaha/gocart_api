#GoCart API
python manage.py runserver 0.0.0.0:8000
celery -A core worker -l info -P solo