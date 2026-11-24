"""IWA Water Balance, Infrastructure Leakage Index (ILI) & Minimum Night Flow (MNF) burst detector."""

from __future__ import annotations

import statistics
from dataclasses import dataclass


@dataclass(frozen=True)
class DmaNetworkInput:
    """District Metered Area (DMA) water-utility balance & network geometry."""

    dma_id: str
    system_input_m3_per_day: float
    billed_authorized_m3_per_day: float
    unbilled_authorized_m3_per_day: float
    apparent_losses_m3_per_day: float  # Meter under-registration + unauthorized consumption
    mains_length_km: float  # Lm
    service_connections: int  # Nc
    avg_operating_pressure_m: float  # P (meters of water head)
    avg_private_pipe_m: float = 0.0  # Lp (km total = Nc * avg_private_pipe_m / 1000)
    production_cost_usd_per_m3: float = 0.45


@dataclass(frozen=True)
class IwaWaterBalanceReport:
    dma_id: str
    nrw_m3_per_day: float
    nrw_pct: float
    real_losses_m3_per_day: float  # CARL (m3/day)
    uawl_m3_per_day: float  # UARL (Unavoidable Annual Real Losses, m3/day)
    ili: float  # Infrastructure Leakage Index = CARL / UARL
    world_bank_band: str  # A (<=2) | B (2-4) | C (4-8) | D (>8) for developing-country benchmarks
    annual_lost_water_m3: float
    annual_direct_cost_usd: float


@dataclass(frozen=True)
class NightFlowSample:
    date_iso: str
    mnf_m3_per_hr: float  # 02:00-04:00 Minimum Night Flow
    pressure_m: float


@dataclass(frozen=True)
class BurstAlert:
    date_iso: str
    mnf_m3_per_hr: float
    baseline_mnf_m3_per_hr: float
    excess_m3_per_hr: float
    z_score: float
    pressure_drop_m: float
    severity: str  # critical | high


def compute_iwa_water_balance(dma: DmaNetworkInput) -> IwaWaterBalanceReport:
    """Compute IWA Standard Water Balance, UARL (Lambert et al., 1999), and ILI."""
    if dma.system_input_m3_per_day <= 0 or dma.avg_operating_pressure_m <= 0:
        raise ValueError("system_input_m3_per_day and avg_operating_pressure_m must be > 0")

    nrw = max(0.0, dma.system_input_m3_per_day - dma.billed_authorized_m3_per_day)
    nrw_pct = (nrw / dma.system_input_m3_per_day) * 100.0
    total_losses = max(0.0, nrw - dma.unbilled_authorized_m3_per_day)
    carl_m3_day = max(0.0, total_losses - dma.apparent_losses_m3_per_day)

    # IWA UARL formula (liters/day): (18*Lm + 0.80*Nc + 25*Lp) * P
    lp_km = (dma.service_connections * dma.avg_private_pipe_m) / 1000.0
    uarl_liters_day = (18.0 * dma.mains_length_km + 0.80 * dma.service_connections + 25.0 * lp_km) * (
        dma.avg_operating_pressure_m
    )
    uarl_m3_day = max(0.001, uarl_liters_day / 1000.0)
    ili = carl_m3_day / uarl_m3_day

    # World Bank Institute developing-country ILI performance bands
    if ili < 4.0:
        band = "A (Good)"
    elif ili < 8.0:
        band = "B (Potential for improvement)"
    elif ili < 16.0:
        band = "C (Poor - active leakage control needed)"
    else:
        band = "D (Critical - inefficient resource use)"

    annual_lost = carl_m3_day * 365.0
    return IwaWaterBalanceReport(
        dma_id=dma.dma_id,
        nrw_m3_per_day=round(nrw, 2),
        nrw_pct=round(nrw_pct, 2),
        real_losses_m3_per_day=round(carl_m3_day, 2),
        uawl_m3_per_day=round(uarl_m3_day, 2),
        ili=round(ili, 2),
        world_bank_band=band,
        annual_lost_water_m3=round(annual_lost, 1),
        annual_direct_cost_usd=round(annual_lost * dma.production_cost_usd_per_m3, 2),
    )


def detect_night_flow_bursts(
    samples: list[NightFlowSample],
    *,
    baseline_window: int = 7,
    z_threshold: float = 3.0,
    min_excess_m3_hr: float = 2.0,
) -> list[BurstAlert]:
    """Detect emerging main breaks from rolling Minimum Night Flow (02:00-04:00) & pressure drops."""
    if len(samples) <= baseline_window:
        return []
    alerts: list[BurstAlert] = []
    for i in range(baseline_window, len(samples)):
        win = samples[i - baseline_window : i]
        cur = samples[i]
        flows = [s.mnf_m3_per_hr for s in win]
        pressures = [s.pressure_m for s in win]
        med_flow = statistics.median(flows)
        mad = statistics.median([abs(x - med_flow) for x in flows])
        robust_std = max(0.25, 1.4826 * mad)
        excess = cur.mnf_m3_per_hr - med_flow
        z = excess / robust_std
        p_drop = max(0.0, statistics.median(pressures) - cur.pressure_m)

        if z >= z_threshold and excess >= min_excess_m3_hr:
            sev = "critical" if (z >= 5.0 or p_drop >= 3.0) else "high"
            alerts.append(
                BurstAlert(
                    date_iso=cur.date_iso,
                    mnf_m3_per_hr=round(cur.mnf_m3_per_hr, 2),
                    baseline_mnf_m3_per_hr=round(med_flow, 2),
                    excess_m3_per_hr=round(excess, 2),
                    z_score=round(z, 2),
                    pressure_drop_m=round(p_drop, 2),
                    severity=sev,
                )
            )
    return alerts
