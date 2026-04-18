#!/usr/bin/env python3
"""
NAME: tri_band_roaming_report.py

PURPOSE:
    This script reads roaming event CSV files from a specified directory (one CSV per client device),
    detects individual roam events by clustering Authentication frames (frame_type column), computes
    management roam time (first Authentication frame to last EAPOL frame), and generates an HTML/PDF
    report with per-client tables using the lf_report module.

    Roam Detection:
        Authentication frames are extracted, deduplicated by (timestamp, sa, da), sorted by time,
        and clustered: a gap of more than AUTH_GAP_THRESHOLD (1.0 seconds) between consecutive
        Authentication frames marks the start of a new roam event.

    Management Roam Time:
        For each detected roam, EAPOL frames (eapol == 1) are searched in a time window from the
        first Authentication frame to last Authentication frame + 2.0 seconds.
        - If EAPOL frames are found: mgmt_roam_time = (last_eapol_timestamp - first_auth_timestamp) * 1000 ms
        - If no EAPOL frames: mgmt_roam_time = "N/A"

EXAMPLE:
    python3 tri_band_roaming_report.py --csv_dir ./three_node_roaming/

    python3 tri_band_roaming_report.py --csv_dir ./three_node_roaming/ --output_path /tmp/roam_reports

NOTES:
    1. Each CSV file in --csv_dir represents one client device. The filename (without extension)
       is used as the client name in the report.
    2. The pcap_name column encodes the roam segment and iteration, e.g. 'P1-P15_1' means
       segment P1 to P15, iteration 1.
    3. Use './tri_band_roaming_report.py --help' to see all options.
"""

import os
import sys
import glob
import argparse
import importlib
import pandas as pd
import logging

sys.path.append(os.path.join(os.path.abspath(__file__ + "../../")))

lf_report_module = importlib.import_module("lf_report")
lf_report = lf_report_module.lf_report

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

AUTH_GAP_THRESHOLD = (
    1.0  # seconds – gap between consecutive auth frames to start a new roam
)


def parse_pcap_name(pcap_name):
    """Parse pcap_name like 'P1-P15_1' into (from_point, to_point, iteration)."""
    parts = pcap_name.rsplit("_", 1)
    iteration = int(parts[1]) if len(parts) == 2 else 1
    segment = parts[0]
    seg_parts = segment.split("-", 1)
    from_point = seg_parts[0] if len(seg_parts) == 2 else segment
    to_point = seg_parts[1] if len(seg_parts) == 2 else ""
    return from_point, to_point, iteration


def extract_roam_events(df):
    """Detect roam events from raw frame data and compute management roam time.

    Algorithm:
        1. Group by pcap_name
        2. For each group, extract Authentication frames and deduplicate by (timestamp, sa, da)
        3. Cluster consecutive auth frames: gap > AUTH_GAP_THRESHOLD = new roam
        4. For each roam cluster, search for EAPOL frames in [first_auth, last_auth + 2.0s]
        5. Compute mgmt_roam_time_ms or "N/A" if no EAPOL frames found

    Returns a list of dicts, one per detected roam event.
    """
    events = []
    grouped = df.groupby("pcap_name", sort=False)

    for pcap_name, group in grouped:
        # Get Authentication frames
        auth_frames = group[group["frame_type"] == "Authentication"].copy()
        if auth_frames.empty:
            continue

        # Deduplicate by (timestamp, sa, da) – same physical frame may appear with different roam_index
        auth_frames = auth_frames.drop_duplicates(subset=["timestamp", "sa", "da"])
        auth_frames = auth_frames.sort_values("timestamp").reset_index(drop=True)

        # Cluster auth frames by time gap
        timestamps = auth_frames["timestamp"].astype(float).values
        clusters = []  # list of lists of row indices into auth_frames
        current_cluster = [0]
        for i in range(1, len(timestamps)):
            if timestamps[i] - timestamps[i - 1] > AUTH_GAP_THRESHOLD:
                clusters.append(current_cluster)
                current_cluster = [i]
            else:
                current_cluster.append(i)
        clusters.append(current_cluster)

        # For each cluster, build a roam event
        from_point, to_point, iteration = parse_pcap_name(str(pcap_name))

        for cluster_indices in clusters:
            cluster_rows = auth_frames.iloc[cluster_indices]
            first_auth_time = float(cluster_rows["timestamp"].min())
            last_auth_time = float(cluster_rows["timestamp"].max())

            # Look up metadata from the original group row matching the first auth frame
            first_auth_row = cluster_rows.iloc[0]
            original_match = group[
                (group["timestamp"] == first_auth_row["timestamp"])
                & (group["sa"] == first_auth_row["sa"])
                & (group["da"] == first_auth_row["da"])
            ]
            meta_row = (
                original_match.iloc[0] if not original_match.empty else first_auth_row
            )

            # Search for EAPOL frames in the time window
            eapol_window = group[
                (group["eapol"] == 1)
                & (group["timestamp"].astype(float) >= first_auth_time)
                & (group["timestamp"].astype(float) <= last_auth_time + 10.0)
            ]

            if not eapol_window.empty:
                last_eapol_time = float(eapol_window["timestamp"].max())
                mgmt_roam_time_ms = round((last_eapol_time - first_auth_time) * 1000, 2)
            else:
                mgmt_roam_time_ms = "N/A"

            events.append(
                {
                    "pcap_name": pcap_name,
                    "roam_segment": f"{from_point} -> {to_point}",
                    "iteration": iteration,
                    "client_mac": meta_row.get("client_mac", ""),
                    "from_ap": meta_row.get("from_ap", ""),
                    "to_ap": meta_row.get("to_ap", ""),
                    "roam_type": meta_row.get("roam_type", ""),
                    "band": meta_row.get("band", ""),
                    "mgmt_roam_time_ms": mgmt_roam_time_ms,
                }
            )

    return events


