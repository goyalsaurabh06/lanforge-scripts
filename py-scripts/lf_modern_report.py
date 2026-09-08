#!/usr/bin/env python3
"""
NAME: lf_modern_report.py

PURPOSE:

Drop-in replacement for lf_report.py that keeps the exact same `lf_report`
class API (constructor signature, method names/signatures, return values,
and public attributes) so existing scripts only need to change:

    from lf_report import lf_report
to:
    from lf_modern_report import lf_report

Internally, the generated HTML report uses a modern design-token based
stylesheet (artifacts/modern-report.css, copied over the output "report.css")
and ships a self-hosted, vendored Apache ECharts runtime
(artifacts/echarts.min.js) for a new opt-in interactive-chart capability
(see build_echarts_chart). Charts produced by callers today (matplotlib PNGs
from lf_graph.py or elsewhere) keep working unchanged -- they're still
embedded as images, now inside a modern ".chart-card" container instead of
ad hoc inline styles.

See lf_report.py for the original implementation this mirrors, and
lf_graph.py for the repo's matplotlib chart-generation library used by
callers to produce the PNGs this module embeds.

LICENSE:
    Free to distribute and modify. LANforge systems must be licensed.
    Copyright (C) 2020-2026 Candela Technologies Inc

INCLUDE_IN_README
"""
# CAUTION: adding imports to this file which are not in update_dependencies.py is not advised
import os
import sys
import json
import shutil
import base64
import datetime

import pandas as pd
import pdfkit
import argparse
import traceback
import logging
import importlib

from matplotlib import pyplot as plt
import platform
import subprocess

sys.path.append(os.path.join(os.path.abspath(__file__ + "../../../")))

logger = logging.getLogger(__name__)
lf_logger_config = importlib.import_module("py-scripts.lf_logger_config")
lf_csv = importlib.import_module("py-scripts.lf_csv").lf_csv
os_name = platform.system()

__all__ = ["lf_report", "lf_bar_graph", "lf_bar_graph_horizontal", "lf_line_graph", "lf_pie_graph",
          "create_pie_chart", "create_info_card", "create_device_summary_card", "create_findings_card"]

# ECharts styling conventions below are lifted verbatim (palette, baseOption,
# tooltip/legend/axis/dataZoom conventions, named-series coloring) from the
# existing modern report sample so any interactive chart added through this
# module looks consistent with that established visual language.
_ECHARTS_PALETTE = ["#1f6f58", "#f1b24a", "#2f80ed", "#1d9a8a", "#d95f5f", "#d48b1f"]

# Auto-assigned DOM ids for charts created without an explicit chart_id (e.g.
# create_pie_chart(data=..., title=...) with no chart_id kwarg), so multiple
# charts can be dropped into the same report without the caller having to
# invent/track unique ids themselves.
_chart_id_counter = 0


def _next_chart_id(prefix):
    global _chart_id_counter
    _chart_id_counter += 1
    return "{}-{}".format(prefix, _chart_id_counter)

_ECHARTS_RUNTIME_JS = """
<script>
(function () {
  if (typeof window.echarts === "undefined") { return; }
  var PALETTE = %(palette)s;

  function baseOption(yName, xName) {
    return {
      color: PALETTE,
      tooltip: { trigger: "axis", axisPointer: { type: "cross" } },
      // itemWidth/itemHeight wider than the ECharts default (25x14) so a dashed series'
      // legend swatch has room to draw a couple of full dashes instead of one small
      // fragment that reads as a broken line next to the solid series' swatches.
      legend: { bottom: 0, textStyle: { color: "#5f6f82", fontSize: 12 }, itemWidth: 30, itemHeight: 14 },
      grid: { left: 76, right: 28, top: 48, bottom: 84, containLabel: true },
      xAxis: {
        type: "category", name: xName || "", nameLocation: "middle", nameGap: 34,
        nameTextStyle: { color: "#2c3e50", fontWeight: 600 },
        axisLine: { lineStyle: { color: "#c8d4e3" } },
        axisLabel: { color: "#2c3e50", fontWeight: 600 },
        splitLine: { show: true, lineStyle: { color: "#ecf1f6" } }
      },
      yAxis: {
        type: "value", name: yName || "", nameLocation: "middle", nameGap: 52, nameRotate: 90,
        nameTextStyle: { color: "#2c3e50", fontWeight: 600 },
        axisLine: { lineStyle: { color: "#c8d4e3" } },
        axisLabel: { color: "#5f6f82" },
        splitLine: { show: true, lineStyle: { color: "#ecf1f6" } }
      },
      dataZoom: [
        { type: "inside", xAxisIndex: 0 },
        { type: "slider", xAxisIndex: 0, bottom: 18, height: 18, brushSelect: false }
      ],
      series: []
    };
  }

  function namedColor(seriesName) {
    if (/Download$/.test(seriesName)) { return "#1f6f58"; }
    if (/Upload$/.test(seriesName)) { return "#f1b24a"; }
    if (/Bidirectional\\(UL\\+DL\\)$/.test(seriesName)) { return "#2f80ed"; }
    return undefined;
  }

  function renderFallback(id, message) {
    var el = document.getElementById(id);
    if (el) {
      el.innerHTML = '<div class="chart-fallback">' + (message || "Interactive chart unavailable.") + "</div>";
    }
  }

  window.__lfModernReport = window.__lfModernReport || {};

  window.__lfModernReport.renderLineChart = function (id, payload, yName, xName) {
    var el = document.getElementById(id);
    if (!el || !payload || !payload.series) { renderFallback(id); return; }
    var chart = window.echarts.init(el);
    var option = baseOption(yName, xName);
    if (payload.categories) { option.xAxis.data = payload.categories; option.xAxis.type = "category"; }
    if (payload.inverseX) { option.xAxis.inverse = true; }
    if (payload.inverseY) { option.yAxis.inverse = true; }
    option.series = payload.series.map(function (s) {
      var c = s.color || namedColor(s.name);
      return {
        name: s.name, type: "line", smooth: false, symbol: "none", connectNulls: false,
        data: s.data,
        // A named "dashed" type default to a short pattern that, at legend-swatch size,
        // draws as one small fragment rather than a recognizable dashed line -- an
        // explicit [dash, gap] pattern keeps it looking dashed at that size too.
        lineStyle: { width: 2, color: c, type: s.dashed ? [6, 4] : "solid" },
        itemStyle: c ? { color: c } : undefined
      };
    });
    chart.setOption(option);
    window.addEventListener("resize", function () { chart.resize(); });
  };

  window.__lfModernReport.renderBarChart = function (id, payload, yName, xName) {
    var el = document.getElementById(id);
    if (!el || !payload || !payload.series) { renderFallback(id); return; }
    var chart = window.echarts.init(el);
    var option = baseOption(yName, xName);
    option.tooltip.axisPointer = { type: "shadow" };
    option.xAxis.data = payload.categories || [];
    option.series = payload.series.map(function (s) {
      var c = s.color || namedColor(s.name);
      return {
        name: s.name, type: "bar", data: s.data, barMaxWidth: 34,
        stack: payload.stacked ? "total" : undefined,
        itemStyle: c ? { color: c } : undefined
      };
    });
    // Optional per-category, per-series breakdown (e.g. the individual
    // clients behind one stacked segment's count) shown in the tooltip
    // instead of just that segment's total. Generic: keyed only by category
    // name and series name, so any stacked/grouped bar chart can supply this
    // -- lf_modern_report.py itself has no idea what the detail lines mean.
    // Switches the tooltip to per-segment (trigger: "item") instead of the
    // default whole-category (trigger: "axis") so hovering one segment only
    // shows that segment's items, not every series at that category.
    if (payload.itemDetails) {
      option.tooltip.trigger = "item";
      option.tooltip.formatter = function (p) {
        var details = (payload.itemDetails[p.name] || {})[p.seriesName] || [];
        var body = details.length
          ? details.map(function (t) { return "&nbsp;&nbsp;" + t; }).join("<br/>")
          : "&nbsp;&nbsp;<i>none</i>";
        return "<b>" + p.name + "</b> &mdash; " + p.marker + " <b>" + p.seriesName + "</b><br/>" + body;
      };
    }
    chart.setOption(option);
    window.addEventListener("resize", function () { chart.resize(); });
  };

  window.__lfModernReport.renderHorizontalBarChart = function (id, payload, xName) {
    var el = document.getElementById(id);
    if (!el || !payload || !payload.series) { renderFallback(id); return; }
    el.style.height = Math.max(300, (payload.categories || []).length * 52 + 120) + "px";
    var chart = window.echarts.init(el);
    var option = baseOption(xName, "");
    option.xAxis = {
      type: "value", name: xName || "", min: 0,
      nameLocation: "middle", nameGap: 30,
      nameTextStyle: { color: "#2c3e50", fontWeight: 600 },
      axisLabel: { color: "#5f6f82" }
    };
    option.yAxis = {
      type: "category", data: payload.categories || [],
      axisLabel: {
        color: "#2c3e50", fontWeight: 600,
        // Truncate only what's shown on the axis -- the full category name
        // stays in the data, so hovering a bar's tooltip still shows it in full.
        formatter: function (value) { return value.length > 9 ? value.slice(0, 9) + "…" : value; }
      }
    };
    option.series = payload.series.map(function (s) {
      var c = s.color || namedColor(s.name);
      return {
        name: s.name, type: "bar", data: s.data,
        stack: payload.stacked ? "total" : undefined,
        itemStyle: c ? { color: c } : undefined,
        label: { show: true, color: payload.stacked ? "#ffffff" : "#2c3e50", position: payload.stacked ? "inside" : "right" }
      };
    });
    chart.setOption(option);
    window.addEventListener("resize", function () { chart.resize(); });
  };

  window.__lfModernReport.renderConnectivityTimeline = function (id, payload) {
    var el = document.getElementById(id);
    var clients = (payload && payload.clients) || [];
    var stations = (payload && payload.stations) || [];
    var segments = (payload && payload.segments) || [];
    if (!el || !clients.length || !segments.length) {
      renderFallback(id, payload && payload.emptyMessage);
      return;
    }

    el.style.height = Math.max(320, clients.length * 38 + 150) + "px";
    var chart = window.echarts.init(el);

    function renderSegment(params, api) {
      var category = api.value(0);
      var start = api.coord([api.value(1), category]);
      var end = api.coord([api.value(2), category]);
      var height = api.size([0, 1])[1] * 0.56;
      var shape = echarts.graphic.clipRectByRect({
        x: start[0],
        y: start[1] - height / 2,
        width: Math.max(end[0] - start[0], 1),
        height: height
      }, {
        x: params.coordSys.x,
        y: params.coordSys.y,
        width: params.coordSys.width,
        height: params.coordSys.height
      });
      return shape && { type: "rect", shape: shape, style: api.style() };
    }

    function seriesFor(status, label, color) {
      return {
        name: label,
        type: "custom",
        renderItem: renderSegment,
        itemStyle: { color: color },
        encode: { x: [1, 2], y: 0 },
        data: segments.filter(function (s) { return s.status === status; })
          .map(function (s) { return [s.clientIndex, s.start, s.end]; })
      };
    }

    chart.setOption({
      tooltip: {
        trigger: "item",
        formatter: function (p) {
          var values = p.value || [];
          var station = stations[values[0]];
          var stationLine = station ? " (" + station + ")" : "";
          return p.marker + " <b>" + clients[values[0]] + "</b>" + stationLine + "<br/>" +
            p.seriesName + ": " + Number(values[1]).toFixed(1) + "–" +
            Number(values[2]).toFixed(1) + " s";
        }
      },
      legend: { bottom: 0, data: ["Up", "Drop"], textStyle: { color: "#5f6f82" } },
      grid: { left: 165, right: 30, top: 25, bottom: 72, containLabel: false },
      xAxis: {
        type: "value",
        min: 0,
        max: payload.duration,
        name: "Time (seconds)",
        nameLocation: "middle",
        nameGap: 36,
        axisLabel: { color: "#5f6f82" },
        splitLine: { lineStyle: { color: "#ecf1f6" } }
      },
      yAxis: {
        type: "category",
        inverse: true,
        data: clients,
        axisLabel: { color: "#2c3e50", fontWeight: 600, width: 145, overflow: "truncate" },
        axisTick: { show: false },
        axisLine: { show: false }
      },
      series: [
        seriesFor("up", "Up", "#2e8b57"),
        seriesFor("drop", "Drop", "#eb5757")
      ]
    });
    window.addEventListener("resize", function () { chart.resize(); });
  };

  window.__lfModernReport.renderPieChart = function (id, payload) {
    var el = document.getElementById(id);
    if (!el || !payload || !payload.slices || !payload.slices.length) {
      renderFallback(id, payload && payload.emptyMessage);
      return;
    }
    var chart = window.echarts.init(el);
    var showPct = !!payload.showPercentage;
    var labelFmt = payload.labelFormatter || (showPct ? "{b}\\n{d}%%" : "{b}\\n{c}");
    var tooltipFmt = payload.tooltipFormatter || "{b}: {c} ({d}%%)";
    function formatPieLabel(p) {
      // ECharts may still lay out labels for zero-sized slices. Keep those
      // categories in the legend, but do not draw a misleading 0%% label.
      if (!(Number(p.value) > 0)) { return ""; }
      return String(labelFmt)
        .replace(/\\{b\\}/g, p.name)
        .replace(/\\{c\\}/g, p.value)
        .replace(/\\{d\\}/g, p.percent);
    }
    var option = {
      color: payload.colors || PALETTE,
      tooltip: { trigger: "item", formatter: tooltipFmt },
      legend: (payload.legend === false) ? { show: false } : { bottom: 0, textStyle: { color: "#5f6f82", fontSize: 12 } },
      series: [{
        type: "pie",
        radius: payload.radius || ["38%%", "68%%"],
        center: payload.center || ["50%%", "44%%"],
        // When the selected slices total zero, ECharts otherwise renders
        // them as equal wedges. Zero values must occupy no area.
        stillShowZeroSum: false,
        label: (payload.showLabels === false) ? { show: false } : { formatter: formatPieLabel },
        labelLine: { show: payload.showLabels !== false },
        itemStyle: { borderWidth: 0 },
        data: payload.slices
      }]
    };
    // Optional per-slice breakdown (e.g. the individual clients behind one
    // slice's count) shown in the tooltip instead of just that slice's
    // total. Generic: keyed only by slice name, so any pie chart can supply
    // this -- lf_modern_report.py has no idea what the detail lines mean.
    if (payload.itemDetails) {
      option.tooltip.formatter = function (p) {
        var items = payload.itemDetails[p.name] || [];
        var body = items.length
          ? items.map(function (t) { return "&nbsp;&nbsp;" + t; }).join("<br/>")
          : "&nbsp;&nbsp;<i>none</i>";
        return p.marker + " <b>" + p.name + "</b>: " + p.value + " (" + p.percent + "%%)<br/>" + body;
      };
    }
    if (payload.centerLabel) {
      var main = (typeof payload.centerLabel === "object") ? (payload.centerLabel.main || "") : String(payload.centerLabel);
      var sub = (typeof payload.centerLabel === "object") ? (payload.centerLabel.sub || "") : "";
      option.graphic = [{
        type: "text",
        left: "center",
        top: (payload.center && payload.center[1]) || "44%%",
        style: {
          text: sub ? (main + "\\n" + sub) : main,
          textAlign: "center",
          fill: "#2c3e50",
          fontSize: 20,
          fontWeight: 700,
          lineHeight: 24
        }
      }];
    }
    chart.setOption(option);
    window.addEventListener("resize", function () { chart.resize(); });
  };
})();
</script>
""" % {"palette": json.dumps(_ECHARTS_PALETTE)}

