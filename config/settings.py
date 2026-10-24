import os
import secrets
from datetime import timedelta
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured
BASE_DIR=Path(__file__).resolve().parent.parent
DEBUG=os.environ.get("DJANGO_DEBUG","true").lower() in ("true","1","yes")
SECRET_KEY=os.environ.get("DJANGO_SECRET_KEY")
if not SECRET_KEY:
 if DEBUG: SECRET_KEY=secrets.token_urlsafe(50)
 else: raise ImproperlyConfigured("Set DJANGO_SECRET_KEY before running with DJANGO_DEBUG=false.")
ALLOWED_HOSTS=["127.0.0.1","localhost"]
INSTALLED_APPS=["django.contrib.admin","django.contrib.auth","django.contrib.contenttypes","django.contrib.sessions","django.contrib.messages","django.contrib.staticfiles","corsheaders","rest_framework","rest_framework_simplejwt.token_blacklist","store"]
MIDDLEWARE=["django.middleware.security.SecurityMiddleware","corsheaders.middleware.CorsMiddleware","django.contrib.sessions.middleware.SessionMiddleware","django.middleware.common.CommonMiddleware","django.middleware.csrf.CsrfViewMiddleware","django.contrib.auth.middleware.AuthenticationMiddleware","django.contrib.messages.middleware.MessageMiddleware","django.middleware.clickjacking.XFrameOptionsMiddleware"]
ROOT_URLCONF="config.urls"
TEMPLATES=[{"BACKEND":"django.template.backends.django.DjangoTemplates","DIRS":[],"APP_DIRS":True,"OPTIONS":{"context_processors":["django.template.context_processors.debug","django.template.context_processors.request","django.contrib.auth.context_processors.auth","django.contrib.messages.context_processors.messages"]}}]
WSGI_APPLICATION="config.wsgi.application"
DATABASES={"default":{"ENGINE":"django.db.backends.sqlite3","NAME":BASE_DIR/"db.sqlite3"}}
AUTH_PASSWORD_VALIDATORS=[]
LANGUAGE_CODE="en-us"
TIME_ZONE="Asia/Dhaka"
USE_I18N=True
USE_TZ=True
STATIC_URL="static/"
DEFAULT_AUTO_FIELD="django.db.models.BigAutoField"
CORS_ALLOWED_ORIGINS=["https://t-shoe-bd.vercel.app/","http://localhost:3000"]
CORS_ALLOW_CREDENTIALS = True
REST_FRAMEWORK={
 "DEFAULT_AUTHENTICATION_CLASSES":("rest_framework_simplejwt.authentication.JWTAuthentication",),
 "DEFAULT_PERMISSION_CLASSES":("rest_framework.permissions.AllowAny",),
 "DEFAULT_THROTTLE_CLASSES":("rest_framework.throttling.ScopedRateThrottle",),
 "DEFAULT_THROTTLE_RATES":{"auth":"10/min"},
}
SIMPLE_JWT={
 "ACCESS_TOKEN_LIFETIME":timedelta(minutes=15),
 "REFRESH_TOKEN_LIFETIME":timedelta(days=30),
 "ROTATE_REFRESH_TOKENS":True,
 "BLACKLIST_AFTER_ROTATION":True,
 "AUTH_HEADER_TYPES":("Bearer",),
}