def generate_report(csv_dir, output_path):
    csv_files = sorted(glob.glob(os.path.join(csv_dir, "*.csv")))
    if not csv_files:
        logger.error("No CSV files found in %s", csv_dir)
        sys.exit(1)

    logger.info(
        "Found %d CSV file(s): %s",
        len(csv_files),
        [os.path.basename(f) for f in csv_files],
    )

    # Load and process all CSVs
    all_clients = {}
    for csv_file in csv_files:
        client_name = os.path.splitext(os.path.basename(csv_file))[0].replace("_", " ")
        logger.info("Processing %s (%s)", client_name, csv_file)
        df = pd.read_csv(csv_file)
        events = extract_roam_events(df)
        all_clients[client_name] = events
        logger.info("  -> %d roam events detected", len(events))

    # Initialize report
    report = lf_report(
        _output_pdf="roaming_report.pdf",
        _output_html="roaming_report.html",
        _results_dir_name="roaming_report",
        _path=output_path,
    )
    report_path = report.get_path_date_time()
    logger.info("Report output directory: %s", report_path)

    # Banner
    report.set_title("Three Node Roaming Report")
    report.build_banner()

    # Objective
    report.set_table_title("Objective:")
    report.build_table_title()
    report.set_text(
        "The objective is to analyze WiFi roaming performance across a three-node AP topology. "
        "For each client device, roam events are detected from Authentication frame sequences in "
        "the capture data. Management roam time is measured from the first Authentication frame to "
        "the last EAPOL frame of each roam event. If no EAPOL frames are present, management roam "
        "time is reported as N/A."
    )
    report.build_text_simple()

    # Per-client sections
    for client_name, events in all_clients.items():
        if not events:
            continue

        report.set_table_title(f"Roaming Results - {client_name}")
        report.build_table_title()

        table_data = []
        for e in events:
            table_data.append(
                {
                    "Pcap Name": e["pcap_name"],
                    "Roam Segment": e["roam_segment"],
                    "Iteration": e["iteration"],
                    "Client MAC": e["client_mac"],
                    "From DUT MAC": e["from_ap"],
                    "To DUT MAC": e["to_ap"],
                    "Roam Type": e["roam_type"],
                    "Band": e["band"],
                    "Mgmt Roam Time (ms)": e["mgmt_roam_time_ms"],
                }
            )

        table_df = pd.DataFrame(table_data)
        report.set_table_dataframe(table_df)
        report.build_table()

    # Cross-client comparison
    if len(all_clients) > 1:
        report.set_table_title("Cross-Client Roaming Comparison")
        report.build_table_title()
        report.set_text(
            "Summary of roaming events and average management roam time per client device."
        )
        report.build_text_simple()

        comparison_data = []
        for client_name, events in all_clients.items():
            total = len(events)
            mgmt_vals = [
                e["mgmt_roam_time_ms"]
                for e in events
                if e["mgmt_roam_time_ms"] != "N/A"
            ]
            eapol_count = len(mgmt_vals)
            avg_mgmt = round(sum(mgmt_vals) / len(mgmt_vals), 2) if mgmt_vals else "N/A"
            comparison_data.append(
                {
                    "Client": client_name,
                    "Total Roams": total,
                    "Roams with EAPOL": eapol_count,
                    "Avg Mgmt Roam Time (ms)": avg_mgmt,
                }
            )

        comparison_df = pd.DataFrame(comparison_data)
        report.set_table_dataframe(comparison_df)
        report.build_table()

    report.generate_report()
    logger.info("Report generated at: %s", report_path)


def main():
    parser = argparse.ArgumentParser(
        prog="tri_band_roaming_report.py",
        formatter_class=argparse.RawTextHelpFormatter,
        description="Generate a Three Node Roaming Report from CSV files.",
    )
    parser.add_argument(
        "--csv_dir",
        type=str,
        default=os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "three_node_roaming"
        ),
        help="Directory containing per-client roaming CSV files.",
    )
    parser.add_argument(
        "--output_path",
        type=str,
        default=os.path.join(os.getcwd(), "three_node_roaming_report"),
        help="Output path for the generated report.",
    )
    args = parser.parse_args()

    if not os.path.isdir(args.csv_dir):
        logger.error("CSV directory not found: %s", args.csv_dir)
        sys.exit(1)

    os.makedirs(args.output_path, exist_ok=True)
    generate_report(args.csv_dir, args.output_path)


if __name__ == "__main__":
    main()