# Shared runtime for the searchable/paginated device table in
# create_device_summary_card()/build_device_summary_card(). Kept as its own
# small runtime (injected once per page, same convention as
# _ECHARTS_RUNTIME_JS) rather than folded into the ECharts one, since it has
# nothing to do with charting -- it only needs plain DOM APIs.
_TABLE_RUNTIME_JS = """
<script>
(function () {
  window.__lfModernReport = window.__lfModernReport || {};

  // rows: [{cellsHtml: "<td>...</td><td>...</td>", searchText: "lowercased ... "}]
  window.__lfModernReport.initSearchTable = function (rootId, rows, pageSize) {
    var root = document.getElementById(rootId);
    if (!root) { return; }
    var tbody = root.querySelector(".device-table tbody");
    var searchInput = root.querySelector(".device-search");
    var pageSizeSelect = root.querySelector(".rows-per-page select");
    var paginationEl = root.querySelector(".pagination");
    var countEl = root.querySelector(".device-count-label");
    var viewAllBtn = root.querySelector(".view-all-btn");
    if (!tbody) { return; }

    var state = { filtered: rows, page: 1, pageSize: pageSize || rows.length || 10 };

    function renderRows() {
      var total = state.filtered.length;
      var pages = Math.max(1, Math.ceil(total / state.pageSize));
      if (state.page > pages) { state.page = pages; }
      var start = (state.page - 1) * state.pageSize;
      var pageRows = state.filtered.slice(start, start + state.pageSize);
      tbody.innerHTML = pageRows.map(function (r, i) {
        return "<tr><td>" + (start + i + 1) + "</td>" + r.cellsHtml + "</tr>";
      }).join("") || "<tr><td colspan='99' style='text-align:center;color:var(--muted);'>No matching rows</td></tr>";
      renderPagination(pages);
    }

    function renderPagination(pages) {
      if (!paginationEl) { return; }
      var parts = [];
      parts.push('<button data-page="' + (state.page - 1) + '"' + (state.page === 1 ? " disabled" : "") + ">&lsaquo;</button>");
      var shown = [];
      for (var p = 1; p <= pages; p++) {
        if (p === 1 || p === pages || Math.abs(p - state.page) <= 1) { shown.push(p); }
        else if (shown[shown.length - 1] !== "...") { shown.push("..."); }
      }
      shown.forEach(function (p) {
        if (p === "...") { parts.push('<span class="pagination-ellipsis">&hellip;</span>'); }
        else { parts.push('<button data-page="' + p + '" class="' + (p === state.page ? "active" : "") + '">' + p + "</button>"); }
      });
      parts.push('<button data-page="' + (state.page + 1) + '"' + (state.page === pages ? " disabled" : "") + ">&rsaquo;</button>");
      paginationEl.innerHTML = parts.join("");
      Array.prototype.forEach.call(paginationEl.querySelectorAll("button[data-page]"), function (btn) {
        btn.addEventListener("click", function () {
          state.page = parseInt(btn.getAttribute("data-page"), 10);
          renderRows();
        });
      });
    }

    if (searchInput) {
      searchInput.addEventListener("input", function () {
        var q = searchInput.value.trim().toLowerCase();
        state.filtered = !q ? rows : rows.filter(function (r) { return r.searchText.indexOf(q) !== -1; });
        state.page = 1;
        renderRows();
      });
    }
    if (pageSizeSelect) {
      pageSizeSelect.addEventListener("change", function () {
        state.pageSize = pageSizeSelect.value === "all" ? rows.length : parseInt(pageSizeSelect.value, 10);
        state.page = 1;
        renderRows();
      });
    }
    if (viewAllBtn) {
      viewAllBtn.addEventListener("click", function () {
        state.pageSize = rows.length || 1;
        state.page = 1;
        if (pageSizeSelect) { pageSizeSelect.value = "all"; }
        renderRows();
      });
    }
    renderRows();
  };
})();
</script>
"""

# Makes every plain report table (built by build_table()/pass_failed_build_table(), class
# "data-table") sortable by clicking a column header. Injected once at the end of the page,
# after all tables have been appended, so it can just scan the DOM rather than needing each
# build_table() call to wire anything up.
_SORTABLE_TABLE_JS = """
<script>
(function () {
  function cellSortValue(cell) {
    var text = cell.textContent.trim();
    var numeric = parseFloat(text.replace(/,/g, ""));
    if (!isNaN(numeric) && /^-?[\\d.,]+/.test(text)) { return numeric; }
    return text.toLowerCase();
  }

  function sortTable(table, columnIndex, ascending) {
    var tbody = table.tBodies[0];
    if (!tbody) { return; }
    var rows = Array.prototype.slice.call(tbody.rows);
    rows.sort(function (rowA, rowB) {
      var a = cellSortValue(rowA.cells[columnIndex]);
      var b = cellSortValue(rowB.cells[columnIndex]);
      if (a < b) { return ascending ? -1 : 1; }
      if (a > b) { return ascending ? 1 : -1; }
      return 0;
    });
    rows.forEach(function (row) { tbody.appendChild(row); });
  }

  Array.prototype.forEach.call(document.querySelectorAll("table.data-table"), function (table) {
    var headerRow = table.tHead && table.tHead.rows[0];
    if (!headerRow || !table.tBodies.length) { return; }
    Array.prototype.forEach.call(headerRow.cells, function (th, columnIndex) {
      th.classList.add("sortable");
      th.addEventListener("click", function () {
        var ascending = !th.classList.contains("sort-asc");
        Array.prototype.forEach.call(headerRow.cells, function (cell) {
          cell.classList.remove("sort-asc", "sort-desc");
        });
        th.classList.add(ascending ? "sort-asc" : "sort-desc");
        sortTable(table, columnIndex, ascending);
      });
    });
  });
})();
</script>
"""


