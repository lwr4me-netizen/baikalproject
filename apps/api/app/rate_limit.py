"""Единый экземпляр rate limiter, используемый и в main.py, и в роутерах."""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
