import os

os.environ["DEBUG"] = "1"
os.environ.pop("REDIS_URL", None)
os.environ["DATABASE_URL"] = "sqlite://:memory:"

from .settings import *  # noqa: E402,F401,F403

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]  # fast tests
