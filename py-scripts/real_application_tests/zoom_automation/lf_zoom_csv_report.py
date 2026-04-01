#!/usr/bin/env python3
"""Build zoom_call_report from received_UserQos CSV in generate_report_from_api format."""

import argparse
import importlib
import logging
import os
import re
import sys
import time

import pandas as pd


sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../.."))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

lf_report_mod = importlib.import_module("py-scripts.lf_report")
lf_report = lf_report_mod.lf_report
lf_graph = importlib.import_module("py-scripts.lf_graph")
lf_bar_graph_horizontal = lf_graph.lf_bar_graph_horizontal


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


class ZoomCsvReportBuilder:
    def __init__(
        self,
        input_csv,
        output_path,
        email=None,
        password=None,
        host=None,
        test_type="AUDIO & VIDEO",
        coordinates="",
        iterations="",
    ):
        self.input_csv = input_csv
        self.output_path = output_path
        self.email = email
        self.password = password
        self.host = host
        self.test_type = test_type
        self.coordinates = coordinates
        self.iterations = iterations
        self.summary_row = None
        self.participants_df = None
        self.summary_data = {}
        self.device_rows = []

    def parse_zoom_value(self, value):
        if value is None:
            return None

        value = str(value).strip()
        if value in ["", "-"]:
            return None

        # Keep MOS values as-is for table display (e.g. Good(4.41)).
        mos_match = re.match(r"^[A-Za-z]+\(([\d.]+)\)$", value)
        if mos_match:
            return value

        # For patterns like "21 ms/40 ms", use avg part only.
        if "/" in value:
            avg_part = value.split("/", 1)[0].strip()
            if avg_part in ["", "-"]:
                return None
            nums = re.findall(r"[\d.]+", avg_part)
            return float(nums[0]) if nums else None

        nums = re.findall(r"[\d.]+", value)
        return float(nums[0]) if nums else None

    def load_csv_sections(self):
        with open(self.input_csv, "r", encoding="utf-8-sig") as file_obj:
            lines = file_obj.readlines()

        # Top section contains meeting summary.
        meeting_summary = pd.read_csv(self.input_csv, nrows=1, encoding="utf-8-sig")
        self.summary_row = meeting_summary.iloc[0].to_dict() if not meeting_summary.empty else {}

        header_line_idx = None
        for idx, line in enumerate(lines):
            if line.strip().startswith("Participant,"):
                header_line_idx = idx
                break

        if header_line_idx is None:
            raise ValueError("Participant section was not found in CSV")

        participants_df = pd.read_csv(
            self.input_csv,
            skiprows=header_line_idx,
            encoding="utf-8-sig",
        )
        participants_df.columns = participants_df.columns.str.strip()
        self.participants_df = participants_df

    def summarize_audio_video(self):
        metric_map = {
            "audio_output_bitrate_avg": "Audio (Sending) Bitrate",
            "audio_input_bitrate_avg": "Audio (Receiving) Bitrate",
            "audio_output_latency_avg": "Audio (Sending) Latency-Avg/Max",
            "audio_input_latency_avg": "Audio (Receiving) Latency-Avg/Max",
            "audio_output_jitter_avg": "Audio (Sending) Jitter-Avg/Max",
            "audio_input_jitter_avg": "Audio (Receiving) Jitter-Avg/Max",
            "audio_output_avg_loss_avg": "Audio (Sending) Packet Loss-Avg/Max",
            "audio_input_avg_loss_avg": "Audio (Receiving) Packet Loss-Avg/Max",
            "audio_mos_avg": "Audio Quality",
            "video_output_bitrate_avg": "Video (Sending) Bitrate",
            "video_input_bitrate_avg": "Video (Receiving) Bitrate",
            "video_output_latency_avg": "Video (Sending) Latency-Avg/Max",
            "video_input_latency_avg": "Video (Receiving) Latency-Avg/Max",
            "video_output_jitter_avg": "Video (Sending) Jitter-Avg/Max",
            "video_input_jitter_avg": "Video (Receiving) Jitter-Avg/Max",
            "video_output_avg_loss_avg": "Video (Sending) Packet Loss-Avg/Max",
            "video_input_avg_loss_avg": "Video (Receiving) Packet Loss-Avg/Max",
            "video_output_frame_rate_avg": "Video (Sending) Frame Rate",
            "video_input_frame_rate_avg": "Video (Receiving) Frame Rate",
            "video_mos_avg": "Video Quality",
        }

        summary = {}
        host_name = str(self.summary_row.get("Host", "")).replace("(Guest)", "").strip()

        for _, row in self.participants_df.iterrows():
            participant = row.get("Participant")
            if pd.isna(participant):
                continue

            participant = str(participant).replace("(Guest)", "").strip()
            if participant == "":
                continue

            summary[participant] = {key: None for key in metric_map.keys()}
            summary[participant]["is_host"] = participant == host_name

            for key, csv_col in metric_map.items():
                raw_val = row.get(csv_col)
                parsed = self.parse_zoom_value(raw_val)
                summary[participant][key] = round(parsed, 2) if isinstance(parsed, float) else parsed

        self.summary_data = summary

    def _build_metric_graph(self, report, graph_title, xaxis_name, data_set, categories, image_name):
        report.set_graph_title(graph_title)
        report.build_graph_title()
        bar_graph = lf_bar_graph_horizontal(
            _data_set=data_set,
            _xaxis_name=xaxis_name,
            _yaxis_name="Devices",
            _yaxis_label=categories,
            _yaxis_categories=categories,
            _yaxis_step=1,
            _yticks_font=8,
            _bar_height=0.20,
            _color_name=["blue", "orange"],
            _show_bar_value=True,
            _figsize=(18, len(categories) * 1 + 4),
            _graph_title=graph_title.replace("a. ", "").replace("b. ", "").replace("c. ", "").replace("d. ", ""),
            _graph_image_name=image_name,
            _label=["Avg Recv", "Avg Sent"],
        )
        report.set_graph_image(bar_graph.build_bar_graph_horizontal())
        report.move_graph_image()
        report.build_graph()

    def _infer_os_type(self, device_name, participant):
        blob = f"{device_name} {participant}".lower()
        if "android" in blob or "samsung" in blob or "pixel" in blob:
            return "android"
        if "iphone" in blob or "ios" in blob:
            return "ios"
        if "web browser" in blob or "chrome" in blob:
            return "windows"
        return "unknown"

    def _build_device_rows(self):
        rows = []
        seen = set()
        for _, row in self.participants_df.iterrows():
            participant = row.get("Participant")
            if pd.isna(participant):
                continue
            hostname = str(participant).replace("(Guest)", "").strip()
            if not hostname or hostname in seen:
                continue
            seen.add(hostname)

            device_name = str(row.get("Device", ""))
            os_type = self._infer_os_type(device_name, hostname)
            mac = row.get("Media Access Control (MAC) Address", "")
            role = "Host" if self.summary_data.get(hostname, {}).get("is_host") else "Participant"
            rows.append(
                {
                    "Hostname": hostname,
                    "OS Type": os_type,
                    "MAC": mac if pd.notna(mac) else "",
                    "SSID": "",
                    "Role in call": role,
                    "Overall Audio MOS": self.summary_data.get(hostname, {}).get("audio_mos_avg") or 0,
                    "Overall Video MOS": self.summary_data.get(hostname, {}).get("video_mos_avg") or 0,
                }
            )
        self.device_rows = rows

    def add_roam_details(self, report_obj, roam_dir=None):
        """
        Separate function for future roam-details integration.
        Intentionally not used in default report generation.
        """
        report_obj.set_table_title("Roam Details")
        report_obj.build_table_title()
        if roam_dir:
            report_obj.set_text(
                f"Roam details integration placeholder. Directory provided: {roam_dir}"
            )
        else:
            report_obj.set_text("Roam details integration placeholder.")
        report_obj.build_text_simple()

    def generate_report(self):
        self.load_csv_sections()
        self.summarize_audio_video()
        self._build_device_rows()

        report = lf_report(
            _output_pdf="zoom_call_report.pdf",
            _output_html="zoom_call_report.html",
            _results_dir_name="zoom_call_report",
            _path=self.output_path,
        )

        report.set_title("Zoom Call Automated Report")
        report.build_banner()

        report.set_table_title("Objective:")
        report.build_table_title()
        report.set_text(
            """The Zoom Conference Test is designed to evaluate an Access Point ability
                to handle real-time conferencing workloads when multiple clients, including Windows,
                Linux, macOS, and Android devices, participate in a Zoom meeting. The test measures
                the AP’s efficiency in managing audio, video, and screen share traffic while maintaining
                acceptable latency, jitter, packet loss, and bitrate. Additional observations include client
                connection stability, airtime fairness, and MOS Score. The expected behavior is for the
                Access Point to sustain consistent Zoom performance as the client load increases,
                ensuring reliable conferencing quality without significant degradation across upstream
                and downstream traffic
            """
        )
        report.build_text_simple()

        report.set_table_title("Test Parameters:")
        report.build_table_title()

        os_counter = {"windows": 0, "linux": 0, "macos": 0, "android": 0}
        for row in self.device_rows:
            if row["OS Type"] in os_counter:
                os_counter[row["OS Type"]] += 1
        host_value = self.host if self.host is not None else (self.device_rows[0]["Hostname"] if self.device_rows else "")
        params = {
            "Test Name": "Zoom Conference Call Test",
            "Date": time.strftime("%d-%m-%Y", time.localtime()),
            "Devices Used": f"W({os_counter['windows']}),L({os_counter['linux']}),M({os_counter['macos']}),A({os_counter['android']})",
            "EMAIL ID": self.email if self.email is not None else self.summary_row.get("Email", ""),
            "PASSWORD": self.password if self.password is not None else "",
            "HOST": host_value,
            "TEST TYPE": self.test_type,
            "Coordinates": self.coordinates,
            "Iterations": self.iterations,
        }
        report.set_table_dataframe(pd.DataFrame([params]))
        report.build_table()

        report.set_table_title("Test Devices:")
        report.build_table_title()
        report.set_table_dataframe(pd.DataFrame(self.device_rows))
        report.build_table()

        if self.summary_data:
            participants = [row["Hostname"] for row in self.device_rows]

            def vals(in_key, out_key):
                return [
                    [(self.summary_data.get(c, {}).get(in_key) or 0) for c in participants],
                    [(self.summary_data.get(c, {}).get(out_key) or 0) for c in participants],
                ]

            report.set_table_title("1. Audio Performance")
            report.build_table_title()
            report.set_text(
                """Audio quality is evaluated through latency, jitter, bitrate, and packet loss, ensuring clear communication and consistent voice transmission."""
            )
            report.build_text_simple()

            self._build_metric_graph(report, "a. Audio Bitrate (Recevied/Sent)", "Bitrate (Kbps)", vals("audio_input_bitrate_avg", "audio_output_bitrate_avg"), participants, "Audio Bitrate(Recevied and Sent)")
            self._build_metric_graph(report, "b. Audio Latency (Recevied/Sent)", "Latency (ms)", vals("audio_input_latency_avg", "audio_output_latency_avg"), participants, "Audio Latency(received and sent)")
            self._build_metric_graph(report, "c. Audio Jitter (Recevied/Sent)", "Jitter (ms)", vals("audio_input_jitter_avg", "audio_output_jitter_avg"), participants, "Audio Jitter(received and Sent)")
            self._build_metric_graph(report, "d. Audio Packet Loss (Recevied/Sent)", "Packet Loss (%)", vals("audio_input_avg_loss_avg", "audio_output_avg_loss_avg"), participants, "Audio Packet Loss(Recevied and Sent)")

            report.set_table_title("Test Audio Results Table:")
            report.build_table_title()
            audio_test_details = pd.DataFrame(
                {
                    "Device Name": participants,
                    "Avg Bitrate (kbps) [Recevied/Sent]": [f"{(self.summary_data.get(c, {}).get('audio_input_bitrate_avg') or 0)}/{(self.summary_data.get(c, {}).get('audio_output_bitrate_avg') or 0)}" for c in participants],
                    "Avg Latency (ms) [Recevied/Sent]": [f"{(self.summary_data.get(c, {}).get('audio_input_latency_avg') or 0)}/{(self.summary_data.get(c, {}).get('audio_output_latency_avg') or 0)}" for c in participants],
                    "Avg Jitter (ms) [Recevied/Sent]": [f"{(self.summary_data.get(c, {}).get('audio_input_jitter_avg') or 0)}/{(self.summary_data.get(c, {}).get('audio_output_jitter_avg') or 0)}" for c in participants],
                    "Avg Pkt Loss (%) [Recevied/Sent]": [f"{(self.summary_data.get(c, {}).get('audio_input_avg_loss_avg') or 0)}/{(self.summary_data.get(c, {}).get('audio_output_avg_loss_avg') or 0)}" for c in participants],
                }
            )
            report.set_table_dataframe(audio_test_details)
            report.dataframe_html = report.dataframe.to_html(index=False, justify="center", render_links=True, escape=False)
            report.html += report.dataframe_html

            report.set_table_title("2. Video Performance")
            report.build_table_title()
            report.set_text(
                "Video traffic stresses the Access Point with higher bandwidth demand. Performance is validated by maintaining resolution, frame rate, and minimal loss under increasing client loads."
            )
            report.build_text_simple()

            self._build_metric_graph(report, "a. Video Bitrate (Recevied/Sent)", "Bitrate (kbps)", vals("video_input_bitrate_avg", "video_output_bitrate_avg"), participants, "Video Bitrate(Recevied and Sent)")
            self._build_metric_graph(report, "b. Video Latency (Recevied/Sent)", "Latency (ms)", vals("video_input_latency_avg", "video_output_latency_avg"), participants, "Video Latency(Recevied and Sent)")
            self._build_metric_graph(report, "c. Video Jitter (Recevied/Sent)", "Jitter (ms)", vals("video_input_jitter_avg", "video_output_jitter_avg"), participants, "Video Jitter(Recevied and sent)")
            self._build_metric_graph(report, "d. Video Packet Loss (Recevied/Sent)", "Packet Loss (%)", vals("video_input_avg_loss_avg", "video_output_avg_loss_avg"), participants, "Video Packet Loss(Recevied and Sent)")

            report.set_table_title("Test Video Results Table:")
            report.build_table_title()
            video_test_details = pd.DataFrame(
                {
                    "Device Name": participants,
                    "Avg Bitrate (kbps) [Recevied/Sent]": [f"{(self.summary_data.get(c, {}).get('video_input_bitrate_avg') or 0)}/{(self.summary_data.get(c, {}).get('video_output_bitrate_avg') or 0)}" for c in participants],
                    "Avg Latency (ms) [Recevied/Sent]": [f"{(self.summary_data.get(c, {}).get('video_input_latency_avg') or 0)}/{(self.summary_data.get(c, {}).get('video_output_latency_avg') or 0)}" for c in participants],
                    "Avg Jitter (ms) [Received/Sent]": [f"{(self.summary_data.get(c, {}).get('video_input_jitter_avg') or 0)}/{(self.summary_data.get(c, {}).get('video_output_jitter_avg') or 0)}" for c in participants],
                    "Avg Pkt Loss (%) [Recevied/Sent]": [f"{(self.summary_data.get(c, {}).get('video_input_avg_loss_avg') or 0)}/{(self.summary_data.get(c, {}).get('video_output_avg_loss_avg') or 0)}" for c in participants],
                }
            )
            report.set_table_dataframe(video_test_details)
            report.dataframe_html = report.dataframe.to_html(index=False, justify="center", render_links=True, escape=False)
            report.html += report.dataframe_html

        report.write_html()
        try:
            report.write_pdf(_page_size="Legal", _orientation="Landscape")
        except Exception as exc:
            logger.warning("PDF generation failed, HTML report is still available: %s", exc)

        logger.info("Report generated at: %s", report.get_path_date_time())


def main():
    parser = argparse.ArgumentParser(
        description="Generate Zoom call report from received_UserQos CSV"
    )
    parser.add_argument("--input_csv", required=True, help="Path to received_UserQos CSV")
    parser.add_argument(
        "--output_path",
        default=os.path.join(os.getcwd(), "zoom_csv_report_results"),
        help="Directory where report output folder will be created",
    )
    parser.add_argument("--email", default=None, help="Top table EMAIL ID value")
    parser.add_argument("--password", default=None, help="Top table PASSWORD value")
    parser.add_argument("--host", default=None, help="Top table HOST value")
    parser.add_argument("--test_type", default="AUDIO & VIDEO", help="Top table TEST TYPE")
    parser.add_argument("--coordinates", default="", help="Top table Coordinates")
    parser.add_argument("--iterations", default="", help="Top table Iterations")

    args = parser.parse_args()

    builder = ZoomCsvReportBuilder(
        input_csv=args.input_csv,
        output_path=args.output_path,
        email=args.email,
        password=args.password,
        host=args.host,
        test_type=args.test_type,
        coordinates=args.coordinates,
        iterations=args.iterations,
    )
    builder.generate_report()


if __name__ == "__main__":
    main()
