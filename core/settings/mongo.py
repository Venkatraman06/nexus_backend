from decouple import config

MONGO_HOST = config("MONGO_HOST", default="localhost")
MONGO_PORT = config("MONGO_PORT", default=27017, cast=int)
MONGO_NAME = config("MONGO_NAME", default="pmt")
MONGO_USER = config("MONGO_USER", default="")
MONGO_PASSWORD = config("MONGO_PASSWORD", default="")
