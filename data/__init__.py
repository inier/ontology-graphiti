"""Backward compatibility shim for data module.

.. deprecated::
    Import from odap.biz.simulator.data_generator instead.
"""
# 直接使用同目录下的 simulation_data.py，不从 odap.biz 导入避免循环依赖
from .simulation_data import generate_simulation_data, load_simulation_data

__all__ = ['generate_simulation_data', 'load_simulation_data']
