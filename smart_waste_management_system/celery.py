# smart_waste_management_system/celery.py
import os
from celery import Celery
from django.conf import settings

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "smart_waste_management_system.settings")

app = Celery("smart_waste_management_system")
app.config_from_object("django.conf:settings", namespace="CELERY")

app.conf.enable_utc = False
app.conf.timezone = "Europe/Athens"

app.autodiscover_tasks()