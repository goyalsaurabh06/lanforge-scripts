#!/usr/bin/env python3
"""
NAME: tri_band_roaming_report.py

PURPOSE:
    This script reads roaming event CSV files from a specified directory (one CSV per client device),
    detects individual roam events, computes management and data roam times, and generates an
    HTML/PDF report with per-client tables using the lf_report module.

    Roam Detection:
        Client-initiated auth_request frames are extracted and sorted by time. Starting from the
        first auth_request, the algorithm scans forward for EAPOL frames (eapol == 1). If EAPOL
        frames are found, the sequence from the first auth_request to the last EAPOL frame
        constitutes one complete roam event. Any intermediate auth_requests (retries) are absorbed
        into the same roam. The next roam starts at the first auth_request after the last EAPOL.
        If no EAPOL frames are found after an auth_request sequence, the roam is considered
        failed and is skipped.

    Management Roam Time:
        mgmt_roam_time = (last_eapol_timestamp - first_auth_request_timestamp) * 1000 ms

    Data Roam Time:
        data_roam_time = (first_data_frame_after_last_eapol - last_data_frame_before_first_auth) * 1000 ms
        Data frames are filtered to exclude EAPOL frames (eapol != 1). No AP BSSID filtering is
        used; temporal boundaries alone ensure correctness.

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
import json
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

DATA_SUBTYPES = [
    "Data subtype 0",
    "Data subtype 4",
    "Data subtype 8",
    "Data subtype 12",
]


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
    """Detect roam events from raw frame data and compute roam times.

    Algorithm:
        1. Group by pcap_name
        2. Extract client->AP auth_request frames, deduplicate, sort by time
        3. Extract EAPOL frames (eapol == 1), deduplicate, sort by time
        4. Walk sequentially: first auth_request starts a roam, scan forward
           (skipping intermediate auth_requests / retries) until EAPOL is found.
           auth_request to last EAPOL = one complete roam. Next roam starts at
           the first auth_request after that last EAPOL.
        5. If no EAPOL found after an auth_request sequence, skip (failed roam)

    Returns a list of dicts, one per detected roam event.
    """
    events = []
    grouped = df.groupby("pcap_name", sort=False)

    for pcap_name, group in grouped:
        from_point, to_point, iteration = parse_pcap_name(str(pcap_name))

        # Extract client->AP auth_request frames and deduplicate
        auth_requests = group[
            (group["event_label"] == "auth_request")
            & (group["frame_type"] == "Authentication")
        ].copy()
        if auth_requests.empty:
            continue
        # Detect client_mac from the first auth_request's sa
        client_mac = auth_requests.iloc[0]["sa"]
        auth_requests = auth_requests[auth_requests["sa"] == client_mac]
        auth_requests = auth_requests.drop_duplicates(subset=["timestamp", "sa", "da"])
        auth_requests = auth_requests.sort_values("timestamp").reset_index(drop=True)
        auth_req_times = auth_requests["timestamp"].astype(float).values

        # Extract EAPOL frames and deduplicate
        eapol_frames = group[group["eapol"] == 1].copy()
        eapol_frames = eapol_frames.drop_duplicates(subset=["timestamp", "sa", "da"])
        eapol_frames = eapol_frames.sort_values("timestamp").reset_index(drop=True)
        eapol_times = eapol_frames["timestamp"].astype(float).values

        # Pre-filter data frames (exclude EAPOL)
        data_frames = group[
            group["frame_type"].isin(DATA_SUBTYPES) & (group["eapol"] != 1)
        ].copy()
        if not data_frames.empty:
            data_frames["ts_float"] = data_frames["timestamp"].astype(float)

        # Walk auth_requests sequentially to find complete roams
        roam_list = []  # list of (first_auth_time, last_eapol_time)
        cursor = 0  # index into auth_req_times
        while cursor < len(auth_req_times):
            first_auth_time = auth_req_times[cursor]

            # Find the first EAPOL frame after this auth_request
            eapol_after = eapol_times[eapol_times > first_auth_time]
            if len(eapol_after) == 0:
                # No EAPOL after this auth_request — failed roam, skip remaining
                break

            first_eapol_time = eapol_after[0]

            # Find all consecutive EAPOL frames that belong to this roam:
            # collect all EAPOL frames up to the next auth_request that comes
            # AFTER the first EAPOL (if any)
            next_auth_after_eapol = auth_req_times[auth_req_times > first_eapol_time]
            if len(next_auth_after_eapol) > 0:
                eapol_end_bound = next_auth_after_eapol[0]
            else:
                eapol_end_bound = float("inf")

            roam_eapols = eapol_times[
                (eapol_times >= first_eapol_time) & (eapol_times < eapol_end_bound)
            ]
            last_eapol_time = roam_eapols[-1]

            roam_list.append((first_auth_time, last_eapol_time))

            # Advance cursor to the first auth_request after last_eapol_time
            next_indices = (auth_req_times > last_eapol_time).nonzero()[0]
            if len(next_indices) > 0:
                cursor = next_indices[0]
            else:
                break

        # Build event dicts for each complete roam
        for idx, (first_auth_time, last_eapol_time) in enumerate(roam_list):
            mgmt_roam_time_ms = round((last_eapol_time - first_auth_time) * 1000, 2)

            # Look up metadata from the original group row matching the first auth
            auth_row_match = group[
                (group["event_label"] == "auth_request")
                & (group["timestamp"].astype(float) == first_auth_time)
                & (group["sa"] == client_mac)
            ]
            meta_row = (
                auth_row_match.iloc[0] if not auth_row_match.empty else group.iloc[0]
            )

            # --- Data roam time ---
            data_roam_time_ms = "N/A"
            if not data_frames.empty:
                # Lower bound: previous roam's last_eapol_time, or 10s before first auth
                lower_bound = (
                    roam_list[idx - 1][1] if idx > 0 else first_auth_time - 10.0
                )
                # Upper bound: next roam's first_auth_time, or 10s after last eapol
                upper_bound = (
                    roam_list[idx + 1][0]
                    if idx < len(roam_list) - 1
                    else last_eapol_time + 10.0
                )

                # Last data frame before this roam's first auth
                old_ap_data = data_frames[
                    (data_frames["ts_float"] < first_auth_time)
                    & (data_frames["ts_float"] > lower_bound)
                ]
                # First data frame after this roam's last EAPOL
                new_ap_data = data_frames[
                    (data_frames["ts_float"] > last_eapol_time)
                    & (data_frames["ts_float"] < upper_bound)
                ]

                if not old_ap_data.empty and not new_ap_data.empty:
                    last_old_ts = old_ap_data["ts_float"].max()
                    first_new_ts = new_ap_data["ts_float"].min()
                    data_roam_time_ms = round((first_new_ts - last_old_ts) * 1000, 2)

            events.append(
                {
                    "pcap_name": pcap_name,
                    "from_coordinate": from_point,
                    "to_coordinate": to_point,
                    "iteration": iteration,
                    "client_mac": meta_row.get("client_mac", client_mac),
                    "roam_type": meta_row.get("roam_type", ""),
                    "band": meta_row.get("band", ""),
                    "mgmt_roam_time_ms": mgmt_roam_time_ms,
                    "data_roam_time_ms": data_roam_time_ms,
                }
            )

    return events


def generate_report(csv_dir, output_path, config_json=None):
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
        "The objective of this roaming test is to measure and validate the Wi-Fi roaming performance of real client "
        "devices while moving through different locations in the lab using a robot. The test aims to accurately capture roam events, "
        "calculate roam times, and verify the stability of user-experience scenarios (such as Zoom calls) during AP transitions. By "
        "using automated robot paths, parallel sniffing, and multiple device types (Android and iOS), the goal is to generate "
        "consistent, repeatable, and data-driven roaming performance reports for analysis and benchmarking."
    )
    report.build_text_simple()

    report.set_text(
        "Roam Time Calculation (Managment Roam Time)"
        "Roam time calculation measures the delay between the EAPOL M4 and the subsequent Authentication Request within the "
        "pcap file. Roam Time (ms) = Timestamp of EAPOL M4 – Timestamp of Authentication Request. "
        "Roam Time Calculation (Data Roam Time)"
        "Data roam time calculation measures the delay between the last data frame received from the old AP and the first data frame received from the new AP within the pcap file."
        "Data Roam Time (ms) = Timestamp of first data frame from new AP – Timestamp of last data frame from old AP."
    )

    # Test Setup Information table from roaming_config.json
    if config_json and os.path.isfile(config_json):
        with open(config_json, "r") as f:
            config = json.load(f)

        setup = config.get("test_setup", {})
        ap_aliases = config.get("ap_aliases", {})
        client_aliases = config.get("client_aliases", {})

        # Map configured band to the JSON key
        band_str = setup.get("configured_band", "5GHz")
        band_key_map = {
            "2.4GHz": "2g_link",
            "2GHz": "2g_link",
            "5GHz": "5g_link",
            "6GHz": "6g_link",
        }
        band_key = band_key_map.get(band_str, "5g_link")

        # Build rows
        setup_rows = []
        setup_rows.append(
            {"Parameter": "Test Name", "Value": setup.get("test_name", "")}
        )
        setup_rows.append({"Parameter": "DUT", "Value": setup.get("dut", "")})
        setup_rows.append({"Parameter": "Configured Band", "Value": band_str})
        setup_rows.append(
            {
                "Parameter": "Configured Channel",
                "Value": setup.get("configured_channel", ""),
            }
        )
        setup_rows.append(
            {
                "Parameter": "Configured Security",
                "Value": setup.get("configured_security", ""),
            }
        )
        setup_rows.append(
            {"Parameter": "Roaming Type", "Value": setup.get("roaming_type", "")}
        )
        setup_rows.append(
            {
                "Parameter": "Mesh Configuration",
                "Value": setup.get("mesh_configuration", ""),
            }
        )
        setup_rows.append(
            {"Parameter": "Coordinates", "Value": setup.get("coordinates", "")}
        )
        setup_rows.append(
            {
                "Parameter": "No of Iterations",
                "Value": setup.get("no_of_iterations", ""),
            }
        )
        # Root AP (Controller)
        controller = ap_aliases.get("Controller", {})
        setup_rows.append(
            {"Parameter": "Root BSSID", "Value": controller.get(band_key, "")}
        )
        setup_rows.append(
            {"Parameter": "Root MLD", "Value": controller.get("mld_addr", "")}
        )

        # Node APs (all non-Controller entries)
        node_num = 1
        for ap_name, ap_info in ap_aliases.items():
            if ap_name == "Controller":
                continue
            label = f"Node{node_num}" if len(ap_aliases) > 2 else "Node"
            setup_rows.append(
                {"Parameter": f"{label} BSSID", "Value": ap_info.get(band_key, "")}
            )
            setup_rows.append(
                {"Parameter": f"{label} MLD", "Value": ap_info.get("mld_addr", "")}
            )
            node_num += 1

        # Clients
        setup_rows.append(
            {"Parameter": "No of clients", "Value": str(len(client_aliases))}
        )
        for ci, (cname, cinfo) in enumerate(client_aliases.items(), start=1):
            mac = cinfo.get(band_key, cinfo.get("mld_addr", ""))
            setup_rows.append(
                {
                    "Parameter": f"Client {ci} Name & Mac Address",
                    "Value": f"{cname} and {mac}",
                }
            )

        setup_rows.append(
            {
                "Parameter": "No of Iterations",
                "Value": str(setup.get("no_of_iterations", "")),
            }
        )

        report.set_table_title("Test Setup Information:")
        report.build_table_title()
        setup_df = pd.DataFrame(setup_rows)
        report.set_table_dataframe(setup_df)
        report.build_table()
    else:
        logger.warning(
            "Config JSON not found at %s — skipping Test Setup table", config_json
        )

    # Per-client sections
    for client_name, events in all_clients.items():
        if not events:
            continue

        report.set_table_title(f"{client_name}")
        report.build_table_title()

        table_data = []
        for e in events:
            table_data.append(
                {
                    # "Pcap Name": e["pcap_name"],
                    "From Coordinate": e["from_coordinate"],
                    "To Coordinate": e["to_coordinate"],
                    "Iteration": e["iteration"],
                    "Client MAC": e["client_mac"],
                    # "Roam Type": e["roam_type"],
                    # "Band": e["band"],
                    "Mgmt Roam Time (ms)": e["mgmt_roam_time_ms"],
                    "Data Roam Time (ms)": e["data_roam_time_ms"],
                }
            )

        table_df = pd.DataFrame(table_data)
        report.set_table_dataframe(table_df)
        report.build_table()

    # # Cross-client comparison
    # if len(all_clients) > 1:
    #     report.set_table_title("Cross-Client Roaming Comparison")
    #     report.build_table_title()
    #     report.set_text(
    #         "Summary of roaming events and average roam times per client device."
    #     )
    #     report.build_text_simple()

    #     comparison_data = []
    #     for client_name, events in all_clients.items():
    #         total = len(events)
    #         mgmt_vals = [
    #             e["mgmt_roam_time_ms"]
    #             for e in events
    #             if e["mgmt_roam_time_ms"] != "N/A"
    #         ]
    #         data_vals = [
    #             e["data_roam_time_ms"]
    #             for e in events
    #             if e["data_roam_time_ms"] != "N/A"
    #         ]
    #         eapol_count = len(mgmt_vals)
    #         avg_mgmt = round(sum(mgmt_vals) / len(mgmt_vals), 2) if mgmt_vals else "N/A"
    #         avg_data = round(sum(data_vals) / len(data_vals), 2) if data_vals else "N/A"
    #         comparison_data.append(
    #             {
    #                 "Client": client_name,
    #                 "Total Roams": total,
    #                 "Roams with EAPOL": eapol_count,
    #                 "Avg Mgmt Roam Time (ms)": avg_mgmt,
    #                 "Avg Data Roam Time (ms)": avg_data,
    #             }
    #         )

    #     comparison_df = pd.DataFrame(comparison_data)
    #     report.set_table_dataframe(comparison_df)
    #     report.build_table()

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

    config_json = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "roaming_config.json"
    )

    os.makedirs(args.output_path, exist_ok=True)
    generate_report(args.csv_dir, args.output_path, config_json=config_json)


if __name__ == "__main__":
    main()
