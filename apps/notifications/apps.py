from django.apps import AppConfig
from .firebase import initialize_firebase

class NotificationsConfig(AppConfig):
    name = "apps.notifications"


    def ready(self):
        from .firebase import initialize_firebase
        initialize_firebase()