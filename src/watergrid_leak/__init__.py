"""watergrid-leak — IWA NRW water balance, ILI & Minimum Night Flow burst detector."""

from watergrid_leak.hydraulics import (
    BurstAlert,
    DmaNetworkInput,
    IwaWaterBalanceReport,
    NightFlowSample,
    compute_iwa_water_balance,
    detect_night_flow_bursts,
)

__version__ = "0.1.0"

__all__ = [
    "BurstAlert",
    "DmaNetworkInput",
    "IwaWaterBalanceReport",
    "NightFlowSample",
    "__version__",
    "compute_iwa_water_balance",
    "detect_night_flow_bursts",
]