class lf_report:
    def __init__(self,
                 # _path the report directory under which the report directories will be created.
                 _path="/home/lanforge/html-reports",
                 _alt_path="",
                 _date="",
                 _title="LANForge Unit Test Run Heading",
                 _table_title="LANForge Table Heading",
                 _graph_title="LANForge Graph Title",
                 _obj="",
                 _obj_title="",
                 _output_html="outfile.html",
                 _output_pdf="outfile.pdf",
                 _results_dir_name="LANforge_Test_Results_Unit_Test",
                 _output_format='html',  # pass in on the write functionality, current not used
                 _dataframe="",
                 _path_date_time="",
                 _custom_css='custom-example.css',
                 _allure_report_dir_name="allure-report"):  # this is where the final report is placed.
        # other report paths,

        # _path is where the directory with the data time will be created
        if _path == "local" or _path == "here":
            self.path = os.path.abspath(__file__)
            logger.info("path set to file path: {}".format(self.path))
        elif _alt_path != "":
            self.path = _alt_path
            logger.info("path set to alt path: {}".format(self.path))
        else:
            self.path = _path
            logger.info("path set: {}".format(self.path))

        # allure report is the allure report directory
        self.allure_report_dir_name = _allure_report_dir_name
        self.allure_report_dir = os.path.join(self.path, self.allure_report_dir_name)

        allure_report_history = format("{allure_report}/history".format(allure_report=self.allure_report_dir_name))
        self.allure_report_history = os.path.join(self.path, allure_report_history)
        self.allure_report_history_path = str(self.allure_report_history)

        self.allure_results_history = ""
        self.allure_results = ""
        self.allure_result_dir = ""
        self.allure_report_timeout = 120    # TODO have configurable or allow process to complete and not wait.
        self.allure_result = "SUCCESS"

        self.dataframe = _dataframe
        self.text = ""
        self.title = _title
        self.table_title = _table_title
        self.graph_title = _graph_title
        self.date = _date
        self.output_html = _output_html
        if _output_html.lower().endswith(".pdf"):
            raise ValueError("HTML output file cannot end with suffix '.pdf'")
        self.path_date_time = _path_date_time
        self.report_location = ""   # used by lf_check.py to know where to write the meta data "Report Location:::/home/lanforge/html-reports/wifi-capacity-2021-08-17-04-02-56"
        self.write_output_html = ""
        self.write_output_index_html = ""
        self.output_pdf = _output_pdf
        self.write_output_pdf = ""
        self.banner_html = ""
        self.footer_html = ""
        self.graph_titles = ""
        self.graph_image = ""
        self.csv_file_name = ""
        self.html = ""
        self.allure_executor = ""
        self.allure_executor_dir = ""
        self.write_out_allure_executor = ""
        self.allure_environment_properties = ""
        self.allure_environment_properties_dir = ""
        self.write_out_allure_environment_properties = ""
        self.junit = ""
        self.write_output_junit = ""
        self.junit_dir = ""
        self.custom_html = ""
        self.pdf_link_html = ""
        self.objective = _obj
        self.obj_title = _obj_title
        self.description = ""
        self.desc_title = ""
        self.date_time_directory = ""
        self.log_directory = ""

        self.banner_directory = "artifacts"
        self.banner_file_name = "banner.png"
        self.logo_directory = "artifacts"
        self.logo_file_name = "CandelaLogo2-90dpi-200x90-trans.png"
        self.logo_footer_file_name = "candela_swirl_small-72h.png"
        self.current_path = os.path.dirname(os.path.abspath(__file__))
        self.custom_css = _custom_css
        # modern report assets
        self.modern_css_file = "modern-report.css"
        self.echarts_file = "echarts.min.js"
        self._echarts_runtime_emitted = False
        self._table_runtime_emitted = False

        # note: the following 3 calls must be in order
        self.set_date_time_directory(_date, _results_dir_name)
        self.build_date_time_directory()
        self.build_log_directory()

        self.font_file = "CenturyGothic.woff"
        # move the banners and candela images to report path
        self.copy_banner()
        self.copy_css()
        self.copy_logo()
        self.copy_logo_footer()
        self.copy_echarts()

    def copy_banner(self):
        banner_src_file = str(self.current_path) + '/' + str(self.banner_directory) + '/' + str(self.banner_file_name)
        banner_dst_file = str(self.path_date_time) + '/' + str(self.banner_file_name)
        shutil.copy(banner_src_file, banner_dst_file)

    def move_data(self, directory=None, _file_name=None, directory_name=None):
        if directory_name is None:
            _src_file = str(self.current_path) + '/' + str(_file_name)
            if directory is None:
                _dst_file = str(self.path_date_time)
            else:
                _dst_file = str(self.path_date_time) + '/' + str(directory) + '/' + str(_file_name)
        else:
            _src_file = str(self.current_path) + '/' + str(directory_name)
            _dst_file = str(self.path_date_time) + '/' + str(directory_name)
        shutil.move(_src_file, _dst_file)

    def copy_css(self):
        # modern report stylesheet is copied to the same output filename ("report.css")
        # the legacy lf_report.py used, so get_html_head()'s <link> tags need no changes.
        reportcss_src_file = str(self.current_path) + '/' + str(self.banner_directory) + '/' + str(self.modern_css_file)
        reportcss_dest_file = str(self.path_date_time) + '/report.css'

        customcss_src_file = str(self.current_path) + '/' + str(self.banner_directory) + '/' + str(self.custom_css)
        customcss_dest_file = str(self.path_date_time) + '/custom.css'

        font_src_file = str(self.current_path) + '/' + str(self.banner_directory) + '/' + str(self.font_file)
        font_dest_file = str(self.path_date_time) + '/' + str(self.font_file)

        shutil.copy(reportcss_src_file, reportcss_dest_file)
        shutil.copy(customcss_src_file, customcss_dest_file)
        shutil.copy(font_src_file, font_dest_file)

    def copy_echarts(self):
        echarts_src_file = str(self.current_path) + '/' + str(self.banner_directory) + '/' + str(self.echarts_file)
        echarts_dst_file = str(self.path_date_time) + '/' + str(self.echarts_file)
        shutil.copy(echarts_src_file, echarts_dst_file)

    def copy_logo(self):
        logo_src_file = str(self.current_path) + '/' + str(self.logo_directory) + '/' + str(self.logo_file_name)
        logo_dst_file = str(self.path_date_time) + '/' + str(self.logo_file_name)
        shutil.copy(logo_src_file, logo_dst_file)

    def copy_logo_footer(self):
        logo_footer_src_file = str(self.current_path) + '/' + str(self.logo_directory) + '/' + str(
            self.logo_footer_file_name)
        logo_footer_dst_file = str(self.path_date_time) + '/' + str(self.logo_footer_file_name)
        shutil.copy(logo_footer_src_file, logo_footer_dst_file)

    def move_graph_image(self, ):
        if _CHART_MARKUP_SENTINEL in str(self.graph_image):
            # self.graph_image holds interactive chart-card markup (from
            # lf_bar_graph/lf_bar_graph_horizontal/lf_line_graph), not a PNG
            # path on disk -- nothing to move.
            return
        graph_src_file = str(self.graph_image)
        graph_dst_file = str(self.path_date_time) + '/' + str(self.graph_image)
        logger.info("graph_src_file: {}".format(graph_src_file))
        logger.info("graph_dst_file: {}".format(graph_dst_file))
        shutil.move(graph_src_file, graph_dst_file)

    def move_csv_file(self):
        csv_src_file = str(self.csv_file_name)
        csv_dst_file = str(self.path_date_time) + '/' + str(self.csv_file_name)
        logger.info("csv_src_file: {}".format(csv_src_file))
        logger.info("csv_dst_file: {}".format(csv_dst_file))
        shutil.move(csv_src_file, csv_dst_file)

    def set_path(self, _path):
        self.path = _path

    def set_date_time_directory(self, _date, _results_dir_name):
        self.date = _date
        self.results_dir_name = _results_dir_name
        if self.date != "":
            self.date_time_directory = str(self.date) + str("_") + str(self.results_dir_name)
        else:
            self.date = str(datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S")).replace(':', '-')
            self.date_time_directory = self.date + str("_") + str(self.results_dir_name)

    def build_date_time_directory(self):
        if self.date_time_directory == "":
            self.set_date_time_directory()
        self.path_date_time = os.path.join(self.path, self.date_time_directory)
        logger.info("path_date_time {}".format(self.path_date_time))
        try:
            if not os.path.exists(self.path_date_time):
                os.mkdir(self.path_date_time)
        except Exception as x:
            traceback.print_exception(Exception, x, x.__traceback__, chain=True)
            self.path_date_time = os.path.join(self.current_path, self.date_time_directory)
            if not os.path.exists(self.path_date_time):
                os.mkdir(self.path_date_time)
        logger.info("report path : {}".format(self.path_date_time))

    def build_log_directory(self):
        if self.log_directory == "":
            self.log_directory = os.path.join(self.path_date_time, "log")
        try:
            if not os.path.exists(self.log_directory):
                os.mkdir(self.log_directory)
        except Exception as x:
            traceback.print_exception(Exception, x, x.__traceback__, chain=True)
            logger.critical("exception making {}".format(self.log_directory))
            exit(1)

    def build_x_directory(self, directory_name=None):
        directory = None
        if directory_name:
            directory = os.path.join(self.path_date_time, str(directory_name))
        try:
            if not os.path.exists(directory):
                os.mkdir(directory)
        except Exception as x:
            traceback.print_exception(Exception, x, x.__traceback__, chain=True)
            logger.critical("exception making {}".format(directory))
            exit(1)

    def set_text(self, _text):
        self.text = _text

    def set_title(self, _title):
        self.title = _title

    def set_table_title(self, _table_title):
        self.table_title = _table_title

    def set_graph_title(self, _graph_title):
        self.graph_title = _graph_title

    # sets the csv file name as graph title
    def set_csv_filename(self, _graph_title):
        fname, ext = os.path.splitext(_graph_title)
        self.csv_file_name = fname + ".csv"

    def write_dataframe_to_csv(self, _index=False):
        csv_file = "{path_date_time}/{csv_file_name}".format(path_date_time=self.path_date_time, csv_file_name=self.csv_file_name)
        self.dataframe.to_csv(csv_file, index=_index)

    # The _date is set when class is enstanciated / created so this set_date should be used with caution, used to synchronize results
    def set_date(self, _date):
        self.date = _date

    def set_table_dataframe(self, _dataframe):
        self.dataframe = _dataframe

    def set_table_dataframe_from_csv(self, _csv):
        self.dataframe = pd.read_csv(_csv)

    def set_table_dataframe_from_csv_sep_tab(self, _csv):
        self.dataframe = pd.read_csv(_csv, sep='\t')

    # TODO
    def set_table_dataframe_from_xlsx(self, _xlsx):
        self.dataframe = pd.read_excel(_xlsx)

    def set_custom_html(self, _custom_html):
        self.custom_html = _custom_html

    def set_obj_html(self, _obj_title, _obj):
        self.objective = _obj
        self.obj_title = _obj_title

    def set_desc_html(self, _desc_title, _desc):
        self.description = _desc
        self.desc_title = _desc_title

    def set_graph_image(self, _graph_image):
        self.graph_image = _graph_image

    def get_date(self):
        return self.date

    def get_path(self):
        return self.path

    def get_parent_path(self):
        parent_path = os.path.dirname(self.path)
        return parent_path

    # get_path_date_time, get_report_path and need to be the same
    def get_path_date_time(self):
        return self.path_date_time

    def get_report_path(self):
        return self.path_date_time

    def get_flat_dir_report_path(self):
        return self.path

    def get_log_path(self):
        return self.log_directory

    def file_add_path(self, file):
        output_file = str(self.path_date_time) + '/' + str(file)
        logger.info("output file {}".format(output_file))
        return output_file

    # Report Location:::/<locaton> as a key in lf_check.py

    def write_report_location(self):
        self.report_location = self.path_date_time
        logger.info("Report Location:::{report_location}".format(report_location=self.report_location))

    def write_html(self):
        if not self.output_html:
            logger.info("no html file name, skipping report generation")
            return
        if self.output_html.lower().endswith(".pdf"):
            raise ValueError("write_html: HTML filename [%s] should not end with .pdf" % self.output_html)
        if self.write_output_html.endswith(".pdf"):
            raise ValueError("wrong suffix for an HTML file: %s" % self.write_output_html)
        self.write_output_html = str(self.path_date_time) + '/' + str(self.output_html)
        logger.info("write_output_html: {}".format(self.write_output_html))
        try:
            test_file = open(self.write_output_html, "w")
            test_file.write(self.html)
            test_file.close()
        except Exception as x:
            traceback.print_exception(Exception, x, x.__traceback__, chain=True)
            logger.info("write_html failed")
        return self.write_output_html

    def write_index_html(self):
        if not self.output_html:
            logger.info("no html file name, skipping report generation")
            return
        self.write_output_index_html = str(self.path_date_time) + '/' + str("readme.html")
        logger.info("write_output_index_html: {}".format(self.write_output_index_html))
        try:
            test_file = open(self.write_output_index_html, "w")
            test_file.write(self.html)
            test_file.close()
        except Exception as x:
            traceback.print_exception(Exception, x, x.__traceback__, chain=True)
            logger.info("write_index_html failed")
        return self.write_output_index_html

    def write_html_with_timestamp(self):
        if not self.output_html:
            logger.info("no html file name, skipping report generation")
            return
        if self.output_html.lower().endswith(".pdf"):
            raise ValueError("write_html_with_timestamp: will not save file with PDF suffix [%s]" % self.output_html)
        self.write_output_html = "{}/{}-{}".format(self.path_date_time, self.date, self.output_html)
        logger.info("write_output_html: {}".format(self.write_output_html))
        try:
            test_file = open(self.write_output_html, "w")
            test_file.write(self.html)
            test_file.close()
        except Exception as x:
            traceback.print_exception(Exception, x, x.__traceback__, chain=True)
            logger.warning("write_html failed")
        return self.write_output_html

    # will put the set here
    def set_allure_environment_properties(self, allure_environment_properties=""):
        self.allure_environment_properties = allure_environment_properties

    def write_allure_environment_properties(self, allure_results_path=""):
        if allure_results_path == "":
            self.write_out_allure_environment_properties = "{}/environment.properties".format(self.path_date_time)
        else:
            self.allure_environment_properties_dir = allure_results_path
            self.write_out_allure_environment_properties = "{allure_results_path}/environment.properties".format(allure_results_path=allure_results_path)
        logger.info("write_out_allure_environment_properties: {}".format(self.write_out_allure_environment_properties))
        logger.info("allure_environment_properties_dir: {}".format(self.allure_environment_properties_dir))
        try:
            test_file = open(self.write_out_allure_environment_properties, "w")
            test_file.write(self.allure_environment_properties)
            test_file.close()
        except Exception as x:
            traceback.print_exception(Exception, x, x.__traceback__, chain=True)
            logger.warning("write_out_allure_environment_properties failed")
        return self.write_out_allure_environment_properties, self.allure_environment_properties_dir

    def set_allure_executor(self, allure_executor):
        self.allure_executor = allure_executor

    def write_allure_executor(self, allure_results_path=""):
        if allure_results_path == "":
            self.write_out_allure_executor = "{}/executor.json".format(self.path_date_time)
        else:
            self.write_out_allure_executor = "{allure_results_path}/executor.json".format(allure_results_path=allure_results_path)
            self.allure_executor_dir = allure_results_path
        logger.info("write_out_allure_executor: {}".format(self.write_out_allure_executor))
        logger.info("allure_executor_dir: {}".format(self.allure_executor_dir))
        try:
            test_file = open(self.write_out_allure_executor, "w")
            test_file.write(self.allure_executor)
            test_file.close()
        except Exception as x:
            traceback.print_exception(Exception, x, x.__traceback__, chain=True)
            logger.warning("write_out_allure_executor failed")
        return self.write_out_allure_executor, self.allure_executor_dir

    def set_junit_results(self, junit_results):
        self.junit = junit_results

    def write_junit_results(self, test_suite=""):
        self.junit_dir = "{}".format(self.path_date_time)
        if test_suite == "":
            self.write_output_junit = "{}/junit.xml".format(self.path_date_time)
        else:
            self.write_output_junit = "{dir}/{suite}_junit.xml".format(dir=self.path_date_time, suite=test_suite)
        logger.info("write_output_html: {}".format(self.write_output_html))
        logger.info("junit_dir: {}".format(self.junit_dir))
        try:
            test_file = open(self.write_output_junit, "w")
            test_file.write(self.junit)
            test_file.close()
        except Exception as x:
            traceback.print_exception(Exception, x, x.__traceback__, chain=True)
            logger.warning("write_junit failed")
        return self.write_output_junit, self.junit_dir

    def update_allure_results_history(self, allure_results_path=""):
        if allure_results_path == "":
            self.allure_results_history_path = os.path.join(self.path_date_time, "history")
            self.allure_results = "{allure_results_path}".format(allure_results_path=self.path_date_time)
        else:
            self.allure_results = allure_results_path
            self.allure_results_history_path = os.path.join(self.allure_results, "history")

        if not os.path.exists(self.allure_results_history_path):
            os.makedirs(self.allure_results_history_path)

        logger.info("copying history from {allure_report} to {allure_results}".format(allure_report=self.allure_report_history, allure_results=self.allure_results_history_path))

        if not os.path.exists(self.allure_results_history_path):
            os.makedirs(self.allure_results_history_path)

        if not os.path.exists(self.allure_report_history):
            os.makedirs(self.allure_report_history)

        try:
            files = os.listdir(self.allure_report_history)
            for fname in files:
                allure_report_history_file = str(self.allure_report_history_path) + '/' + str(fname)
                allure_results_history_file = str(self.allure_results_history_path) + '/' + str(fname)
                shutil.copy(allure_report_history_file, allure_results_history_file)
        except Exception as x:
            traceback.print_exception(Exception, x, x.__traceback__, chain=True)
            logger.warning("Either no allure report history present or the copy of history failed.")

    def copy_allure_report(self, allure_results_path=""):
        if allure_results_path == "":
            self.allure_results_history_path = os.path.join(self.path_date_time, "history")
            self.allure_results = "{allure_results_path}".format(allure_results_path=self.path_date_time)
        else:
            self.allure_results = allure_results_path
            self.allure_results_history_path = os.path.join(self.allure_results, "history")

        logger.info("copying history from {allure_report} to {allure_results}".format(allure_report=self.allure_report_history, allure_results=self.allure_results_history_path))

        if not os.path.exists(self.allure_results_history_path):
            os.makedirs(self.allure_results_history_path)

        try:
            files = os.listdir(self.allure_report_history)
            for fname in files:
                allure_report_history_file = str(self.allure_report_history_path) + '/' + str(fname)
                allure_results_history_file = str(self.allure_results_history_path) + '/' + str(fname)
                shutil.copy(allure_report_history_file, allure_results_history_file)
        except Exception as x:
            traceback.print_exception(Exception, x, x.__traceback__, chain=True)
            logger.info("Either no allure report present or the copy of history failed.")

    def generate_allure_report(self):
        allure_command = "allure generate {allure_results} --report-dir {allure_report} --clean".format(allure_results=self.allure_results, allure_report=self.allure_report_dir)
        try:
            logger.info("allure command: {allure_command}".format(allure_command=allure_command))
            summary = subprocess.Popen((allure_command), shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            out, err = summary.communicate()
            errcode = summary.returncode
            logger.info("allure out: {out} errcode: {errcode} err: {err}".format(
                out=out,
                errcode=errcode,
                err=err
            ))
        except Exception as x:
            traceback.print_exception(Exception, x, x.__traceback__, chain=True)
            logger.info("allure command: {allure_command} failed or timed out".format(allure_command=allure_command))

    # https://wkhtmltopdf.org/usage/wkhtmltopdf.txt
    # page_size A4, A3, Letter, Legal
    # orientation Portrait , Landscape
    @staticmethod
    def _write_pdf_file(input_html, output_pdf, options, configuration=None):
        """Run wkhtmltopdf, retrying once when its Qt renderer segfaults."""
        kwargs = {'options': options}
        if configuration is not None:
            kwargs['configuration'] = configuration

        try:
            pdfkit.from_file(input_html, output_pdf, **kwargs)
        except OSError as error:
            # wkhtmltopdf 0.12.x occasionally exits with SIGSEGV (-11) even
            # though the same document succeeds immediately afterward.
            if 'non-zero code -11' not in str(error):
                raise
            logger.warning('wkhtmltopdf crashed with exit code -11; retrying PDF generation once')
            pdfkit.from_file(input_html, output_pdf, **kwargs)

    def write_pdf(self, _page_size='A4', _orientation='Portrait'):
        if not self.output_pdf:
            logger.info("write_pdf: no pdf file name, skipping pdf output")
            return
        options = {"enable-local-file-access": None,
                   'orientation': _orientation,
                   'page-size': _page_size}
        self.write_output_pdf = str(self.path_date_time) + '/' + str(self.output_pdf)
        if (os_name == "Windows"):
            path_to_wkhtmltopdf = r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe'
            config = pdfkit.configuration(wkhtmltopdf=path_to_wkhtmltopdf)
            self._write_pdf_file(self.write_output_html, self.write_output_pdf, options, configuration=config)
        else:
            self._write_pdf_file(self.write_output_html, self.write_output_pdf, options)

    def write_pdf_with_timestamp(self, _page_size='A4', _orientation='Portrait'):
        if not self.output_pdf:
            logger.info("write_pdf_with_timestamp: no pdf file name, skipping pdf output")
            return
        options = {"enable-local-file-access": None,
                   'orientation': _orientation,
                   'page-size': _page_size}
        self.write_output_pdf = "{}/{}-{}".format(self.path_date_time, self.date, self.output_pdf)
        self._write_pdf_file(self.write_output_html, self.write_output_pdf, options)

    def get_pdf_path(self):
        pdf_link_path = "{}/{}-{}".format(self.path_date_time, self.date, self.output_pdf)
        return pdf_link_path

    def get_pdf_file(self):
        if not self.output_pdf:
            logger.info("get_pdf_file: no pdf name, returning None")
            return None
        pdf_file = "{}-{}".format(self.date, self.output_pdf)
        return pdf_file

    def build_pdf_link(self, _pdf_link_name, _pdf_link_path):
        self.pdf_link_html = """
            <!-- pdf link -->
            <a href="{pdf_link_path}" target="_blank">{pdf_link_name}</a>
            <br>
        """.format(pdf_link_path=_pdf_link_path, pdf_link_name=_pdf_link_name)
        self.html += self.pdf_link_html

    def build_link(self, _link_name, _link_path):
        self.link = """
            <!-- link -->
            <a href="{link_path}" target="_blank">{link_name}</a>
            <br>
        """.format(link_path=_link_path, link_name=_link_name)
        self.html += self.link

    def generate_report(self):
        self.write_html()
        if self.output_pdf:
            self.write_pdf()

    def build_all(self):
        self.build_banner()
        self.start_content_div()
        self.build_table_title()
        self.build_table()
        self.end_content_div()

    # These two helpers make the report work as one single .html file -- no report.css/custom.css/
    # echarts.min.js/images alongside it needed -- so it still looks and works right if someone
    # copies or emails just the one .html file instead of the whole report folder.
    _ASSET_MIME_TYPES = {".css": "text/css", ".js": "text/javascript", ".png": "image/png", ".woff": "font/woff"}

    def _read_report_asset(self, filename):
        """Reads a file already copied into this report's folder. Returns "" if it's missing,
        so a report still builds (just without that one piece) instead of crashing."""
        try:
            with open(os.path.join(self.path_date_time, filename), "r", encoding="utf-8") as f:
                return f.read()
        except OSError:
            return ""

    def _report_asset_as_data_uri(self, filename):
        """Turns a report asset (an image, a font) into a "data:...;base64,..." string that can go
        straight into an src="..." attribute, so the browser doesn't need to fetch a separate file."""
        try:
            with open(os.path.join(self.path_date_time, filename), "rb") as f:
                raw_bytes = f.read()
        except OSError:
            return filename
        ext = os.path.splitext(filename)[1].lower()
        mime = self._ASSET_MIME_TYPES.get(ext, "application/octet-stream")
        return "data:{};base64,{}".format(mime, base64.b64encode(raw_bytes).decode("ascii"))

    def get_html_head(self, title='Untitled'):
        report_css = self._read_report_asset("report.css")
        font_data_uri = self._report_asset_as_data_uri(self.font_file)
        report_css = report_css.replace('url("{}")'.format(self.font_file), 'url("{}")'.format(font_data_uri))
        custom_css = self._read_report_asset("custom.css")
        echarts_js = self._read_report_asset(self.echarts_file)
        return """<head>
        <meta charset='UTF-8'>
        <meta name='viewport' content='width=device-width, initial-scale=1' />
        <style>
        body {{ margin: 0; padding: 0; }}
        </style>
        <style>
        {report_css}
        </style>
        <style>
        {custom_css}
        </style>
        <script>
        {echarts_js}
        </script>
        <title>{title}</title>
    </head>""".format(title=title, report_css=report_css, custom_css=custom_css, echarts_js=echarts_js)

    def build_banner(self):
        self.banner_html = """<!DOCTYPE html>
<html lang='en'>
    {head_tag}
    <body>
        <div class='report-shell'>
        <div id='BannerBack'>
            <div id='Banner'>
                <img id='BannerLogo' align='right' src="{logo_data_uri}" border='0'/>
                <div class='HeaderStyle'>
                    <h1 class='TitleFontPrint'>{title}</h1>
                    <h4 class='TitleFontPrintSub'>{date}</h4>
                </div>
            </div>
        </div>
                 """.format(
            head_tag=self.get_html_head(title=self.title),
            logo_data_uri=self._report_asset_as_data_uri(self.logo_file_name),
            title=self.title,
            date=self.date,
        )
        self.html += self.banner_html

    def build_banner_left(self):
        self.banner_html = """<!DOCTYPE html>
<html lang='en'>
    {head_tag}
    <body>
        <div class='report-shell'>
        <div id='BannerBack'>
            <div id='BannerLeft'>
                <img id='BannerLogo' align='right' src="{logo_data_uri}" border='0'/>
                <div class='HeaderStyle'>
                    <h1 class='TitleFontPrint'>{title}</h1>
                    <h4 class='TitleFontPrintSub'>{date}</h4>
                </div>
            </div>
        </div>
                 """.format(
            head_tag=self.get_html_head(title=self.title),
            logo_data_uri=self._report_asset_as_data_uri(self.logo_file_name),
            title=self.title,
            date=self.date,
        )
        self.html += self.banner_html

    def build_banner_left_h2_font(self):
        self.banner_html = """<!DOCTYPE html>
<html lang='en'>
    {head_tag}
    <body>
        <div class='report-shell'>
        <div id='BannerBack'>
            <div id='BannerLeft'>
                <img id='BannerLogo' align='right' src="{logo_data_uri}" border='0'/>
                <div class='HeaderStyle'>
                    <h2 class='TitleFontPrint'>{title}</h2>
                    <h4 class='TitleFontPrintSub'>{date}</h4>
                </div>
            </div>
        </div>
                 """.format(
            head_tag=self.get_html_head(title=self.title),
            logo_data_uri=self._report_asset_as_data_uri(self.logo_file_name),
            title=self.title,
            date=self.date,
        )
        self.html += self.banner_html

    def build_banner_cover(self):
        self.banner_html = """<!DOCTYPE html>
       <html lang='en'>
           {head_tag}
           <body>
               <div class='report-shell'>
               <div id='BannerBack' style='height: 100%; max-height: 100%;'>
                   <div id='BannerLeft' style="margin: 0%; max-height: 100%; max-width: 100%; width: 100%; height: 100%;">
                       <img id='BannerLogo' align='right' src="{logo_data_uri}" border='0'/>
                       <div class='HeaderStyle'>
                           <h1 class='TitleFontPrint'>{title}</h1>
                           <h4 class='TitleFontPrintSub'>{date}</h4>
                       </div>
                   </div>
               </div>
                        """.format(
            head_tag=self.get_html_head(title=self.title),
            logo_data_uri=self._report_asset_as_data_uri(self.logo_file_name),
            title=self.title,
            date=self.date,
        )
        self.html += self.banner_html

    def build_table_title(self):
        self.table_title_html = """
                    <!-- Table Title-->
                    <h3 align='left'>{title}</h3>
                    """.format(title=self.table_title)
        self.html += self.table_title_html

    def start_content_div2(self):
        self.html += "\n<div class='contentDiv2'>\n"

    def start_content_div(self):
        self.html += "\n<div class='contentDiv'>\n"

    def build_text(self):
        # please do not use 'style=' tags unless you cannot override a class
        self.text_html = """
        <div class='HeaderStyle'>
            <h3 class='TitleFontPrint'>{text}</h3>\n
        </div>""".format(text=self.text)
        self.html += self.text_html

    def build_text_simple(self):
        self.text_html = """
            <p align='left' width='900'>{text}</p>
        """.format(text=self.text)
        self.html += self.text_html

    def build_date_time(self):
        self.date_time = str(datetime.datetime.now().strftime("%Y-%m-%d-%H-h-%m-m-%S-s")).replace(':', '-')
        return self.date_time

    def build_path_date_time(self):
        try:
            self.path_date_time = os.path.join(self.path, self.date_time)
            os.mkdir(self.path_date_time)
        except Exception as x:
            traceback.print_exception(Exception, x, x.__traceback__, chain=True)
            curr_dir_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.path_date_time = os.path.join(curr_dir_path, self.date_time)
            os.mkdir(self.path_date_time)

    def pass_fail_background(self, cell_value):
        highlight_success = 'background-color: #1d9a8a; color: #ffffff;'
        highlight_fail = 'background-color: #d95f5f; color: #ffffff;'
        if type(cell_value) in [str]:
            if cell_value == "Success":
                return highlight_success
            elif cell_value == "Failed":
                return highlight_fail

    def build_table(self):
        self.dataframe_html = self.dataframe.to_html(index=False, justify='center', classes='data-table')
        self.html += "<div class='table-wrap'>" + self.dataframe_html + "</div>"

    def pass_failed_build_table(self):
        # Render Success/Failed values as modern status badges instead of raw
        # cell background colors. This also sidesteps pandas Styler.hide_index(),
        # which was removed in current pandas and made this method unusable there.
        def _badge(value):
            if value == "Success":
                return '<span class="status-badge pass">Success</span>'
            if value == "Failed":
                return '<span class="status-badge fail">Failed</span>'
            return value

        badge_df = self.dataframe.applymap(_badge)
        self.dataframe_html = badge_df.to_html(index=False, justify='center', classes='data-table', escape=False)
        self.html += "<div class='table-wrap'>" + self.dataframe_html + "</div>"

    def rating_build_table(self, rating_column, rating_colors):
        """Like pass_failed_build_table(), but for an arbitrary column of rating labels (e.g.
        "Excellent"/"Good"/"Average"/"Poor") instead of a fixed Success/Failed pair -- renders
        that column's values as colored badges via inline styles rather than a raw text cell.

        Args:
            rating_column: name of the column in self.dataframe to badge.
            rating_colors: {label: css_color} -- labels not present here are left as plain text.
        """
        def _badge(value):
            color = rating_colors.get(value)
            if not color:
                return value
            return ("<span style='background:{color}; color:#fff; padding:2px 10px; "
                    "border-radius:10px; font-weight:600; white-space:nowrap;'>{value}</span>"
                    ).format(color=color, value=value)

        badge_df = self.dataframe.copy()
        badge_df[rating_column] = badge_df[rating_column].apply(_badge)
        self.dataframe_html = badge_df.to_html(index=False, justify='center', classes='data-table', escape=False)
        self.html += "<div class='table-wrap'>" + self.dataframe_html + "</div>"

    def save_csv(self, file_name, save_to_csv_data):
        save_to_csv_data.to_csv(str(self.path_date_time) + "/" + file_name)

    def save_pie_chart(self, pie_chart_data):
        pie_chart_data.plot.pie(y='Pass/Fail', autopct="%.2f%%", figsize=(8, 8), 
                                shadow=False, startangle=90,
                                colors=['#1d9a8a', '#d95f5f'])
        plt.tight_layout()
        plt.savefig(str(self.path_date_time) + '/pie-chart.png')
        plt.close()

    def save_bar_chart(self, xlabel, ylabel, bar_chart_data, name):
        plot = bar_chart_data.plot.bar(alpha=0.9, rot=0, width=0.9, linewidth=0.9, figsize=(10, 6),
                                       color=_ECHARTS_PALETTE)
        plot.legend(bbox_to_anchor=(1.0, 1.0))
        for p in plot.patches:
            height = p.get_height()
            plot.annotate('{}'.format(height),
                          xy=(p.get_x() + p.get_width() / 2, height),
                          xytext=(0, 0),
                          textcoords="offset points",
                          rotation=90,
                          annotation_clip=False,
                          ha='center', va='bottom')
        plt.xticks(rotation=0, horizontalalignment='right', fontweight='light', fontsize='small')
        plt.ylabel(ylabel)
        plt.tight_layout()
        plt.savefig(str(self.path_date_time) + '/' + name + '.png')
        plt.close()

    def test_setup_table(self, test_setup_data, value):
        if test_setup_data is None:
            return None
        else:
            var = ""
            for i in test_setup_data:
                var = var + "<tr><td>" + i + "</td><td colspan='3'>" + str(test_setup_data[i]) + "</td></tr>"

        setup_information = """
                            <!-- Test Setup Information -->
                            <div class='table-wrap'>
                            <table width='700px' cellpadding='2' cellspacing='0'>
                                <tr>
                                  <td>""" + str(value) + """</td>
                                  <td>
                                    <table width='100%' cellpadding='2' cellspacing='0'>
                                      """ + var + """
                                    </table>
                                  </td>
                                </tr>
                            </table>
                            </div>
                            <br>
                            """
        self.html += setup_information

    def build_footer(self):
        self.footer_html = """
    <footer class='FooterStyle'>
        <a href="https://www.candelatech.com/"><img
            id='BannerLogoFooter' align='right' src="{logo_footer_data_uri}" border='0'/></a>
        <p>Generated by Candela Technologies LANforge network testing tool</p>
        <p><a href="https://www.candelatech.com">www.candelatech.com</a><p>
    </footer>
    </div><!-- end report-shell -->
        """.format(logo_footer_data_uri=self._report_asset_as_data_uri(self.logo_footer_file_name))
        self.html += self.footer_html
        self.html += _SORTABLE_TABLE_JS

    def build_footer_no_png(self):
        self.footer_html = """
    <footer class='FooterStyle'>
        <p>Generate by Candela Technologies LANforge network testing tool</p>
        <p><a href="https://www.candelatech.com">www.candelatech.com</a><p>
    </footer>
    </div><!-- end report-shell -->"""
        self.html += self.footer_html
        self.html += _SORTABLE_TABLE_JS

    def copy_js(self):
        self.html += """
<script>
function fallbackCopyTextToClipboard(text) {
  var textArea = document.createElement("textarea");
  textArea.value = text;

  textArea.style.top = "0";
  textArea.style.left = "0";
  textArea.style.position = "fixed";

  document.body.appendChild(textArea);
  textArea.focus();
  textArea.select();

  try {
    var successful = document.execCommand('copy');
    var msg = successful ? 'successful' : 'unsuccessful';
    console.log('Fallback: Copying text command was ' + msg);
  } catch (err) {
    console.error('Fallback: Oops, unable to copy', err);
  }
  document.body.removeChild(textArea);
}
function copyTextToClipboard(ele) {
  var text = ele.innerHTML || '';
  if (!navigator.clipboard) {
    fallbackCopyTextToClipboard(text);
    return;
  }
  navigator.clipboard.writeText(text).then(function() {
    console.log('Async: Copying to clipboard was successful!');
  }, function(err) {
    console.error('Async: Could not copy text: ', err);
  });
}
</script>
        """

    def build_custom(self):
        self.html += self.custom_html

    def build_objective(self):
        self.obj_html = """
            <!-- Test Objective -->
            <h3 align='left'>{title}</h3>
            <p align='left' width='900'>{objective}</p>
            """.format(title=self.obj_title,
                       objective=self.objective)
        self.html += self.obj_html

    def build_description(self):
        self.obj_html = """
            <!-- Test Description -->
            <h3 align='left'>{title}</h3>
            <p align='left' width='900'>{description}</p>
            """.format(title=self.desc_title,
                       description=self.description)
        self.html += self.obj_html

    def build_graph_title(self):
        self.table_graph_html = """
            <div class='HeaderStyle'>
                <h2 class='TitleFontPrint'>{title}</h2>
            """.format(title=self.graph_title)
        self.html += self.table_graph_html

    def build_graph(self):
        content = str(self.graph_image)
        if _CHART_MARKUP_SENTINEL in content:
            # self.graph_image already holds a full interactive chart-card
            # (from lf_bar_graph/lf_bar_graph_horizontal/lf_line_graph) --
            # inline it directly instead of wrapping it in an <img> tag, and
            # make sure the shared JS runtime is on the page exactly once.
            if not self._echarts_runtime_emitted:
                self.html += _ECHARTS_RUNTIME_JS
                self._echarts_runtime_emitted = True
            self.graph_html_obj = content
        else:
            self.graph_html_obj = """
            <div class='chart-card'>
              <img src='{image}' alt='' />
            </div>
            """.format(image=content)
        self.html += self.graph_html_obj

    def build_graph_without_border(self):
        content = str(self.graph_image)
        if _CHART_MARKUP_SENTINEL in content:
            if not self._echarts_runtime_emitted:
                self.html += _ECHARTS_RUNTIME_JS
                self._echarts_runtime_emitted = True
            self.graph_html_obj = content
        else:
            self.graph_html_obj = """
            <div class='chart-card' style='text-align:left;'>
              <img src='{image}' alt='' />
            </div>
            """.format(image=content)
        self.html += self.graph_html_obj

    def end_content_div(self):
        self.html += "\n</div><!-- end contentDiv -->\n"

    def build_chart_title(self, chart_title):
        self.chart_title_html = """
            <div class='HeaderStyle'>
                <h3 class='TitleFontPrint'>{title}</h3>
            """.format(title=chart_title)
        self.html += self.chart_title_html

    def build_chart(self, name):
        self.chart_html_obj = """
            <div class='chart-card' style='max-width:500px;margin-left:auto;margin-right:auto;'>
              <img src='{image}' alt=''/>
            </div>
            """.format(image=name)
        self.html += self.chart_html_obj

    def build_chart_custom(self, name, align='center', padding='15px', margin='5px 5px 2em 5px', width='500px', height='500px'):
        self.chart_html_obj = """
            <div class='chart-card' style='text-align:{align};padding:{padding};margin:{margin};'>
              <img src='{image}' style='width:{width};height:{height};' alt=''/>
            </div>
            """.format(image=name, align=align, padding=padding, margin=margin, width=width, height=height)
        self.html += self.chart_html_obj

    # ------------------------------------------------------------------
    # New, additive capability (not used by any legacy caller): renders a
    # genuine interactive ECharts chart using the same styling conventions
    # (palette, baseOption, tooltip/legend/axis/dataZoom, named-series
    # coloring) as the reusable render* functions above. Legacy image-based
    # methods (build_graph/build_chart/save_pie_chart/save_bar_chart) cannot
    # be converted to this because their existing API only ever carries an
    # already-rendered image path or a DataFrame meant to be rasterized --
    # never the raw series data an interactive chart needs.
    # ------------------------------------------------------------------
    def build_echarts_chart(self, chart_id, chart_type, payload, title="", y_name="", x_name=""):
        """Add an interactive ECharts chart-card.

        chart_id: unique DOM id for the chart container.
        chart_type: one of "line", "bar", "horizontal_bar",
            "connectivity_timeline", "pie".
        payload: dict matching the shape the corresponding JS renderer expects,
            e.g. {"categories": [...], "series": [{"name": ..., "data": [...]}, ...]}
            for line/bar/horizontal_bar; {"clients": [...], "segments": [...],
            "duration": ...} for connectivity_timeline; or
            {"slices": [{"name": ..., "value": ...}, ...]} for pie.
        """
        if not self._echarts_runtime_emitted:
            self.html += _ECHARTS_RUNTIME_JS
            self._echarts_runtime_emitted = True
        self.html += _chart_markup(chart_id, chart_type, payload, title=title, y_name=y_name, x_name=x_name)

    def build_pie_chart_interactive(self, chart_id, labels, values, title=""):
        """Interactive donut/pie chart from parallel labels/values lists.
        (lf_graph.py has no pie-chart class to mirror, so this stays a
        report-level convenience rather than a standalone class.)
        Kept for existing callers; delegates to the generic create_pie_chart()
        module function -- see that function for the full option set (center
        labels, subtitles, custom tooltips, percentages, dimensions, ...)."""
        data = [{"name": labels[i], "value": values[i]} for i in range(len(labels))]
        if not self._echarts_runtime_emitted:
            self.html += _ECHARTS_RUNTIME_JS
            self._echarts_runtime_emitted = True
        self.html += create_pie_chart(data, title=title, chart_id=chart_id, show_percentage=False)

    def build_pie_chart(self, data, title="", **kwargs):
        """Add a create_pie_chart() chart directly to the report (handles the
        one-time ECharts runtime injection for callers not going through
        set_graph_image()/build_graph()). See create_pie_chart() for the full
        set of optional kwargs (subtitle, chart_id, legend, show_percentage,
        center_label, tooltip_formatter, label_formatter, width, height,
        radius, center, empty_message)."""
        if not self._echarts_runtime_emitted:
            self.html += _ECHARTS_RUNTIME_JS
            self._echarts_runtime_emitted = True
        self.html += create_pie_chart(data, title=title, **kwargs)

    def build_info_card(self, title, items, icon=None, card_id=None):
        """Add a create_info_card() card directly to the report. See
        create_info_card() for the full option set."""
        self.html += create_info_card(title, items, icon=icon, card_id=card_id)

    def build_findings_card(self, title, findings, card_id=None):
        """Add a create_findings_card() card directly to the report. See
        create_findings_card() for the full option set."""
        self.html += create_findings_card(title, findings, card_id=card_id)

    def build_device_summary_card(self, devices, **kwargs):
        """Add a create_device_summary_card() card directly to the report
        (handles the one-time ECharts + search-table runtime injection).
        See create_device_summary_card() for the full set of optional
        kwargs (name_field, platform_field, columns, platform_icons,
        page_size, card_id, title)."""
        if not self._echarts_runtime_emitted:
            self.html += _ECHARTS_RUNTIME_JS
            self._echarts_runtime_emitted = True
        if not self._table_runtime_emitted:
            self.html += _TABLE_RUNTIME_JS
            self._table_runtime_emitted = True
        self.html += create_device_summary_card(devices, **kwargs)


def _chart_markup(chart_id, chart_type, payload, title="", y_name="", x_name=""):
    """Build the <div class='chart-card'>...</div> markup (chart container +
    inline script invoking the shared JS renderer) for one chart. Used by
    lf_report.build_echarts_chart() (which also injects the JS runtime once
    per page) and by the standalone lf_bar_graph/lf_bar_graph_horizontal/
    lf_line_graph classes below, whose build_*() methods return this same
    markup instead of saving a matplotlib PNG -- the runtime script is
    injected once the caller hands the markup to lf_report.build_graph().
    """
    renderer_by_type = {
        "line": "renderLineChart",
        "bar": "renderBarChart",
        "horizontal_bar": "renderHorizontalBarChart",
        "connectivity_timeline": "renderConnectivityTimeline",
        "pie": "renderPieChart",
    }
    renderer = renderer_by_type.get(chart_type)
    if renderer is None:
        raise ValueError("unknown chart_type '{}' (expected one of {})".format(
            chart_type, list(renderer_by_type)))

    extra_args = ""
    if chart_type in ("line", "bar"):
        extra_args = ", {y}, {x}".format(y=json.dumps(y_name), x=json.dumps(x_name))
    elif chart_type == "horizontal_bar":
        extra_args = ", {x}".format(x=json.dumps(x_name))

    return """
            <div class='chart-card'>
              {title_html}
              <div id='{chart_id}' class='chart'></div>
              <script>
                window.__lfModernReport.{renderer}({chart_id_json}, {payload}{extra_args});
              </script>
            </div>
            """.format(
        title_html=("<h3>{}</h3>".format(title) if title else ""),
        chart_id=chart_id,
        chart_id_json=json.dumps(chart_id),
        renderer=renderer,
        payload=json.dumps(payload),
        extra_args=extra_args,
    )


def _sanitize_pie_slices(data):
    """Coerce a generic pie-chart `data` argument into a clean list of
    {"name": str, "value": float} slices, dropping/repairing anything that
    would otherwise crash json.dumps(), produce a NaN percentage in ECharts,
    or silently render nothing. Never raises -- worst case returns []."""
    if not data:
        return []
    slices = []
    for item in data:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if name is None or str(name).strip() == "":
            continue
        value = item.get("value")
        if value is None:
            value = 0
        try:
            value = float(value)
        except (TypeError, ValueError):
            value = 0
        if value < 0 or value != value:  # negative or NaN
            value = 0
        slices.append({"name": str(name), "value": value})
    return slices


def create_pie_chart(data, title="", subtitle="", chart_id=None, legend=True,
                     show_percentage=True, show_labels=True, center_label=None,
                     tooltip_formatter=None, label_formatter=None, colors=None,
                     item_details=None, width=None, height=None, radius=None, center=None,
                     empty_message="No data available"):
    """Build a single reusable, self-contained ECharts pie/donut chart-card.

    This is the one generic pie-chart building block for the whole report --
    every section that needs a pie chart (RSSI distribution, pass/fail
    summary, band distribution, device connectivity, ...) should call this
    instead of hand-rolling its own chart markup.

    Args:
        data: generic slice list, e.g.
            [{"name": "Pass", "value": 80}, {"name": "Fail", "value": 15}].
            Category names are never hard-coded here -- pass whatever this
            report section's categories are. Missing/None/negative/non-numeric
            values are coerced to 0 rather than raising; entries without a
            usable "name" are dropped. Empty/None `data` is handled gracefully
            (renders an inline "no data" card instead of a chart).
        title: chart title, rendered above the chart (h3).
        subtitle: optional one-line description rendered under the title.
        chart_id: unique DOM id for the chart container. Auto-generated
            (and guaranteed unique within the process) when omitted, so
            multiple pie charts can be dropped into one report without the
            caller having to invent/track ids.
        legend: show/hide the bottom legend.
        show_percentage: show "<name> <percent>%" on each slice label (the
            tooltip always shows both the raw value and the percentage
            regardless of this flag, e.g. "Passed: 85 (85%)").
        show_labels: show/hide the on-slice text labels entirely (independent
            of show_percentage) -- turn off for a small/compact donut where
            slice labels would just overlap; the tooltip is unaffected.
        center_label: optional text shown in the middle of the donut hole.
            Either a plain string, or {"main": "70%", "sub": "Online"} for a
            two-line main/sub label (e.g. a total count with a caption).
        tooltip_formatter / label_formatter: optional raw ECharts formatter
            strings (e.g. "{b}: {c}") to override the defaults above.
        colors: optional list of CSS colors, one per slice in `data` order
            (e.g. a green-to-red severity gradient) -- overrides the report's
            default color palette for this one chart.
        item_details: optional {slice_name: [detail line, ...]} shown in the
            tooltip when hovering that slice, in place of just its count --
            e.g. the actual clients behind one signal-quality bucket's count.
            A slice with no entry (or an empty list) shows "none".
        width / height: optional CSS size for the chart container (int -> px,
            or any CSS length string, e.g. "480px", "60%").
        radius / center: optional ECharts pie radius/center overrides (2-item
            lists), e.g. radius=["0%", "70%"] for a solid pie instead of a
            donut, or center=["50%", "50%"] to drop the legend-reserved gap.
        empty_message: message shown when `data` is empty/None or every value
            is 0 (avoids ECharts rendering an all-NaN-percentage chart).

    Returns:
        HTML string: a self-contained "<div class='chart-card'>...</div>"
        chart card (container + inline init call, no title/subtitle markup
        omitted). Hand it to lf_report via
        `report.set_graph_image(chart_html); report.build_graph()` (same
        pattern used by lf_bar_graph/lf_line_graph's build_*() markup), or
        append it directly to an `lf_report` instance's `.html` after making
        sure the shared ECharts runtime has been emitted once (see
        lf_report.build_echarts_chart / build_pie_chart_interactive for that
        pattern) if not routing through set_graph_image()/build_graph().
    """
    chart_id = chart_id or _next_chart_id("pie-chart")
    slices = _sanitize_pie_slices(data)
    total = sum(s["value"] for s in slices)

    title_html = "<h3>{}</h3>".format(title) if title else ""
    subtitle_html = "<p class='chart-subtitle'>{}</p>".format(subtitle) if subtitle else ""

    if not slices or total <= 0:
        # Graceful empty/all-zero fallback -- still valid, self-contained
        # markup (no chart gets initialized, so no NaN percentages), and
        # visually matches the client-side renderFallback() look.
        return """
            <div class='chart-card'>
              {title_html}
              {subtitle_html}
              <div id='{chart_id}' class='chart'>
                <div class='chart-fallback'>{message}</div>
              </div>
            </div>
            """.format(
            title_html=title_html,
            subtitle_html=subtitle_html,
            chart_id=chart_id,
            message=empty_message,
        )

    payload = {"slices": slices, "showPercentage": bool(show_percentage)}
    if not legend:
        payload["legend"] = False
    if not show_labels:
        payload["showLabels"] = False
    if center_label is not None:
        payload["centerLabel"] = center_label
    if tooltip_formatter:
        payload["tooltipFormatter"] = tooltip_formatter
    if label_formatter:
        payload["labelFormatter"] = label_formatter
    if colors:
        payload["colors"] = list(colors)
    if item_details:
        payload["itemDetails"] = item_details
    if radius:
        payload["radius"] = list(radius)
    if center:
        payload["center"] = list(center)

    style_parts = []
    if width:
        style_parts.append("width:{}".format(width if isinstance(width, str) else "{}px".format(width)))
    if height:
        style_parts.append("height:{}".format(height if isinstance(height, str) else "{}px".format(height)))
    container_style = " style='{}'".format(";".join(style_parts)) if style_parts else ""

    return """
            <div class='chart-card'>
              {title_html}
              {subtitle_html}
              <div id='{chart_id}' class='chart'{container_style}></div>
              <script>
                window.__lfModernReport.renderPieChart({chart_id_json}, {payload});
              </script>
            </div>
            """.format(
        title_html=title_html,
        subtitle_html=subtitle_html,
        chart_id=chart_id,
        container_style=container_style,
        chart_id_json=json.dumps(chart_id),
        payload=json.dumps(payload),
    )


def create_info_card(title, items, icon=None, card_id=None):
    """Build a reusable "info card": a titled card containing a responsive
    grid of icon + label + value blocks -- e.g. a test's configuration
    summary (traffic type, duration, rates, ...). Generic across scripts:
    nothing here is tied to any particular kind of test or field, the
    caller supplies whatever (icon, label, value) triples make sense for
    their report.

    Args:
        title: card header text, e.g. "Test Configuration".
        items: list of {"icon": <inline HTML, optional>, "label": str,
            "value": str}. Items with a missing/empty value are skipped.
            `icon` may be any inline HTML snippet (an emoji character, an
            inline "<svg>...</svg>", ...) -- this function doesn't
            interpret it, just places it in a small badge; items with no
            icon get no badge at all (just the label/value box).
        icon: optional inline HTML for the card header's own icon badge.
        card_id: optional DOM id for the card (only useful if a script
            wants to reference/style a specific card).

    Returns:
        HTML string: a self-contained "<div class='info-card'>...</div>".
    """
    rows = []
    for item in items or []:
        value = item.get("value")
        if value is None or str(value).strip() == "":
            continue
        item_icon_html = "<div class='icon-badge'>{}</div>".format(item["icon"]) if item.get("icon") else ""
        rows.append("""
            <div class='info-item'>
              {icon}
              <div class='info-item-body'>
                <div class='info-item-label'>{label}</div>
                <div class='info-item-value'>{value}</div>
              </div>
            </div>
            """.format(icon=item_icon_html, label=item.get("label", ""), value=value))

    id_attr = " id='{}'".format(card_id) if card_id else ""
    header_icon_html = "<div class='icon-badge'>{}</div>".format(icon) if icon else ""

    return """
            <div class='info-card'{id_attr}>
              <div class='info-card-header'>{header_icon}{title}</div>
              <div class='info-grid'>{rows}</div>
            </div>
            """.format(id_attr=id_attr, header_icon=header_icon_html, title=title, rows="".join(rows))


_FINDING_TYPE_ICON = {"positive": "&#10003;", "neutral": "&bull;", "warning": "&#9888;", "critical": "&#10007;"}


def create_findings_card(title, findings, card_id=None):
    """Build a reusable "Key Findings" style card: a short, prioritized
    bulleted list of plain-English observations, each tagged with a subtle
    severity marker (checkmark/dot/warning/cross) rather than a raw value
    dump. Generic across scripts -- this function has no idea what a
    "throughput" or "RSSI" or "band" is, it only renders whatever finding
    dicts a caller hands it; a script's own analysis code decides what the
    findings say.

    Args:
        title: card header text, e.g. "Key Findings".
        findings: list of {"type": "positive"|"neutral"|"warning"|"critical"
            (optional, defaults to "neutral"), "text": str}, most important
            first. Findings with empty/missing text are skipped.
        card_id: optional DOM id for the card.

    Returns:
        HTML string: a self-contained "<div class='info-card'>...</div>".
        If `findings` is empty (or every entry is empty), renders a plain
        "no findings" message instead of an empty list.
    """
    items = []
    for f in findings or []:
        text = f.get("text")
        if not text or not str(text).strip():
            continue
        ftype = f.get("type") if f.get("type") in _FINDING_TYPE_ICON else "neutral"
        items.append("""
            <li class='finding finding-{ftype}'>
              <span class='finding-icon'>{icon}</span>
              <span class='finding-text'>{text}</span>
            </li>
            """.format(ftype=ftype, icon=_FINDING_TYPE_ICON[ftype], text=text))

    id_attr = " id='{}'".format(card_id) if card_id else ""

    if not items:
        return """
            <div class='info-card'{id_attr}>
              <div class='info-card-header'>{title}</div>
              <p style='color:var(--muted);'>No findings available for this data.</p>
            </div>
            """.format(id_attr=id_attr, title=title)

    return """
            <div class='info-card'{id_attr}>
              <div class='info-card-header'>{title}</div>
              <ul class='findings-list'>{items}</ul>
            </div>
            """.format(id_attr=id_attr, title=title, items="".join(items))


def create_device_summary_card(devices, name_field="name", platform_field="platform",
                               columns=None, platform_icons=None, page_size=10,
                               card_id=None, title="Devices"):
    """Build a reusable "device summary" card: total/per-category counts, a
    donut breakdown, and a searchable, paginated table. Generic across
    scripts -- despite the name, `devices` can be any list of dicts: real
    clients, IoT devices, APs, whatever the caller's "platform"/category
    field is; nothing here is Wi-Fi- or device-specific.

    Args:
        devices: list of dicts, e.g.
            [{"name": "vivo V12", "platform": "Android"}, ...].
        name_field / platform_field: which keys in each device dict hold its
            display name and its category (used for the counts/donut).
        columns: table columns as [{"key": ..., "label": ...}, ...].
            Defaults to name_field -> "Device Name", platform_field ->
            "Platform".
        platform_icons: optional {category_value: inline HTML/emoji} shown
            next to that category's count. Categories without an entry get
            a plain bullet.
        page_size: initial rows-per-page for the table (also offered in the
            rows-per-page dropdown alongside 5/10/25/50 and "All").
        card_id: DOM id prefix. Auto-generated when omitted, so multiple
            device cards on one page never collide.
        title: card header text.

    Returns:
        HTML string: a self-contained "<div class='info-card'>...</div>"
        card (stats + donut + search/paginated table, with their init
        script). The caller must make sure the shared ECharts and table
        runtimes are already on the page -- lf_report.build_device_summary_card()
        does that for you; going straight through create_device_summary_card()
        means injecting _ECHARTS_RUNTIME_JS and _TABLE_RUNTIME_JS yourself
        (once each, same convention as every other interactive chart here).
    """
    devices = devices or []
    card_id = card_id or _next_chart_id("device-summary")
    columns = columns or [{"key": name_field, "label": "Device Name"}, {"key": platform_field, "label": "OS type"}]
    platform_icons = platform_icons or {}

    if not devices:
        return """
            <div class='info-card' id='{card_id}'>
              <div class='info-card-header'>{title}</div>
              <p style='color:var(--muted);'>No devices to show.</p>
            </div>
            """.format(card_id=card_id, title=title)

    total = len(devices)
    platform_counts = {}
    for d in devices:
        p = d.get(platform_field) or "Unknown"
        platform_counts[p] = platform_counts.get(p, 0) + 1
    # Count-descending so the biggest group leads, same as the stat row.
    ordered_platforms = sorted(platform_counts, key=lambda p: -platform_counts[p])

    stat_items = "".join("""
            <div class='device-stat'>
              <div class='icon-badge'>{icon}</div>
              <div>
                <div class='stat-value'>{count}</div>
                <div class='stat-label'>{label}</div>
              </div>
            </div>
            """.format(icon=platform_icons.get(p, "&bull;"), count=platform_counts[p], label=p)
        for p in ordered_platforms)
    stats_html = """
            <div class='device-stats-col'>
              <div class='device-stat'>
                <div class='icon-badge'>&#9679;</div>
                <div>
                  <div class='stat-value'>{total}</div>
                  <div class='stat-label'>Total Devices</div>
                </div>
              </div>
              {stat_items}
            </div>
            """.format(total=total, stat_items=stat_items)

    slices, legend_items = [], []
    for i, p in enumerate(ordered_platforms):
        count = platform_counts[p]
        pct = count / total * 100
        color = _ECHARTS_PALETTE[i % len(_ECHARTS_PALETTE)]
        slices.append({"name": p, "value": count})
        legend_items.append("""
            <div class='device-legend-item'>
              <span class='device-legend-dot' style='background:{color}'></span>
              <span class='device-legend-name'>{name} ({count})</span>
              <span class='device-legend-pct'>{pct:.1f}%</span>
            </div>
            """.format(color=color, name=p, count=count, pct=pct))

    donut_id = "{}-donut".format(card_id)
    donut_payload = {"slices": slices, "legend": False, "showLabels": False,
                     "tooltipFormatter": "{b}: {c} ({d}%)"}
    donut_html = """
            <div class='device-donut-col'>
              <div id='{donut_id}' class='device-donut'></div>
              <div class='device-legend'>{legend}</div>
            </div>
            <script>
              window.__lfModernReport.renderPieChart({donut_id_json}, {donut_payload});
            </script>
            """.format(donut_id=donut_id, legend="".join(legend_items),
                       donut_id_json=json.dumps(donut_id), donut_payload=json.dumps(donut_payload))

    rows_payload = []
    for d in devices:
        cells = "".join("<td>{}</td>".format(d.get(c["key"], "")) for c in columns)
        search_text = " ".join(str(d.get(c["key"], "")) for c in columns).lower()
        rows_payload.append({"cellsHtml": cells, "searchText": search_text})
    header_cells = "".join("<th>{}</th>".format(c["label"]) for c in columns)

    default_page_size = min(page_size, total) if page_size else total
    size_choices = sorted({n for n in (5, 10, 25, 50, default_page_size) if n <= total})
    page_size_options = "".join(
        "<option value='{n}'{sel}>{n}</option>".format(n=n, sel=" selected" if n == default_page_size else "")
        for n in size_choices
    ) + "<option value='all'>All</option>"

    return """
            <div class='info-card' id='{card_id}'>
              <div class='info-card-header'>{title}</div>
              <div class='device-summary-row'>
                {stats}
                {donut}
              </div>
              <div class='device-toolbar'>
                <input class='device-search' type='text' placeholder='Search device...' />
                <button class='btn-outline view-all-btn' type='button'>View All Devices</button>
              </div>
              <p class='device-count-label'></p>
              <div class='table-wrap'>
                <table class='device-table'>
                  <thead><tr><th>S.No.</th>{header_cells}</tr></thead>
                  <tbody></tbody>
                </table>
              </div>
              <div class='device-footer'>
                <div class='rows-per-page'>Rows per page: <select>{page_size_options}</select></div>
                <div class='pagination'></div>
              </div>
              <script>
                window.__lfModernReport.initSearchTable({card_id_json}, {rows}, {default_page_size});
              </script>
            </div>
            """.format(
        card_id=card_id, title=title, stats=stats_html, donut=donut_html,
        header_cells=header_cells, page_size_options=page_size_options,
        card_id_json=json.dumps(card_id), rows=json.dumps(rows_payload),
        default_page_size=default_page_size,
    )


_CHART_MARKUP_SENTINEL = "<div class='chart-card'>"

# matplotlib single-letter shorthand color codes translated to real CSS colors,
# for scripts that pass e.g. _color=['r', 'g', 'b'] to the chart classes below.
_MPL_SHORTHAND_COLORS = {
    'r': 'red', 'g': 'green', 'b': 'blue', 'c': 'cyan',
    'm': 'magenta', 'y': '#bfbf00', 'k': 'black', 'w': 'white',
}


def _css_color(c):
    return _MPL_SHORTHAND_COLORS.get(c, c) if isinstance(c, str) else c


class lf_bar_graph:
    """Drop-in replacement for lf_graph.py's lf_bar_graph: identical constructor
    signature, but build_bar_graph() returns interactive chart-card markup
    (for use with lf_report.set_graph_image()/build_graph()) instead of saving
    a matplotlib PNG. See lf_graph.lf_bar_graph for the original."""

    def __init__(self, _data_set=None,
                 _xaxis_name="x-axis",
                 _yaxis_name="y-axis",
                 _xaxis_categories=None,
                 _xaxis_label=None,
                 _graph_title="",
                 _title_size=16,
                 _graph_image_name="image_name",
                 _label=None,
                 _color=None,
                 _bar_width=0.25,
                 _color_edge='grey',
                 _font_weight='bold',
                 _color_name=None,
                 _figsize=(10, 5),
                 _show_bar_value=False,
                 _xaxis_step=1,
                 _xticks_font=None,
                 _xaxis_value_location=0,
                 _xticks_rotation=None,
                 _text_font=None,
                 _text_rotation=None,
                 _grp_title="",
                 _legend_handles=None,
                 _legend_loc="best",
                 _legend_box=None,
                 _legend_ncol=1,
                 _legend_fontsize=None,
                 _dpi=96,
                 _enable_csv=False,
                 _remove_border=None,
                 _alignment=None,
                 _stacked=False,
                 _extra_payload=None
                 ):
        if _data_set is None:
            _data_set = [[30.4, 55.3, 69.2, 37.1], [45.1, 67.2, 34.3, 22.4], [22.5, 45.6, 12.7, 34.8]]
        if _xaxis_categories is None:
            _xaxis_categories = [1, 2, 3, 4]
        if _xaxis_label is None:
            _xaxis_label = ["a", "b", "c", "d"]
        if _label is None:
            _label = ["bi-downlink", "bi-uplink", 'uplink']
        if _color_name is None:
            # brand palette (starts #1f6f58, #f1b24a) instead of lf_graph.py's
            # matplotlib defaults, so charts that don't customize colors get
            # the company theme colors -- callers passing their own _color or
            # _color_name are unaffected.
            _color_name = list(_ECHARTS_PALETTE)
        self.data_set = _data_set
        self.xaxis_name = _xaxis_name
        self.yaxis_name = _yaxis_name
        self.xaxis_categories = _xaxis_categories
        self.xaxis_label = _xaxis_label
        self.title = _graph_title
        self.title_size = _title_size
        self.graph_image_name = _graph_image_name
        self.label = _label
        self.color = _color
        self.bar_width = _bar_width
        self.color_edge = _color_edge
        self.font_weight = _font_weight
        self.color_name = _color_name
        self.figsize = _figsize
        self.show_bar_value = _show_bar_value
        self.xaxis_step = _xaxis_step
        self.xticks_font = _xticks_font
        self._xaxis_value_location = _xaxis_value_location
        self.text_font = _text_font
        self.text_rotation = _text_rotation
        self.grp_title = _grp_title
        self.enable_csv = _enable_csv
        self.legend_handles = _legend_handles
        self.legend_loc = _legend_loc
        self.legend_box = _legend_box
        self.legend_ncol = _legend_ncol
        self.legend_fontsize = _legend_fontsize
        self.remove_border = _remove_border
        self.alignment = _alignment
        self.xticks_rotation = _xticks_rotation
        self.stacked = _stacked
        self.extra_payload = _extra_payload

    def build_bar_graph(self):
        colors = self.color if self.color is not None else self.color_name
        # a single series with as many categories as bars gets one color per
        # bar/category (mirrors how scripts use this for e.g. per-item counts);
        # multiple series each get one color, same as the matplotlib version.
        if len(self.data_set) == 1:
            series = [{
                "name": self.label[0] if self.label else "series-0",
                "data": [
                    {"value": v, "itemStyle": {"color": _css_color(colors[i % len(colors)])}}
                    for i, v in enumerate(self.data_set[0])
                ],
            }]
        else:
            series = [
                {
                    "name": self.label[i] if i < len(self.label) else "series-{}".format(i),
                    "data": self.data_set[i],
                    "color": _css_color(colors[i % len(colors)]),
                }
                for i in range(len(self.data_set))
            ]

        if self.xaxis_label and len(self.xaxis_label) == len(self.data_set[0]):
            categories = [str(c) for c in self.xaxis_label]
        else:
            categories = [str(c) for c in self.xaxis_categories]

        payload = {"categories": categories, "series": series}
        if self.stacked:
            payload["stacked"] = True
        if self.extra_payload:
            payload.update(self.extra_payload)
        markup = _chart_markup(self.graph_image_name, "bar", payload,
                               title=self.title, x_name=self.xaxis_name, y_name=self.yaxis_name)

        if self.enable_csv:
            if self.xaxis_categories is not None and len(self.xaxis_categories) == len(self.data_set[0]):
                lf_csv_obj = lf_csv()
                lf_csv_obj.columns = [self.xaxis_name] + list(self.label)
                lf_csv_obj.rows = [self.xaxis_categories] + list(self.data_set)
                lf_csv_obj.filename = "{}.csv".format(self.graph_image_name)
                lf_csv_obj.generate_csv()
            else:
                raise ValueError("Length and x-axis values and y-axis values should be same.")

        return markup


class lf_bar_graph_horizontal:
    """Drop-in replacement for lf_graph.py's lf_bar_graph_horizontal: identical
    constructor signature, but build_bar_graph_horizontal() returns interactive
    chart-card markup instead of saving a matplotlib PNG."""

    def __init__(self, _data_set=None,
                 _xaxis_name="x-axis",
                 _yaxis_name="y-axis",
                 _yaxis_categories=None,
                 _yaxis_label=None,
                 _graph_title="",
                 _title_size=16,
                 _graph_image_name="image_name",
                 _label=None,
                 _color=None,
                 _bar_height=0.25,
                 _color_edge='grey',
                 _font_weight='bold',
                 _color_name=None,
                 _figsize=(10, 5),
                 _show_bar_value=False,
                 _yaxis_step=1,
                 _yticks_font=None,
                 _yaxis_value_location=0,
                 _yticks_rotation=None,
                 _text_font=None,
                 _text_rotation=None,
                 _grp_title="",
                 _legend_handles=None,
                 _legend_loc="best",
                 _legend_box=None,
                 _legend_ncol=1,
                 _legend_fontsize=None,
                 _dpi=96,
                 _enable_csv=False,
                 _remove_border=None,
                 _alignment=None,
                 _stacked=False
                 ):
        if _data_set is None:
            _data_set = [[30.4, 55.3, 69.2, 37.1], [45.1, 67.2, 34.3, 22.4], [22.5, 45.6, 12.7, 34.8]]
        if _yaxis_categories is None:
            _yaxis_categories = [1, 2, 3, 4]
        if _yaxis_label is None:
            _yaxis_label = ["a", "b", "c", "d"]
        if _label is None:
            _label = ["bi-downlink", "bi-uplink", 'uplink']
        if _color_name is None:
            # brand palette (starts #1f6f58, #f1b24a) instead of lf_graph.py's
            # matplotlib defaults, so charts that don't customize colors get
            # the company theme colors -- callers passing their own _color or
            # _color_name are unaffected.
            _color_name = list(_ECHARTS_PALETTE)
        self.data_set = _data_set
        self.xaxis_name = _xaxis_name
        self.yaxis_name = _yaxis_name
        self.yaxis_categories = _yaxis_categories
        self.yaxis_label = _yaxis_label
        self.title = _graph_title
        self.title_size = _title_size
        self.graph_image_name = _graph_image_name
        self.label = _label
        self.color = _color
        self.bar_height = _bar_height
        self.color_edge = _color_edge
        self.font_weight = _font_weight
        self.color_name = _color_name
        self.figsize = _figsize
        self.show_bar_value = _show_bar_value
        self.yaxis_step = _yaxis_step
        self.yticks_font = _yticks_font
        self._yaxis_value_location = _yaxis_value_location
        self.text_font = _text_font
        self.text_rotation = _text_rotation
        self.grp_title = _grp_title
        self.enable_csv = _enable_csv
        self.legend_handles = _legend_handles
        self.legend_loc = _legend_loc
        self.legend_box = _legend_box
        self.legend_ncol = _legend_ncol
        self.legend_fontsize = _legend_fontsize
        self.remove_border = _remove_border
        self.alignment = _alignment
        self.yticks_rotation = _yticks_rotation
        self.stacked = _stacked

    def build_bar_graph_horizontal(self):
        colors = self.color if self.color is not None else self.color_name
        series = [
            {
                "name": self.label[i] if i < len(self.label) else "series-{}".format(i),
                "data": self.data_set[i],
                "color": _css_color(colors[i % len(colors)]),
            }
            for i in range(len(self.data_set))
        ]

        if self.yaxis_label and len(self.yaxis_label) == len(self.data_set[0]):
            categories = [str(c) for c in self.yaxis_label]
        else:
            categories = [str(c) for c in self.yaxis_categories]

        payload = {"categories": categories, "series": series}
        if self.stacked:
            payload["stacked"] = True
        markup = _chart_markup(self.graph_image_name, "horizontal_bar", payload,
                               title=self.title, x_name=self.xaxis_name)

        if self.enable_csv:
            if self.yaxis_categories is not None and len(self.yaxis_categories) == len(self.data_set[0]):
                lf_csv_obj = lf_csv()
                lf_csv_obj.columns = [self.yaxis_name] + list(self.label)
                lf_csv_obj.rows = [self.yaxis_categories] + list(self.data_set)
                lf_csv_obj.filename = "{}.csv".format(self.graph_image_name)
                lf_csv_obj.generate_csv()
            else:
                raise ValueError("Length and x-axis values and y-axis values should be same.")

        return markup


class lf_line_graph:
    """Drop-in replacement for lf_graph.py's lf_line_graph: identical
    constructor signature, but build_line_graph() returns interactive
    chart-card markup instead of saving a matplotlib PNG."""

    def __init__(self, _data_set=None,
                 _xaxis_name="x-axis",
                 _yaxis_name="y-axis",
                 _xaxis_categories=None,
                 _xaxis_label=None,
                 _graph_title="",
                 _title_size=16,
                 _graph_image_name="line_graph",
                 _label=None,
                 _font_weight='bold',
                 _color=None,
                 _figsize=(10, 5),
                 _xaxis_step=5,
                 _xticks_font=None,
                 _text_font=None,
                 _legend_handles=None,
                 _legend_loc="best",
                 _legend_box=None,
                 _legend_ncol=1,
                 _legend_fontsize=None,
                 _marker=None,
                 _dpi=96,
                 _grid=True,
                 _enable_csv=False,
                 _reverse_x=False,
                 _reverse_y=False,
                 _dashed=None):
        if _data_set is None:
            _data_set = [[30.4, 55.3, 69.2, 37.1, 44.0], [45.1, 67.2, 34.3, 22.4, 37.6], [22.5, 45.6, 12.7, 34.8, 22.5]]
        if _xaxis_categories is None:
            _xaxis_categories = [1, 2, 3, 4, 5]
        if _xaxis_label is None:
            _xaxis_label = ["a", "b", "c", "d", "e"]
        if _label is None:
            _label = ["bi-downlink", "bi-uplink", 'uplink']
        if _color is None:
            # brand palette (starts #1f6f58, #f1b24a) instead of lf_graph.py's
            # matplotlib defaults, so charts that don't customize colors get
            # the company theme colors -- callers passing their own _color
            # are unaffected.
            _color = list(_ECHARTS_PALETTE)
        if _marker is None:
            _marker = ['s', 'o', 'v']
        self.grid = _grid
        self.data_set = _data_set
        self.xaxis_name = _xaxis_name
        self.yaxis_name = _yaxis_name
        self.xaxis_categories = _xaxis_categories
        self.xaxis_label = _xaxis_label
        self.grp_title = _graph_title
        self.title_size = _title_size
        self.graph_image_name = _graph_image_name
        self.label = _label
        self.color = _color
        self.font_weight = _font_weight
        self.figsize = _figsize
        self.xaxis_step = _xaxis_step
        self.xticks_font = _xticks_font
        self.text_font = _text_font
        self.marker = _marker
        self.enable_csv = _enable_csv
        self.legend_handles = _legend_handles
        self.legend_loc = _legend_loc
        self.legend_box = _legend_box
        self.legend_ncol = _legend_ncol
        self.legend_fontsize = _legend_fontsize
        self.reverse_x = _reverse_x
        self.reverse_y = _reverse_y
        # Per-series flag for a dashed reference/target line (e.g. an intended-load line drawn
        # alongside the achieved-throughput line) instead of the usual solid measured line.
        self.dashed = _dashed or []

    def build_line_graph(self):
        series = [
            {
                "name": self.label[i] if i < len(self.label) else "series-{}".format(i),
                "data": self.data_set[i],
                "color": _css_color(self.color[i % len(self.color)]),
                "dashed": bool(self.dashed[i]) if i < len(self.dashed) else False,
            }
            for i in range(len(self.data_set))
        ]
        payload = {
            "categories": [str(c) for c in self.xaxis_categories],
            "series": series,
            "inverseX": bool(self.reverse_x),
            "inverseY": bool(self.reverse_y),
        }
        markup = _chart_markup(self.graph_image_name, "line", payload,
                               title=self.grp_title, x_name=self.xaxis_name, y_name=self.yaxis_name)

        if self.enable_csv:
            if self.data_set is not None:
                lf_csv_obj = lf_csv()
                lf_csv_obj.columns = list(self.label)
                lf_csv_obj.rows = list(self.data_set)
                lf_csv_obj.filename = "{}.csv".format(self.graph_image_name)
                lf_csv_obj.generate_csv()
            else:
                logger.debug("No Dataset Found")

        return markup


class lf_pie_graph:
    """Interactive pie/donut chart class mirroring the lf_bar_graph/
    lf_bar_graph_horizontal/lf_line_graph classes above: build_pie_graph()
    returns interactive chart-card markup (for use with
    lf_report.set_graph_image()/build_graph()) instead of saving a
    matplotlib PNG -- lf_graph.py has no pie-chart class to mirror, so this
    follows the same _data_set/_label/_graph_image_name conventions as its
    siblings. Thin wrapper around the generic create_pie_chart() function
    below, which does the actual data-sanitizing/markup-building work and
    remains the right choice for callers that already have {"name",
    "value"} dicts."""

    def __init__(self, _data_set=None,
                 _label=None,
                 _graph_title="",
                 _graph_image_name="pie_chart",
                 _subtitle="",
                 _legend=True,
                 _show_percentage=True,
                 _show_labels=True,
                 _center_label=None,
                 _tooltip_formatter=None,
                 _label_formatter=None,
                 _colors=None,
                 _item_details=None,
                 _radius=None,
                 _center=None,
                 _figsize=None,
                 _empty_message="No data available",
                 _enable_csv=False):
        if _data_set is None:
            _data_set = [30.4, 55.3, 69.2, 37.1]
        if _label is None:
            _label = ["a", "b", "c", "d"]
        self.data_set = _data_set
        self.label = _label
        self.title = _graph_title
        self.graph_image_name = _graph_image_name
        self.subtitle = _subtitle
        self.legend = _legend
        self.show_percentage = _show_percentage
        self.show_labels = _show_labels
        self.center_label = _center_label
        self.tooltip_formatter = _tooltip_formatter
        self.label_formatter = _label_formatter
        self.colors = _colors
        self.item_details = _item_details
        self.radius = _radius
        self.center = _center
        # accepted for signature parity with the other graph classes'
        # _figsize (matplotlib inches); interactive charts size via CSS, so
        # only pull an explicit width/height out of it when provided.
        self.width, self.height = _figsize if _figsize else (None, None)
        self.empty_message = _empty_message
        self.enable_csv = _enable_csv

    def build_pie_graph(self):
        data = [
            {"name": self.label[i] if i < len(self.label) else "series-{}".format(i), "value": v}
            for i, v in enumerate(self.data_set)
        ]
        markup = create_pie_chart(
            data=data,
            title=self.title,
            subtitle=self.subtitle,
            chart_id=self.graph_image_name,
            legend=self.legend,
            show_percentage=self.show_percentage,
            show_labels=self.show_labels,
            center_label=self.center_label,
            tooltip_formatter=self.tooltip_formatter,
            label_formatter=self.label_formatter,
            colors=self.colors,
            item_details=self.item_details,
            radius=self.radius,
            center=self.center,
            width=self.width,
            height=self.height,
            empty_message=self.empty_message,
        )

        if self.enable_csv:
            lf_csv_obj = lf_csv()
            lf_csv_obj.columns = list(self.label)
            lf_csv_obj.rows = [self.data_set]
            lf_csv_obj.filename = "{}.csv".format(self.graph_image_name)
            lf_csv_obj.generate_csv()

        return markup


# Unit Test
if __name__ == "__main__":
    help_summary = '''\
     This script is designed to generate reports in file formats such as PDF and HTML, accommodating various user
     preferences. The reports can encompass a range of elements, including graphs, tables, and customizable objectives,
     tailored to meet specific user requirements. This is the modern-report-styled drop-in replacement for lf_report.py.
    '''
    parser = argparse.ArgumentParser(
        prog="lf_modern_report.py",
        formatter_class=argparse.RawTextHelpFormatter,
        description="Modern reporting library Unit Test")
    parser.add_argument('--lfmgr', help='sample argument: where LANforge GUI is running', default='localhost')
    parser.add_argument('--help_summary', help='Show summary of what this script does', default=None,
                        action="store_true")
    args = parser.parse_args()

    if args.help_summary:
        print(help_summary)
        exit(0)

    logger.info("LANforge manager {lfmgr}".format(lfmgr=args.lfmgr))

    dataframe = pd.DataFrame({
        'product': ['CT521a-264-1ac-1n', 'CT521a-1ac-1ax', 'CT522-264-1ac2-1n', 'CT523c-2ac2-db-10g-cu',
                    'CT523c-3ac2-db-10g-cu', 'CT523c-8ax-ac10g-cu', 'CT523c-192-2ac2-1ac-10g'],
        'radios': [1, 1, 2, 2, 6, 9, 3],
        'MIMO': ['N', 'N', 'N', 'Y', 'Y', 'Y', 'Y'],
        'stations': [200, 64, 200, 128, 384, 72, 192],
        'mbps': [300, 300, 300, 10000, 10000, 10000, 10000]
    })

    logger.info(dataframe)

    dataframe2 = pd.DataFrame({
        'station': [1, 2, 3, 4, 5, 6, 7],
        'time_seconds': [23, 78, 22, 19, 45, 22, 25]
    })

    report = lf_report()
    report.set_title("Banner Title One")
    report.build_banner()

    report.set_table_title("Title One")
    report.build_table_title()

    report.set_table_dataframe(dataframe)
    report.build_table()

    report.set_table_title("Title Two")
    report.build_table_title()

    report.set_table_dataframe(dataframe2)
    report.build_table()

    report.build_chart_title('default width')
    report.build_chart("banner.png")

    report.build_chart_title('custom width')
    report.build_chart_custom(name="banner.png", width="1000")

    report.build_echarts_chart(
        chart_id="demo-line-chart",
        chart_type="line",
        payload={
            "categories": ["1", "2", "3", "4", "5"],
            "series": [{"name": "Download", "data": [10, 22, 18, 30, 25]}],
        },
        title="Demo Interactive Chart",
        y_name="Throughput (Mbps)",
        x_name="Sample",
    )

    # create_pie_chart() demo: the same generic function reused for two
    # unrelated report sections, with no hard-coded category names and no
    # chart_id collision (auto-assigned when omitted).
    report.build_pie_chart(
        data=[
            {"name": "Online", "value": 70},
            {"name": "Offline", "value": 30},
        ],
        title="Device Connectivity",
    )
    report.build_pie_chart(
        data=[
            {"name": "Passed", "value": 85},
            {"name": "Failed", "value": 10},
            {"name": "Warning", "value": 5},
        ],
        title="Test Results",
        subtitle="Across all iterations",
        center_label={"main": "100", "sub": "Total"},
    )
    # Edge case: empty/zero data renders a graceful inline message instead of
    # a broken chart or a crash.
    report.build_pie_chart(data=[], title="No Data Example")

    # lf_pie_graph demo: class-based counterpart to lf_bar_graph/lf_line_graph
    # above (parallel _data_set/_label lists instead of {"name","value"} dicts).
    pie = lf_pie_graph(_data_set=[40, 45, 15],
                       _label=["2.4 GHz", "5 GHz", "6 GHz"],
                       _graph_title="Band Distribution",
                       _graph_image_name="demo-band-distribution")
    report.set_graph_image(pie.build_pie_graph())
    report.build_graph()

    report.build_footer_no_png()

    html_file = report.write_html()
    logger.info("returned file ")
    logger.info(html_file)
    report.write_pdf()

    logger.info("report path {}".format(report.get_path()))
