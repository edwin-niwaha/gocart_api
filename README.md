#GoCart API
python manage.py runserver 0.0.0.0:8000


$env:DJANGO_SETTINGS_MODULE="core.settings.development"
celery -A core worker -l info -P solo


python manage.py test --settings=core.settings.testing -v 2