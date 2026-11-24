"""Tests for IWA water balance, UARL/ILI formula, Minimum Night Flow burst detection & CLI."""

from __future__ import annotations

import json

import pytest

from watergrid_leak import (
    DmaNetworkInput,
    NightFlowSample,
    compute_iwa_water_balance,
    detect_night_flow_bursts,
)
from watergrid_leak.cli import main as cli_main


def test_iwa_uarl_and_ili_match_lambert_formula() -> None:
    # Lm=50km, Nc=2500, Lp=0, P=40m -> UARL = (18*50 + 0.8*2500)*40 / 1000 = (900 + 2000)*40/1000 = 116.0 m3/day
    rep = compute_iwa_water_balance(
        DmaNetworkInput(
            dma_id="DMA-1",
            system_input_m3_per_day=1000.0,
            billed_authorized_m3_per_day=600.0,
            unbilled_authorized_m3_per_day=20.0,
            apparent_losses_m3_per_day=32.0,
            mains_length_km=50.0,
            service_connections=2500,
            avg_operating_pressure_m=40.0,
        )
    )
    assert rep.uawl_m3_per_day == 116.0
    assert rep.real_losses_m3_per_day == 348.0
    assert rep.ili == 3.0
    assert rep.world_bank_band.startswith("A")


def test_night_flow_burst_detector_flags_pipe_break_with_pressure_drop() -> None:
    baseline = [NightFlowSample(f"2026-11-{d:02d}", 12.0 + (d % 2) * 0.2, 35.0) for d in range(1, 9)]
    burst = [*baseline, NightFlowSample("2026-11-09", 24.5, 29.5)]
    alerts = detect_night_flow_bursts(burst)
    assert len(alerts) == 1
    assert alerts[0].severity == "critical"
    assert alerts[0].pressure_drop_m >= 5.0


def test_cli_demo(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli_main(["demo"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["nrw_pct"] > 40.0
    assert len(out["burst_alerts"]) == 1
