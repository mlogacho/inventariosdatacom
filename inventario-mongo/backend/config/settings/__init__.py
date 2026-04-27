"""
Inicializador del módulo de configuración.

Orden de importación correcto: base primero, luego dev para sobreescribir.
V-M1 Fix: El orden anterior (dev, base) causaba que base sobreescribiera dev.
"""

from .base import *
from .dev import *
from .mongo import init_mongo

init_mongo()
