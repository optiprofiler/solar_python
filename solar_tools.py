try:
    from .solar_python_tools import solar_collect_info, solar_load, solar_select
except ImportError:
    from solar_python_tools import solar_collect_info, solar_load, solar_select

__all__ = ["solar_collect_info", "solar_load", "solar_select"]
