"""CLI for watergrid-leak."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from watergrid_leak.hydraulics import (
    DmaNetworkInput,
    NightFlowSample,
    compute_iwa_water_balance,
    detect_night_flow_bursts,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="watergrid-leak",
        description="IWA Non-Revenue Water (NRW) balance, ILI & Minimum Night Flow burst detector.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("demo", help="Run a municipal DMA water-balance & night-flow burst detection demo")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "demo":
        bal = compute_iwa_water_balance(
            DmaNetworkInput(
                dma_id="DMA-KAMPALA-NORTH-04",
                system_input_m3_per_day=2400.0,
                billed_authorized_m3_per_day=1350.0,
                unbilled_authorized_m3_per_day=50.0,
                apparent_losses_m3_per_day=220.0,
                mains_length_km=42.0,
                service_connections=3200,
                avg_operating_pressure_m=32.0,
            )
        )
        samples = [
            NightFlowSample(f"2026-11-{d:02d}", 18.0 + (d % 2) * 0.4, 34.0) for d in range(10, 18)
        ] + [NightFlowSample("2026-11-18", 29.5, 29.0)]
        alerts = detect_night_flow_bursts(samples)
        print(
            json.dumps(
                {
                    "dma_id": bal.dma_id,
                    "nrw_pct": bal.nrw_pct,
                    "ili": bal.ili,
                    "world_bank_band": bal.world_bank_band,
                    "annual_direct_cost_usd": bal.annual_direct_cost_usd,
                    "burst_alerts": [
                        {
                            "date": a.date_iso,
                            "excess_m3_hr": a.excess_m3_per_hr,
                            "pressure_drop_m": a.pressure_drop_m,
                            "severity": a.severity,
                        }
                        for a in alerts
                    ],
                },
                indent=2,
            )
        )
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
