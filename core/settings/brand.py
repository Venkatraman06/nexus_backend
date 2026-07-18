from decouple import config

FRONTEND_APP_URL = config("FRONTEND_APP_URL", default="http://localhost:3000/pmt").rstrip("/")
COMPANY_NAME = config("COMPANY_NAME", default="Hackers Infotech")
COMPANY_SHORT_NAME = config("COMPANY_SHORT_NAME", default="HackerInfotech")
SUPPORT_EMAIL = config("SUPPORT_EMAIL", default="hr@hackersinfotech.com")

OTP_EXPIRY_MINUTES = config("OTP_EXPIRY_MINUTES", default=10, cast=int)
OTP_MAX_ATTEMPTS = config("OTP_MAX_ATTEMPTS", default=5, cast=int)
RESET_TOKEN_EXPIRY_MINUTES = config("RESET_TOKEN_EXPIRY_MINUTES", default=15, cast=int)
ONBOARD_TOKEN_EXPIRY_HOURS = config("ONBOARD_TOKEN_EXPIRY_HOURS", default=72, cast=int)

PASSWORD_MIN_LENGTH = config("PASSWORD_MIN_LENGTH", default=8, cast=int)
