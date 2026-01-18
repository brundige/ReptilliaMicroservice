# adapters/outlets/__init__.py

"""
Outlet controller adapters for power management.
"""

from .kasa import KasaOutletController, KasaConnectionError

__all__ = ["KasaOutletController", "KasaConnectionError"]