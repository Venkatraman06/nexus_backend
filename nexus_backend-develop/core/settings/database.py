from decouple import config

USE_SQLITE = config("USE_SQLITE", default=False, cast=bool)

try:
    import psycopg2
    HAS_POSTGRES = not USE_SQLITE
except ImportError:
    try:
        import psycopg
        HAS_POSTGRES = not USE_SQLITE
    except ImportError:
        HAS_POSTGRES = False

if HAS_POSTGRES:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": config("DB_NAME", default="pmt_db"),
            "USER": config("DB_USER", default="postgres"),
            "PASSWORD": config("DB_PASSWORD", default=""),
            "HOST": config("DB_HOST", default="localhost"),
            "PORT": config("DB_PORT", default="5432"),
            "OPTIONS": {
                "connect_timeout": 10,
            },
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": "db.sqlite3",
        }
    }


