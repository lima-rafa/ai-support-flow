"""Configuração via ambiente: não carregar credenciais no repositório."""
import os
from pathlib import Path


def db_path():
    return Path(os.getenv('DATABASE_PATH', './data/asf.sqlite'))


def service_key():
    return os.getenv('ASF_INTERNAL_SERVICE_KEY', '')
