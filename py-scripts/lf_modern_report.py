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
import argparse
import ast
import base64
import datetime
import importlib
import json
import logging
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
from contextlib import contextmanager
from pathlib import Path

try:
    from importlib import metadata
except ImportError:  # Python < 3.8 (this repo's CI still runs 3.7)
    import pkg_resources

    class _PackageNotFoundError(Exception):
        pass

    class _Metadata:
        PackageNotFoundError = _PackageNotFoundError

        @staticmethod
        def version(package):
            try:
                return pkg_resources.get_distribution(package).version
            except pkg_resources.DistributionNotFound:
                raise _PackageNotFoundError(package)

    metadata = _Metadata()

if os.name == 'nt':
    import msvcrt
else:
    import fcntl

# The PDF worker does not need the report-building libraries.
_IS_PDF_WORKER = __name__ == '__main__' and '--pdf-worker' in sys.argv[1:]
if not _IS_PDF_WORKER:
    import pandas as pd
    import pdfkit
    from matplotlib import pyplot as plt

if not _IS_PDF_WORKER:
    sys.path.append(os.path.join(os.path.abspath(__file__ + "../../../")))

    logger = logging.getLogger(__name__)
    lf_logger_config = importlib.import_module("py-scripts.lf_logger_config")
    lf_csv = importlib.import_module("py-scripts.lf_csv").lf_csv
    os_name = platform.system()

_PDF_PRINT_CSS = """
/* Shared paged layout. Interactive HTML retains its screen styling. */
@media print {
  html, body { background: white; font-size: 10pt; print-color-adjust: exact; -webkit-print-color-adjust: exact; }
  .report-shell { max-width: none; width: 100%; margin: 0; padding: 0; border: 0; border-radius: 0; box-shadow: none; }
  .table-search-bar, .device-toolbar, .device-footer, .hideFromPrint { display: none !important; }
  .hideFromScreen { display: block; }
  .table-wrap { overflow: visible; border-radius: 0; box-shadow: none; }
  table { width: 100%; }
  thead { display: table-header-group; }
  tfoot { display: table-footer-group; }
  tr, .info-item, .finding { break-inside: avoid; }
  th, td { overflow-wrap: anywhere; padding: 5px 6px !important; }
  table.data-table th { position: static; }
  th.sortable::after { display: none; }
  table.pdf-table-compact th, table.pdf-table-compact td {
    padding: 4px 3px !important; white-space: normal !important;
    overflow-wrap: anywhere;
  }
  table.pdf-table-small, table.pdf-table-small th, table.pdf-table-small td {
    font-size: 9pt !important;
  }
  h1, h2, h3, h4, .info-card-header { break-after: avoid; }
  .chart-card, .info-card, .contentDiv, .contentDiv2 { padding: 6px 0; }
  .chart-card h3 { margin-bottom: 6px; }
  .chart-card p { margin-top: 4px; margin-bottom: 6px; }
  .chart.pdf-compact-chart { height: var(--pdf-chart-height, 95mm) !important; }
  .chart-card:has(.chart), .chart-card:has(img), .device-summary-row { break-inside: avoid; }
  .chart-card img { max-width: 100%; max-height: 165mm; object-fit: contain; }
  #BannerBack { padding: 16px 20px; break-inside: avoid; }
  .FooterStyle { margin: 10px 0; padding: 8px; break-inside: avoid; }
  html body, .report-shell p, .report-shell li { font-size: 8pt !important; }
  .report-shell p { font-size: 11pt !important; }
  .report-shell .info-card > ul > li { font-size: 11pt !important; }
  .report-shell .info-item-label { margin-bottom: 6px; }
  .report-shell .info-grid {
    display: flex !important;
    flex-wrap: wrap;
    gap: 14px;
    align-items: stretch;
  }
  .report-shell .info-item {
    flex: 0 1 auto;
    width: auto;
    min-width: 36mm;
    max-width: 100%;
    padding: 12px 18px !important;
    box-sizing: border-box;
  }
  .report-shell h1 { font-size: 22pt !important; }
  .report-shell h2 { font-size: 16pt !important; }
  .report-shell h3, .report-shell .info-card-header { font-size: 14pt !important; }
  .report-shell h4 { font-size: 10pt !important; }
  .report-shell .info-label, .report-shell .stat-label { font-size: 7pt !important; }
  .report-shell .info-value { font-size: 8pt !important; }
  .report-shell table, .report-shell table th, .report-shell table td { font-size: 8pt !important; }
  .report-shell table td.network-identifier {
    white-space: nowrap !important;
    overflow-wrap: normal !important;
    word-break: normal !important;
  }
  .report-shell table th {
    white-space: normal !important;
    overflow-wrap: normal !important;
    word-break: normal !important;
    hyphens: none !important;
  }
}
"""

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
    """Returns a new unique chart id like '<prefix>-3', so charts on one page never clash.

    Args:
        prefix (str): text to put before the counter, e.g. "pie-chart".

    Returns:
        str: a new id such as "pie-chart-3".
    """
    global _chart_id_counter
    _chart_id_counter += 1
    return "{}-{}".format(prefix, _chart_id_counter)


_ECHARTS_RUNTIME_JS = """
<script>
(function () {
  if (typeof window.echarts === "undefined") { return; }
  var PALETTE = %(palette)s;

  function initChart(el) {
    var dpr = Math.max(2, window.devicePixelRatio || 1);
    return window.echarts.init(el, null, { devicePixelRatio: dpr, renderer: window.__lfReportPdf ? "svg" : "canvas" });
  }

  function baseOption(yName, xName) {
    return {
      textStyle: { fontFamily: '"Segoe UI", Roboto, Arial, Helvetica, sans-serif' },
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

  // A dataZoom slider only earns its keep when there are enough categories that
  // some of them would otherwise be crowded off-screen; on a handful of bars/points
  // it just adds a dead scrollbar under an already-empty-looking chart.
  var DATA_ZOOM_MIN_CATEGORIES = 10;

  function dropDataZoomIfFewCategories(option, categories) {
    if (!categories || categories.length < DATA_ZOOM_MIN_CATEGORIES) {
      option.dataZoom = [];
    }
  }

  // A fixed bar width only earns its keep once there are enough categories that
  // an unbounded width would make bars comically fat; with a handful of bars
  // (e.g. one per QoS class) it just leaves the chart looking mostly empty, so
  // let bars grow wider the fewer categories there are.
  function barMaxWidthFor(categories) {
    return (categories || []).length <= 6 ? 90 : 34;
  }

  window.__lfModernReport.renderLineChart = function (id, payload, yName, xName) {
    var el = document.getElementById(id);
    if (!el || !payload || !payload.series) { renderFallback(id); return; }
    var chart = initChart(el);
    var option = baseOption(yName, xName);
    if (payload.categories) { option.xAxis.data = payload.categories; option.xAxis.type = "category"; }
    if (payload.xAxisType === "value") { option.xAxis.type = "value"; }
    if (payload.clockOffsetSeconds !== undefined) {
      var clockLabel = function (value) {
        var seconds = ((Math.round(Number(value) + payload.clockOffsetSeconds) %% 86400) + 86400) %% 86400;
        return [Math.floor(seconds / 3600), Math.floor(seconds / 60) %% 60, seconds %% 60]
          .map(function (part) { return String(part).padStart(2, "0"); }).join(":");
      };
      option.xAxis.axisLabel.formatter = clockLabel;
      option.xAxis.axisLabel.rotate = 45;
      option.xAxis.nameGap = 60;
      option.grid.bottom = 110;
      option.xAxis.axisPointer = { label: { formatter: function (p) { return clockLabel(p.value); } } };
      option.tooltip.formatter = function (params) {
        return clockLabel(params[0].value[0]) + "<br/>" + params.map(function (p) {
          return p.marker + p.seriesName + ": " + p.value[1];
        }).join("<br/>");
      };
    }
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
    var chart = initChart(el);
    var option = baseOption(yName, xName);
    option.tooltip.axisPointer = { type: "shadow" };
    option.xAxis.data = payload.categories || [];
    dropDataZoomIfFewCategories(option, payload.categories);
    var barMaxWidth = barMaxWidthFor(payload.categories);
    // A single series whose bars are each colored individually (one bar per
    // category, e.g. per-traffic-class throughput) has nothing meaningful to
    // show in the default series-name legend -- split it into one series per
    // category instead, so the legend lists the category names/colors and
    // can toggle each bar independently. barGap "-100%%" keeps every bar at
    // full width since only one series ever has a real value at each index.
    var perCategoryColor = payload.categories && payload.series.length === 1 &&
      payload.series[0].data.every(function (d) { return d && typeof d === "object" && d.itemStyle && d.itemStyle.color; });
    if (perCategoryColor) {
      option.legend.data = payload.categories;
      option.series = payload.categories.map(function (cat, i) {
        var point = payload.series[0].data[i];
        var row = payload.categories.map(function () { return null; });
        row[i] = point.value;
        return {
          name: cat, type: "bar", data: row, barMaxWidth: barMaxWidth,
          barGap: "-100%%", barCategoryGap: "20%%",
          itemStyle: { color: point.itemStyle.color }
        };
      });
    } else {
      option.series = payload.series.map(function (s) {
        var c = s.color || namedColor(s.name);
        return {
          name: s.name, type: "bar", data: s.data, barMaxWidth: barMaxWidth,
          stack: payload.stacked ? "total" : undefined,
          itemStyle: c ? { color: c } : undefined
        };
      });
    }
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

  window.__lfModernReport.renderHorizontalBarChart = function (id, payload, xName, yName) {
    var el = document.getElementById(id);
    if (!el || !payload || !payload.series) { renderFallback(id); return; }
    el.style.height = Math.max(300, (payload.categories || []).length * 52 + 120) + "px";
    var chart = initChart(el);
    var option = baseOption(yName, xName);
    option.grid = { left: 70, right: 28, top: 48, bottom: 84, containLabel: true };
    option.xAxis = {
      type: "value", name: xName || "", min: 0,
      nameLocation: "middle", nameGap: 30,
      nameTextStyle: { color: "#2c3e50", fontWeight: 600, fontSize: 13 },
      axisLabel: { color: "#5f6f82" }
    };
    option.yAxis = {
      type: "category", data: payload.categories || [],
      name: payload.yAxisName || yName || "", nameLocation: "middle", nameGap: 115, nameRotate: 90,
      nameTextStyle: { color: "#2c3e50", fontWeight: 600, fontSize: 13 },
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
    var chart = initChart(el);

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
      legend: { bottom: 0, data: [payload.connectedLabel || "Up", "Drop"], textStyle: { color: "#5f6f82" } },
      grid: { left: 165, right: 30, top: 25, bottom: 72, containLabel: false },
      xAxis: {
        type: "value",
        min: 0,
        max: payload.duration,
        name: payload.xAxisName || "Time (seconds)",
        nameLocation: "middle",
        nameGap: 36,
        axisLabel: { color: "#5f6f82" },
        splitLine: { lineStyle: { color: "#ecf1f6" } }
      },
      yAxis: {
        type: "category",
        inverse: true,
        data: clients,
        name: payload.yAxisName || "", nameLocation: "middle", nameGap: 150,
        axisLabel: { color: "#2c3e50", fontWeight: 600, width: 145, overflow: "truncate" },
        axisTick: { show: false },
        axisLine: { show: false }
      },
      series: [
        seriesFor("up", payload.connectedLabel || "Up", "#2e8b57"),
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
    var chart = initChart(el);
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

  // rows: [{cellsHtml: "<td>...</td><td>...</td>"}]
  window.__lfModernReport.initSearchTable = function (rootId, rows, pageSize) {
    var root = document.getElementById(rootId);
    if (!root) { return; }
    var tbody = root.querySelector(".device-table tbody");
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

# Adds one sticky search box, near the top of the page, that filters every plain report table
# (class "data-table") at once: a row is hidden unless it contains the typed text, in any of its
# own table's columns. Injected once at the end of the page, same convention as
# _SORTABLE_TABLE_JS, so no build_table() call site has to opt in individually.
_TABLE_SEARCH_JS = """
<script>
(function () {
  var tables = Array.prototype.slice.call(document.querySelectorAll("table.data-table"))
    .filter(function (table) { return table.tBodies.length > 0; });
  if (!tables.length) { return; }

  var searchBar = document.createElement("div");
  searchBar.className = "table-search-bar";
  var input = document.createElement("input");
  input.type = "text";
  input.className = "table-search-input";
  input.placeholder = "Search for a device, value, or anything else across every table below\\u2026";
  var count = document.createElement("span");
  count.className = "table-search-count";
  searchBar.appendChild(input);
  searchBar.appendChild(count);

  // Placed right below the Key Findings card when the report has one (found by header text,
  // since build_findings_card() doesn't assign it a stable id); else right below the Overall
  // Test Verdict card for reports that skip Key Findings; otherwise right above the first real
  // table, so it still lands after the Test Configuration/Objective sections.
  var anchorCard = null;
  Array.prototype.forEach.call(document.querySelectorAll(".info-card"), function (card) {
    var header = card.querySelector(".info-card-header");
    var text = header && header.textContent.trim();
    if (text === "Key Findings") { anchorCard = card; }
    else if (text === "Overall Test Verdict" && !anchorCard) { anchorCard = card; }
  });
  if (anchorCard) {
    anchorCard.parentNode.insertBefore(searchBar, anchorCard.nextSibling);
  } else {
    var firstWrap = tables[0].closest(".table-wrap") || tables[0].parentNode;
    firstWrap.parentNode.insertBefore(searchBar, firstWrap);
  }

  function applyFilter() {
    var query = input.value.trim().toLowerCase();
    var shown = 0, total = 0;
    tables.forEach(function (table) {
      Array.prototype.forEach.call(table.tBodies[0].rows, function (row) {
        total++;
        var match = !query || row.textContent.toLowerCase().indexOf(query) !== -1;
        row.style.display = match ? "" : "none";
        if (match) { shown++; }
      });
    });
    count.textContent = query ? (shown + " / " + total + " rows across " + tables.length + " tables") : "";
  }
  input.addEventListener("input", applyFilter);
})();
</script>
"""


@contextmanager
def installation_lock(path, timeout=900):
    """Prevent concurrent PDF dependency installations."""
    with open(path, 'a+b') as handle:
        handle.seek(0)
        if not handle.read(1):
            handle.write(b'0')
            handle.flush()
        deadline = time.monotonic() + timeout
        while True:
            try:
                handle.seek(0)
                if os.name == 'nt':
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except (OSError):
                if time.monotonic() >= deadline:
                    raise RuntimeError('Timed out waiting for PDF dependency installation lock')
                time.sleep(0.25)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == 'nt':
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)


def run_install(arguments):
    """Run a PDF dependency installer through the current Python interpreter."""
    print('Setting up PDF dependencies: ' + ' '.join(arguments), file=sys.stderr, flush=True)
    try:
        result = subprocess.run([sys.executable, '-m', *arguments], capture_output=True,
                                text=True, timeout=600)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError('PDF dependency installation timed out; check network access') from exc
    if result.returncode:
        raise RuntimeError('PDF dependency installation failed. Check network access and environment '
                           'permissions; HTML and CSV files are preserved.\n' +
                           (result.stdout + result.stderr)[-5000:])


def ensure_dependencies():
    # Read the installer's literal package list without importing its CLI/dependencies.
    tree = ast.parse(Path(__file__).with_name('update_dependencies.py').read_text())
    packages = next(ast.literal_eval(node.value) for node in tree.body
                    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
                    and node.target.id == 'pip_packages')
    requirement = next(package for package in packages if package.startswith('playwright=='))
    configured = os.environ.get('PLAYWRIGHT_BROWSERS_PATH')
    if configured == '0':
        raise RuntimeError('Use a persistent directory for PLAYWRIGHT_BROWSERS_PATH, not 0')
    browser_dir = Path(configured).expanduser().resolve() if configured else (
        Path.home() / '.cache' / 'lanforge' / 'report-browsers')
    os.environ['PLAYWRIGHT_BROWSERS_PATH'] = str(browser_dir)
    browser_dir.mkdir(parents=True, exist_ok=True)
    auto_install = os.environ.get('LF_REPORT_PDF_AUTO_INSTALL', '1') != '0'
    with installation_lock(browser_dir / '.install.lock'):
        package, expected = requirement.split('==')
        try:
            installed = metadata.version(package)
        except metadata.PackageNotFoundError:
            installed = None
        if installed != expected:
            if not auto_install:
                raise RuntimeError(f'PDF requires {requirement}; automatic installation is disabled')
            run_install(['pip', 'install', '--disable-pip-version-check', requirement])
        sync_playwright = importlib.import_module('playwright.sync_api').sync_playwright
        with sync_playwright() as playwright:
            override = os.environ.get('LF_REPORT_CHROMIUM_EXECUTABLE')
            executable = Path(override).expanduser().resolve() if override else Path(playwright.chromium.executable_path)
        if not executable.is_file():
            if override:
                raise RuntimeError(f'Configured Chromium executable does not exist: {executable}')
            if not auto_install:
                raise RuntimeError(f'Chromium missing at {executable}; automatic installation is disabled')
            run_install(['playwright', 'install', 'chromium'])
        if not executable.is_file():
            raise RuntimeError(f'Browser installation did not produce {executable}')
    return str(executable)


def export_pdf(source, destination, page_size='A4', orientation='Portrait', page_width=None, page_height=None):
    """Render a saved HTML report with headless Chromium."""
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    if orientation.lower() not in ('portrait', 'landscape'):
        raise ValueError('PDF orientation must be Portrait or Landscape')
    if (page_width is None) != (page_height is None):
        raise ValueError('Custom PDF size requires both page width and height')
    custom_mm = None
    if page_width is not None:
        dimensions = (page_width, page_height)
        if any(not isinstance(value, str) or not re.fullmatch(r'[0-9]+(?:\.[0-9]+)?mm', value)
               for value in dimensions):
            raise ValueError('Custom PDF dimensions must be positive values in mm')
        custom_mm = tuple(float(value[:-2]) for value in dimensions)
        if min(custom_mm) <= 0:
            raise ValueError('Custom PDF dimensions must be positive values in mm')
    executable = ensure_dependencies()
    sync_playwright = importlib.import_module('playwright.sync_api').sync_playwright
    descriptor, temporary = tempfile.mkstemp(suffix='.pdf', dir=destination.parent)
    os.close(descriptor)
    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(executable_path=executable)
            except Exception as exc:
                raise RuntimeError(
                    "Chromium is installed but could not launch. System libraries, browser permissions, "
                    "or sandbox restrictions may need administrator setup. On supported Linux systems, "
                    "ask the administrator to run this Python environment's `python -m playwright "
                    "install-deps chromium`. No sudo or system-package installation was attempted.\n"
                    + str(exc)) from exc
            try:
                page = browser.new_page(viewport={'width': 1100 if orientation.lower() == 'landscape' else 760, 'height': 900})
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.add_init_script('window.__lfReportPdf = true;')
                page.emulate_media(media='print')
                page.goto(source.as_uri(), wait_until='load', timeout=60000)
                # Inject current print rules for saved reports as well as newly generated ones.
                page.add_style_tag(content=_PDF_PRINT_CSS)
                paper_mm = {'A4': (210, 297), 'A3': (297, 420), 'Letter': (215.9, 279.4),
                            'Legal': (215.9, 355.6)}.get(page_size)
                if custom_mm:
                    paper_mm = custom_mm if orientation.lower() == 'portrait' else custom_mm[::-1]
                if paper_mm:
                    width = (paper_mm[0] if custom_mm else
                             paper_mm[1 if orientation.lower() == 'landscape' else 0]) - 20
                    page.add_style_tag(content='@media print { .report-shell { width: ' + str(width) + 'mm; } }')
                compact_height = '80mm' if orientation.lower() == 'landscape' else '95mm'
                page.add_style_tag(content='@media print { :root { --pdf-chart-height: ' + compact_height + '; } }')
                page.evaluate('''async () => {
                    await document.fonts.ready;
                    await Promise.all(Array.from(document.images).map(image => {
                        if (image.complete) {
                            if (!image.naturalWidth) throw new Error('Missing image: ' + image.src.slice(0, 160));
                            return;
                        }
                        return new Promise((resolve, reject) => {
                            image.onload = resolve;
                            image.onerror = () => reject(new Error('Image failed: ' + image.src.slice(0, 160)));
                        });
                    }));
                    document.querySelectorAll('.view-all-btn').forEach(button => button.click());
                    document.querySelectorAll('.table-search-input').forEach(input => {
                        input.value = ''; input.dispatchEvent(new Event('input'));
                    });
                    // Use rendered width, not column count, to decide whether to split.
                    for (const table of document.querySelectorAll('table.data-table, table.device-table')) {
                        const shell = table.closest('.report-shell');
                        const container = table.parentElement;
                        const available = Math.min(container.clientWidth,
                            shell ? shell.clientWidth : document.documentElement.clientWidth);
                        const fits = candidate => candidate.getBoundingClientRect().width <= available + 1 &&
                            candidate.scrollWidth <= available + 1;
                        if (fits(table)) continue;
                        table.classList.add('pdf-table-compact');
                        if (fits(table)) continue;
                        table.classList.add('pdf-table-small');
                        if (fits(table)) continue;
                        const rows = Array.from(table.rows);
                        const count = rows.length ? rows[0].cells.length : 0;
                        if (count < 2 || table.querySelector('colgroup') || rows.some(row => row.cells.length !== count ||
                            Array.from(row.cells).some(cell => cell.colSpan !== 1 || cell.rowSpan !== 1))) {
                            throw new Error('Custom table still exceeds printable width; use a larger page or adjust its layout');
                        }
                        const headers = Array.from(rows[0].cells).map(cell => cell.textContent.trim());
                        const identifier = headers.findIndex(label => /^(device name|wireless client|client|station|hostname)$/i.test(label));
                        const key = identifier >= 0 ? identifier : 0;
                        const columns = Array.from({length: count}, (_, index) => index).filter(index => index !== key);
                        const makePanel = selected => {
                            const copy = table.cloneNode(true);
                            copy.removeAttribute('id');
                            copy.style.width = '100%';
                            copy.style.minWidth = '0';
                            copy.style.tableLayout = 'auto';
                            for (const row of copy.rows) {
                                Array.from(row.cells).forEach((cell, index) => {
                                    if (index !== key && !selected.includes(index)) cell.remove();
                                });
                            }
                            container.insertBefore(copy, table);
                            return copy;
                        };
                        let start = 0;
                        while (start < columns.length) {
                            let end = start + 1;
                            let panel = makePanel(columns.slice(start, end));
                            if (!fits(panel)) {
                                panel.remove();
                                throw new Error('Table identifier and one column exceed printable width; use a larger page');
                            }
                            while (end < columns.length) {
                                const trial = makePanel(columns.slice(start, end + 1));
                                if (!fits(trial)) { trial.remove(); break; }
                                panel.remove();
                                panel = trial;
                                end++;
                            }
                            if (start > 0) {
                                const caption = panel.createCaption();
                                caption.textContent += ' Continued — additional columns';
                            }
                            start = end;
                        }
                        table.remove();
                    }
                    const charts = Array.from(document.querySelectorAll('.chart, .device-donut'));
                    for (const element of charts) {
                        const chart = window.echarts && echarts.getInstanceByDom(element);
                        if (!chart) {
                            if (!element.querySelector('.chart-fallback')) throw new Error('Chart not rendered: ' + element.id);
                            continue;
                        }
                        const option = chart.getOption();
                        option.animation = false;
                        option.dataZoom = [];
                        // Time-series charts do not need the screen's 420px height or slider space.
                        // Keep category charts tall enough to display all client labels.
                        const hasClientAxis = option.yAxis && option.yAxis.some(axis => axis.type === 'category');
                        if (element.classList.contains('chart') && !hasClientAxis &&
                            option.series.every(series => series.type === 'line' || series.type === 'bar')) {
                            element.classList.add('pdf-compact-chart');
                            if (option.grid) option.grid.forEach(grid => {
                                grid.top = Math.min(Number(grid.top) || 48, 28);
                                // Leave extra room for rotated clock labels where explicitly requested.
                                grid.bottom = Math.min(Number(grid.bottom) || 84, 90);
                            });
                        }
                        if (option.legend) option.legend.forEach(legend => { legend.selected = {}; });
                        if (option.yAxis) option.yAxis.forEach(axis => {
                            if (axis.type === 'category') axis.axisLabel = Object.assign({}, axis.axisLabel,
                                {formatter: null, overflow: 'break', width: 190});
                        });
                        // Split category charts into readable page-sized panels.
                        const categoryAxis = option.yAxis && option.yAxis.find(axis => axis.type === 'category');
                        const categories = categoryAxis && categoryAxis.data;
                        const panelSize = 8;
                        if (categories && categories.length > panelSize) {
                            const card = element.closest('.chart-card');
                            if (!card) throw new Error('Oversized chart has no card: ' + element.id);
                            for (let start = 0; start < categories.length; start += panelSize) {
                                const panel = card.cloneNode(true);
                                panel.querySelectorAll('script').forEach(script => script.remove());
                                const target = panel.querySelector('.chart');
                                target.innerHTML = '';
                                target.removeAttribute('_echarts_instance_');
                                target.id = element.id + '-pdf-' + start;
                                target.style.height = '410px';
                                const heading = panel.querySelector('h3');
                                if (heading && start) heading.textContent += ' (continued)';
                                card.parentNode.insertBefore(panel, card);
                                const panelOption = Object.assign({}, option);
                                panelOption.yAxis = option.yAxis.map(axis => axis === categoryAxis
                                    ? Object.assign({}, axis, {data: categories.slice(start, start + panelSize)}) : axis);
                                panelOption.series = option.series.map(series => Object.assign({}, series, {
                                    data: series.type === 'custom'
                                        ? series.data.filter(point => point[0] >= start && point[0] < start + panelSize)
                                            .map(point => [point[0] - start, ...point.slice(1)])
                                        : series.data.slice(start, start + panelSize)
                                }));
                                echarts.init(target, null, {renderer: 'svg'}).setOption(panelOption);
                            }
                            chart.dispose();
                            card.remove();
                        } else {
                            chart.setOption(option, true);
                            chart.resize();
                        }
                    }
                    await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
                }''')
                if errors:
                    raise RuntimeError('Report JavaScript errors: ' + '; '.join(errors))
                # Flow content avoids empty header/footer bands on intermediate pages.
                pdf_options = dict(format=page_size, landscape=orientation.lower() == 'landscape',
                                   print_background=True,
                                   margin={'top': '10mm', 'bottom': '10mm', 'left': '10mm', 'right': '10mm'},
                                   display_header_footer=False)
                if custom_mm:
                    pdf_options.pop('format')
                    pdf_options.update(width=f'{paper_mm[0]}mm', height=f'{paper_mm[1]}mm', landscape=False)
                Path(temporary).write_bytes(page.pdf(**pdf_options))
            finally:
                browser.close()
        if Path(temporary).stat().st_size < 100 or Path(temporary).read_bytes()[:5] != b'%PDF-':
            raise RuntimeError('PDF export produced an invalid file')
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _run_pdf_worker():
    """Parse the isolated PDF worker command line and export the report."""
    parser = argparse.ArgumentParser(description='Export saved report HTML to PDF')
    parser.add_argument('--pdf-worker', action='store_true')
    parser.add_argument('source')
    parser.add_argument('destination')
    parser.add_argument('--page-size', default='A4')
    parser.add_argument('--orientation', default='Portrait')
    parser.add_argument('--page-width')
    parser.add_argument('--page-height')
    args = parser.parse_args()
    export_pdf(args.source, args.destination, args.page_size, args.orientation, args.page_width, args.page_height)


class lf_report:
    """Builds a LANforge HTML/PDF test report piece by piece (banner, text, tables, charts, footer).
    Same API as the old lf_report.py; only the look is modernized."""
    # Score band -> (label, color): Excellent 90-100, Good 80-89, Average 70-79, Poor <70.
    SCORE_RATING_BANDS = [(90, "Excellent", "#1e7e34"), (80, "Good", "#28a745"),
                          (70, "Average", "#f1c40f"), (0, "Poor", "#e74c3c")]

    @classmethod
    def classify_score_rating(cls, score):
        """Maps a numeric score to a rating label and color (Excellent/Good/Average/Poor).

        Args:
            score (float): score to classify, 0-100.

        Returns:
            tuple: (label (str), color (str)) for the band the score falls in.
        """
        for threshold, label, color in cls.SCORE_RATING_BANDS:
            if score >= threshold:
                return label, color
        return cls.SCORE_RATING_BANDS[-1][1], cls.SCORE_RATING_BANDS[-1][2]

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
                 _custom_css='custom-example.css'):  # this is where the final report is placed.
        """Sets up the report and creates its '<date>_<results_dir_name>' folder under _path.
        Also copies the CSS, logos, font and chart script into that folder.

        Args:
            _path (str): base folder the report folder is created under ("local"/"here" uses
                this script's own folder instead).
            _alt_path (str): if set, used as the base folder instead of _path.
            _date (str): report date; current date/time is used when empty.
            _title (str): report title shown in the banner.
            _table_title (str): heading used by the first build_table_title() call.
            _graph_title (str): heading used by the first build_graph_title() call.
            _obj (str): objective text used by build_objective().
            _obj_title (str): objective heading used by build_objective().
            _output_html (str): HTML file name written by write_html().
            _output_pdf (str): PDF file name written by write_pdf().
            _results_dir_name (str): second half of the report folder name.
            _output_format (str): accepted for compatibility; not currently used.
            _dataframe: initial table (pandas DataFrame) for build_table().
            _path_date_time (str): pre-set report folder path; normally left empty and computed.
            _custom_css (str): custom CSS file (from the artifacts folder), copied in as custom.css.

        Returns:
            None
        """
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
        self.logo_file_name = "yellow.png"
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
        """Copies the banner image into the report folder."""
        banner_src_file = str(self.current_path) + '/' + str(self.banner_directory) + '/' + str(self.banner_file_name)
        banner_dst_file = str(self.path_date_time) + '/' + str(self.banner_file_name)
        shutil.copy(banner_src_file, banner_dst_file)

    def move_data(self, directory=None, _file_name=None, directory_name=None):
        """Moves a file (or a whole directory, if directory_name is given) from the script folder
        into the report folder, optionally into a sub-folder.

        Args:
            directory (str): sub-folder inside the report folder to move the file into.
            _file_name (str): name of the file to move (ignored when directory_name is given).
            directory_name (str): name of a whole directory to move instead of a single file.

        Returns:
            None
        """
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
        """Copies the stylesheet (saved as report.css), custom.css and the report font into the report folder."""
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
        """Copies the ECharts library (used by the interactive charts) into the report folder."""
        echarts_src_file = str(self.current_path) + '/' + str(self.banner_directory) + '/' + str(self.echarts_file)
        echarts_dst_file = str(self.path_date_time) + '/' + str(self.echarts_file)
        shutil.copy(echarts_src_file, echarts_dst_file)

    def copy_logo(self):
        """Copies the header logo into the report folder."""
        logo_src_file = str(self.current_path) + '/' + str(self.logo_directory) + '/' + str(self.logo_file_name)
        logo_dst_file = str(self.path_date_time) + '/' + str(self.logo_file_name)
        shutil.copy(logo_src_file, logo_dst_file)

    def copy_logo_footer(self):
        """Copies the small footer logo into the report folder."""
        logo_footer_src_file = str(self.current_path) + '/' + str(self.logo_directory) + '/' + str(
            self.logo_footer_file_name)
        logo_footer_dst_file = str(self.path_date_time) + '/' + str(self.logo_footer_file_name)
        shutil.copy(logo_footer_src_file, logo_footer_dst_file)

    def move_graph_image(self, ):
        """Moves the current graph PNG into the report folder.
        Does nothing for interactive charts, since those are HTML and not a file."""
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
        """Moves the current CSV file (set by set_csv_filename) into the report folder."""
        csv_src_file = str(self.csv_file_name)
        csv_dst_file = str(self.path_date_time) + '/' + str(self.csv_file_name)
        logger.info("csv_src_file: {}".format(csv_src_file))
        logger.info("csv_dst_file: {}".format(csv_dst_file))
        shutil.move(csv_src_file, csv_dst_file)

    def set_date_time_directory(self, _date, _results_dir_name):
        """Decides the report folder name: '<date>_<results_dir_name>'.
        Uses the current date and time when no date is given.

        Args:
            _date (str): date string to use; current date/time is used when empty.
            _results_dir_name (str): second half of the report folder name.

        Returns:
            None
        """
        self.date = _date
        self.results_dir_name = _results_dir_name
        if self.date != "":
            self.date_time_directory = str(self.date) + str("_") + str(self.results_dir_name)
        else:
            self.date = str(datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S")).replace(':', '-')
            self.date_time_directory = self.date + str("_") + str(self.results_dir_name)

    def build_date_time_directory(self):
        """Creates the report folder on disk.
        Falls back to a folder next to this script if the path can't be created."""
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
        """Creates the 'log' sub-folder inside the report folder; exits if that fails."""
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
        """Creates a sub-folder with the given name inside the report folder; exits if that fails.

        Args:
            directory_name (str): name of the sub-folder to create.

        Returns:
            None
        """
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
        """Sets the text used by the next build_text() or build_text_simple() call.

        Args:
            _text (str): text to store.

        Returns:
            None
        """
        self.text = _text

    def set_title(self, _title):
        """Sets the report title shown in the banner.

        Args:
            _title (str): report title.

        Returns:
            None
        """
        self.title = _title

    def set_table_title(self, _table_title):
        """Sets the heading used by the next build_table_title() call.

        Args:
            _table_title (str): table heading.

        Returns:
            None
        """
        self.table_title = _table_title

    def set_graph_title(self, _graph_title):
        """Sets the heading used by the next build_graph_title() call.

        Args:
            _graph_title (str): graph heading.

        Returns:
            None
        """
        self.graph_title = _graph_title

    # sets the csv file name as graph title
    def set_csv_filename(self, _graph_title):
        """Sets the CSV file name to the graph name with a .csv extension.

        Args:
            _graph_title (str): name to base the CSV file name on.

        Returns:
            None
        """
        fname, ext = os.path.splitext(_graph_title)
        self.csv_file_name = fname + ".csv"

    def write_dataframe_to_csv(self, _index=False):
        """Saves the current table (dataframe) as a CSV in the report folder.

        Args:
            _index (bool): whether to include the DataFrame index as a column.

        Returns:
            None
        """
        csv_file = "{path_date_time}/{csv_file_name}".format(path_date_time=self.path_date_time, csv_file_name=self.csv_file_name)
        self.dataframe.to_csv(csv_file, index=_index)

    # The _date is set when class is enstanciated / created so this set_date should be used with caution, used to synchronize results
    def set_date(self, _date):
        """Overrides the report date (normally set once when the report is created).

        Args:
            _date (str): new report date string.

        Returns:
            None
        """
        self.date = _date

    def set_table_dataframe(self, _dataframe):
        """Sets the table (pandas DataFrame) used by the next build_table() call.

        Args:
            _dataframe (DataFrame): table to store.

        Returns:
            None
        """
        self.dataframe = _dataframe

    def set_table_dataframe_from_csv(self, _csv):
        """Loads the table for the next build_table() call from a CSV file.

        Args:
            _csv (str): path to the CSV file.

        Returns:
            None
        """
        self.dataframe = pd.read_csv(_csv)

    def set_table_dataframe_from_csv_sep_tab(self, _csv):
        """Loads the table for the next build_table() call from a tab-separated file.

        Args:
            _csv (str): path to the tab-separated file.

        Returns:
            None
        """
        self.dataframe = pd.read_csv(_csv, sep='\t')

    # TODO
    def set_table_dataframe_from_xlsx(self, _xlsx):
        """Loads the table for the next build_table() call from an Excel file.

        Args:
            _xlsx (str): path to the Excel file.

        Returns:
            None
        """
        self.dataframe = pd.read_excel(_xlsx)

    def set_custom_html(self, _custom_html):
        """Sets raw HTML to add with the next build_custom() call.

        Args:
            _custom_html (str): raw HTML to store.

        Returns:
            None
        """
        self.custom_html = _custom_html

    def set_obj_html(self, _obj_title, _obj):
        """Sets the heading and text for the next build_objective() section.

        Args:
            _obj_title (str): objective heading.
            _obj (str): objective body text.

        Returns:
            None
        """
        self.objective = _obj
        self.obj_title = _obj_title

    def set_desc_html(self, _desc_title, _desc):
        """Sets the heading and text for the next build_description() section.

        Args:
            _desc_title (str): description heading.
            _desc (str): description body text.

        Returns:
            None
        """
        self.description = _desc
        self.desc_title = _desc_title

    def set_graph_image(self, _graph_image):
        """Sets the graph (a PNG path or interactive chart HTML) used by the next build_graph() call.

        Args:
            _graph_image (str): PNG file path, or interactive chart HTML.

        Returns:
            None
        """
        self.graph_image = _graph_image

    def get_date(self):
        """Returns the report date string."""
        return self.date

    def get_path(self):
        """Returns the base folder the report folder is created under."""
        return self.path

    def get_parent_path(self):
        """Returns the parent folder of the base report path."""
        parent_path = os.path.dirname(self.path)
        return parent_path

    # get_path_date_time, get_report_path and need to be the same
    def get_path_date_time(self):
        """Returns the full path of this report's folder."""
        return self.path_date_time

    def get_report_path(self):
        """Returns the full path of this report's folder (same as get_path_date_time)."""
        return self.path_date_time

    def get_flat_dir_report_path(self):
        """Returns the base report path, without the dated sub-folder."""
        return self.path

    def get_log_path(self):
        """Returns the path of the report's 'log' sub-folder."""
        return self.log_directory

    def file_add_path(self, file):
        """Returns the full path of a file name inside the report folder.

        Args:
            file (str): file name.

        Returns:
            str: full path of the file inside the report folder.
        """
        output_file = str(self.path_date_time) + '/' + str(file)
        logger.info("output file {}".format(output_file))
        return output_file

    # Report Location:::/<locaton> as a key in lf_check.py

    def write_report_location(self):
        """Logs 'Report Location:::<folder>' so lf_check.py can find this report."""
        self.report_location = self.path_date_time
        logger.info("Report Location:::{report_location}".format(report_location=self.report_location))

    def write_html(self):
        """Writes the report HTML to the report folder and returns the file path."""
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
        """Writes a copy of the report HTML as readme.html in the report folder."""
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
        """Writes the report HTML with the date added to the file name."""
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

    @staticmethod
    def _write_pdf_file(input_html, output_pdf, options, configuration=None):
        """Export HTML through Chromium or the legacy wkhtmltopdf backend."""
        backend = os.environ.get("LF_REPORT_PDF_BACKEND", "chromium").lower()
        if backend == "chromium":
            worker = os.path.abspath(__file__)
            dimension_args = []
            for key in ("page-width", "page-height"):
                if key in options:
                    dimension_args.extend(["--" + key, options[key]])
            result = subprocess.run(
                [sys.executable, worker, "--pdf-worker", os.path.abspath(input_html), os.path.abspath(output_pdf),
                 "--page-size", options.get("page-size", "A4"),
                 "--orientation", options.get("orientation", "Portrait")] + dimension_args,
                capture_output=True, text=True, timeout=2400)
            if result.returncode:
                raise RuntimeError("Chromium PDF export failed; HTML is preserved. Install "
                                   "the pinned Playwright dependency from update_dependencies.py and its matching Chromium browser. "
                                   "Check PLAYWRIGHT_BROWSERS_PATH / LF_REPORT_CHROMIUM_EXECUTABLE.\n"
                                   + result.stderr[-6000:])
            return
        if backend != "wkhtmltopdf":
            raise ValueError("LF_REPORT_PDF_BACKEND must be chromium or wkhtmltopdf")
        logger.warning("Using legacy wkhtmltopdf: interactive charts and layout may be incomplete")
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

    @staticmethod
    def _pdf_options(page_size, orientation, page_width, page_height):
        """Build options shared by both PDF output methods."""
        if (page_width is None) != (page_height is None):
            raise ValueError('Custom PDF size requires both page width and height')
        options = {'enable-local-file-access': None, 'orientation': orientation}
        if page_width is None:
            options['page-size'] = page_size
        else:
            options.update({'page-width': page_width, 'page-height': page_height})
        return options

    def write_pdf(self, _page_size='A4', _orientation='Portrait', _page_width=None, _page_height=None):
        """Write the report PDF to the report folder."""
        if not self.output_pdf:
            logger.info("write_pdf: no pdf file name, skipping pdf output")
            return
        options = self._pdf_options(_page_size, _orientation, _page_width, _page_height)
        self.write_output_pdf = str(self.path_date_time) + '/' + str(self.output_pdf)
        if os_name == "Windows" and os.environ.get("LF_REPORT_PDF_BACKEND", "chromium").lower() == "wkhtmltopdf":
            path_to_wkhtmltopdf = r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe'
            config = pdfkit.configuration(wkhtmltopdf=path_to_wkhtmltopdf)
            self._write_pdf_file(self.write_output_html, self.write_output_pdf, options, configuration=config)
        else:
            self._write_pdf_file(self.write_output_html, self.write_output_pdf, options)

    def write_pdf_with_timestamp(self, _page_size='A4', _orientation='Portrait', _page_width=None, _page_height=None):
        """Write the report PDF with the date in its file name."""
        if not self.output_pdf:
            logger.info("write_pdf_with_timestamp: no pdf file name, skipping pdf output")
            return
        options = self._pdf_options(_page_size, _orientation, _page_width, _page_height)
        self.write_output_pdf = "{}/{}-{}".format(self.path_date_time, self.date, self.output_pdf)
        self._write_pdf_file(self.write_output_html, self.write_output_pdf, options)

    def get_pdf_path(self):
        """Returns the full path of the dated PDF file."""
        pdf_link_path = "{}/{}-{}".format(self.path_date_time, self.date, self.output_pdf)
        return pdf_link_path

    def get_pdf_file(self):
        """Returns the dated PDF file name, or None if no PDF name was set."""
        if not self.output_pdf:
            logger.info("get_pdf_file: no pdf name, returning None")
            return None
        pdf_file = "{}-{}".format(self.date, self.output_pdf)
        return pdf_file

    def build_pdf_link(self, _pdf_link_name, _pdf_link_path):
        """Adds a link to the PDF version of the report.

        Args:
            _pdf_link_name (str): link text.
            _pdf_link_path (str): link target (PDF file path/URL).

        Returns:
            None
        """
        self.pdf_link_html = """
            <!-- pdf link -->
            <a href="{pdf_link_path}" target="_blank">{pdf_link_name}</a>
            <br>
        """.format(pdf_link_path=_pdf_link_path, pdf_link_name=_pdf_link_name)
        self.html += self.pdf_link_html

    def build_link(self, _link_name, _link_path):
        """Adds a link with the given name and target.

        Args:
            _link_name (str): link text.
            _link_path (str): link target.

        Returns:
            None
        """
        self.link = """
            <!-- link -->
            <a href="{link_path}" target="_blank">{link_name}</a>
            <br>
        """.format(link_path=_link_path, link_name=_link_name)
        self.html += self.link

    def generate_report(self):
        """Writes the HTML report, and the PDF too if a PDF name was set."""
        self.write_html()
        if self.output_pdf:
            self.write_pdf()

    def build_all(self):
        """Builds a simple report: banner, table title and table."""
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
        so a report still builds (just without that one piece) instead of crashing.

        Args:
            filename (str): asset file name, relative to the report folder.

        Returns:
            str: the file's contents, or "" if it's missing.
        """
        try:
            with open(os.path.join(self.path_date_time, filename), "r", encoding="utf-8") as f:
                return f.read()
        except OSError:
            return ""

    def _report_asset_as_data_uri(self, filename):
        """Turns a report asset (an image, a font) into a "data:...;base64,..." string that can go
        straight into an src="..." attribute, so the browser doesn't need to fetch a separate file.

        Args:
            filename (str): asset file name, relative to the report folder.

        Returns:
            str: the data URI, or the plain filename if the file is missing.
        """
        try:
            with open(os.path.join(self.path_date_time, filename), "rb") as f:
                raw_bytes = f.read()
        except OSError:
            return filename
        ext = os.path.splitext(filename)[1].lower()
        mime = self._ASSET_MIME_TYPES.get(ext, "application/octet-stream")
        return "data:{};base64,{}".format(mime, base64.b64encode(raw_bytes).decode("ascii"))

    def get_html_head(self, title='Untitled'):
        """Returns the HTML <head> with the CSS, font and chart script inlined,
        so the single .html file works without its folder.

        Args:
            title (str): page title.

        Returns:
            str: the <head>...</head> markup.
        """
        report_css = self._read_report_asset("report.css")
        font_data_uri = self._report_asset_as_data_uri(self.font_file)
        report_css = report_css.replace('url("{}")'.format(self.font_file), 'url("{}")'.format(font_data_uri))
        custom_css = self._read_report_asset("custom.css")
        custom_css += "\n" + _PDF_PRINT_CSS
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
        """Starts the page and adds the top banner with the title, date and logo on the right."""
        self.banner_html = """<!DOCTYPE html>
<html lang='en'>
    {head_tag}
    <body>
        <div class='report-shell'>
        <div id='BannerBack'>
            <div id='Banner'>
                <div class='HeaderStyle'>
                    <h1 class='TitleFontPrint'>{title}</h1>
                    <h4 class='TitleFontPrintSub'>{date}</h4>
                </div>
                <img id='BannerLogo' align='left' src="{logo_data_uri}" border='0'/>
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
        """Starts the page and adds the top banner with the logo on the left."""
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
        """Same as build_banner_left(), with a smaller title font."""
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
        """Starts the page and adds a full-height cover banner."""
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
        """Adds the table heading set by set_table_title()."""
        self.table_title_html = """
                    <!-- Table Title-->
                    <h3 align='left'>{title}</h3>
                    """.format(title=self.table_title)
        self.html += self.table_title_html

    def start_content_div2(self):
        """Opens a 'contentDiv2' section; close it with end_content_div()."""
        self.html += "\n<div class='contentDiv2'>\n"

    def start_content_div(self):
        """Opens a 'contentDiv' section; close it with end_content_div()."""
        self.html += "\n<div class='contentDiv'>\n"

    def build_text(self):
        """Adds the text set by set_text() as a heading."""
        # please do not use 'style=' tags unless you cannot override a class
        self.text_html = """
        <div class='HeaderStyle'>
            <h3 class='TitleFontPrint'>{text}</h3>\n
        </div>""".format(text=self.text)
        self.html += self.text_html

    def build_text_simple(self):
        """Adds the text set by set_text() as a normal paragraph."""
        self.text_html = """
            <p align='left' width='900'>{text}</p>
        """.format(text=self.text)
        self.html += self.text_html

    def build_date_time(self):
        """Returns the current date and time as a folder-safe string."""
        self.date_time = str(datetime.datetime.now().strftime("%Y-%m-%d-%H-h-%m-m-%S-s")).replace(':', '-')
        return self.date_time

    @staticmethod
    def _keep_identifiers_on_one_line(table_html, dataframe):
        """Mark SSID, BSSID, and MAC cells so print CSS keeps their values intact."""
        identifier_columns = {
            index for index, name in enumerate(dataframe.columns)
            if re.search(r'\b(?:ssid|bssid|mac)\b', str(name), re.IGNORECASE)
        }
        if not identifier_columns:
            return table_html

        def mark_row(match):
            cell_index = -1

            def mark_cell(cell):
                nonlocal cell_index
                cell_index += 1
                if cell_index in identifier_columns:
                    return cell.group(0)[:-1] + ' class="network-identifier">'
                return cell.group(0)

            return re.sub(r'<td\b[^>]*>', mark_cell, match.group(0))

        return re.sub(r'<tr\b[^>]*>.*?</tr>', mark_row, table_html, flags=re.DOTALL)

    def build_table(self):
        """Adds the current table (set by set_table_dataframe) to the report."""
        self.dataframe_html = self.dataframe.to_html(index=False, justify='center', classes='data-table')
        self.dataframe_html = self._keep_identifiers_on_one_line(self.dataframe_html, self.dataframe)
        self.html += "<div class='table-wrap'>" + self.dataframe_html + "</div>"

    def pass_failed_build_table(self):
        """Adds the current table with 'Success'/'Failed' values shown as colored badges."""
        # Render Success/Failed values as modern status badges instead of raw
        # cell background colors. This also sidesteps pandas Styler.hide_index(),
        # which was removed in current pandas and made this method unusable there.
        def _badge(value):
            """Wraps 'Success'/'Failed' in a colored badge; other values are left as they are.

            Args:
                value: the cell value.

            Returns:
                str: badge HTML for 'Success'/'Failed', or value unchanged otherwise.
            """
            if value == "Success":
                return '<span class="status-badge pass">Success</span>'
            if value == "Failed":
                return '<span class="status-badge fail">Failed</span>'
            return value

        badge_df = self.dataframe.applymap(_badge)
        self.dataframe_html = badge_df.to_html(index=False, justify='center', classes='data-table', escape=False)
        self.dataframe_html = self._keep_identifiers_on_one_line(self.dataframe_html, badge_df)
        self.html += "<div class='table-wrap'>" + self.dataframe_html + "</div>"

    def rating_build_table(self, rating_column, rating_colors):
        """Like pass_failed_build_table(), but for any column of rating labels (e.g.
        "Excellent"/"Good"/"Average"/"Poor") instead of a fixed Success/Failed pair.

        Args:
            rating_column (str): name of the column to show as colored badges.
            rating_colors (dict): maps each label to a CSS color; labels missing from it
                stay plain text.

        Returns:
            None
        """
        def _badge(value):
            """Wraps a known rating label in a colored badge; other values are left as they are.

            Args:
                value: the cell value.

            Returns:
                str: badge HTML if value is a known rating label, or value unchanged otherwise.
            """
            color = rating_colors.get(value)
            if not color:
                return value
            return ("<span style='background:{color}; color:#fff; padding:2px 10px; "
                    "border-radius:10px; font-weight:600; white-space:nowrap;'>{value}</span>"
                    ).format(color=color, value=value)

        badge_df = self.dataframe.copy()
        badge_df[rating_column] = badge_df[rating_column].apply(_badge)
        self.dataframe_html = badge_df.to_html(index=False, justify='center', classes='data-table', escape=False)
        self.dataframe_html = self._keep_identifiers_on_one_line(self.dataframe_html, badge_df)
        self.html += "<div class='table-wrap'>" + self.dataframe_html + "</div>"

    def save_csv(self, file_name, save_to_csv_data):
        """Saves a DataFrame as a CSV file in the report folder.

        Args:
            file_name (str): CSV file name.
            save_to_csv_data (DataFrame): table to save.

        Returns:
            None
        """
        save_to_csv_data.to_csv(str(self.path_date_time) + "/" + file_name)

    def save_pie_chart(self, pie_chart_data):
        """Saves a Pass/Fail pie chart as pie-chart.png in the report folder.

        Args:
            pie_chart_data (DataFrame): table with a "Pass/Fail" column to plot.

        Returns:
            None
        """
        pie_chart_data.plot.pie(y='Pass/Fail', autopct="%.2f%%", figsize=(8, 8),
                                shadow=False, startangle=90,
                                colors=['#1d9a8a', '#d95f5f'])
        plt.tight_layout()
        plt.savefig(str(self.path_date_time) + '/pie-chart.png')
        plt.close()

    def save_bar_chart(self, xlabel, ylabel, bar_chart_data, name):
        """Saves a bar chart of the DataFrame as <name>.png in the report folder.

        Args:
            xlabel (str): x-axis label.
            ylabel (str): y-axis label.
            bar_chart_data (DataFrame): table to plot.
            name (str): file name (without extension) to save the chart as.

        Returns:
            None
        """
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
        """Adds a two-column 'setting: value' table, with the given label on the left.

        Args:
            test_setup_data (dict): settings to list as rows, {setting: value}.
            value (str): label shown in the left-hand cell.

        Returns:
            None
        """
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
        """Adds the footer with the Candela logo and closes the page layout."""
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
        self.html += _TABLE_SEARCH_JS

    def build_footer_no_png(self):
        """Adds the footer without the logo image and closes the page layout."""
        self.footer_html = """
    <footer class='FooterStyle'>
        <p>Generate by Candela Technologies LANforge network testing tool</p>
        <p><a href="https://www.candelatech.com">www.candelatech.com</a><p>
    </footer>
    </div><!-- end report-shell -->"""
        self.html += self.footer_html
        self.html += _SORTABLE_TABLE_JS
        self.html += _TABLE_SEARCH_JS

    def copy_js(self):
        """Adds the JavaScript that lets the page copy text to the clipboard."""
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
        """Adds the raw HTML set by set_custom_html()."""
        self.html += self.custom_html

    def build_objective(self):
        """Adds a heading and paragraph section, using the text from set_obj_html()."""
        self.obj_html = """
            <!-- Test Objective -->
            <div class='chart-card' style='text-align:left;'>
              <h3 align='left'>{title}</h3>
              <p align='left' width='900'>{objective}</p>
            </div>
            """.format(title=self.obj_title,
                       objective=self.objective)
        self.html += self.obj_html

    def build_description(self):
        """Adds a heading and paragraph, using the text from set_desc_html()."""
        self.obj_html = """
            <!-- Test Description -->
            <h3 align='left'>{title}</h3>
            <p align='left' width='900'>{description}</p>
            """.format(title=self.desc_title,
                       description=self.description)
        self.html += self.obj_html

    def build_graph_title(self):
        """Adds the graph heading set by set_graph_title()."""
        self.table_graph_html = """
            <div class='HeaderStyle'>
                <h2 class='TitleFontPrint'>{title}</h2>
            """.format(title=self.graph_title)
        self.html += self.table_graph_html

    def build_graph(self):
        """Adds the graph set by set_graph_image(): a PNG inside a chart card,
        or an interactive chart as it is."""
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
        """Same as build_graph(), but a PNG is left-aligned."""
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
        """Closes a section opened with start_content_div() or start_content_div2()."""
        self.html += "\n</div><!-- end contentDiv -->\n"

    def build_chart_title(self, chart_title):
        """Adds a chart heading.

        Args:
            chart_title (str): heading text.

        Returns:
            None
        """
        self.chart_title_html = """
            <div class='HeaderStyle'>
                <h3 class='TitleFontPrint'>{title}</h3>
            """.format(title=chart_title)
        self.html += self.chart_title_html

    def build_chart(self, name):
        """Adds an image chart, centered and at most 500px wide.

        Args:
            name (str): image file name/path.

        Returns:
            None
        """
        self.chart_html_obj = """
            <div class='chart-card' style='max-width:500px;margin-left:auto;margin-right:auto;'>
              <img src='{image}' alt=''/>
            </div>
            """.format(image=name)
        self.html += self.chart_html_obj

    def build_chart_custom(self, name, align='center', padding='15px', margin='5px 5px 2em 5px', width='500px', height='500px'):
        """Adds an image chart with your own alignment, spacing and size.

        Args:
            name (str): image file name/path.
            align (str): CSS text-align value for the chart card.
            padding (str): CSS padding for the chart card.
            margin (str): CSS margin for the chart card.
            width (str): CSS width for the image.
            height (str): CSS height for the image.

        Returns:
            None
        """
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
        """Adds an interactive ECharts chart-card to the report.

        Args:
            chart_id (str): unique DOM id for the chart container.
            chart_type (str): one of "line", "bar", "horizontal_bar", "connectivity_timeline", "pie".
            payload (dict): data in the shape the matching JS renderer expects, e.g.
                {"categories": [...], "series": [...]} for line/bar/horizontal_bar.
            title (str): chart title.
            y_name (str): y-axis label.
            x_name (str): x-axis label.

        Returns:
            None
        """
        if not self._echarts_runtime_emitted:
            self.html += _ECHARTS_RUNTIME_JS
            self._echarts_runtime_emitted = True
        self.html += _chart_markup(chart_id, chart_type, payload, title=title, y_name=y_name, x_name=x_name)

    def build_pie_chart_interactive(self, chart_id, labels, values, title=""):
        """Adds an interactive donut/pie chart from parallel labels/values lists. Kept for
        existing callers; delegates to the generic create_pie_chart() module function, which
        has the full option set (center labels, subtitles, custom tooltips, percentages, ...).

        Args:
            chart_id (str): unique DOM id for the chart container.
            labels (list): slice names, parallel to values.
            values (list): slice values, parallel to labels.
            title (str): chart title.

        Returns:
            None
        """
        data = [{"name": labels[i], "value": values[i]} for i in range(len(labels))]
        if not self._echarts_runtime_emitted:
            self.html += _ECHARTS_RUNTIME_JS
            self._echarts_runtime_emitted = True
        self.html += create_pie_chart(data, title=title, chart_id=chart_id, show_percentage=False)

    def build_pie_chart(self, data, title="", **kwargs):
        """Adds a create_pie_chart() chart directly to the report (also handles the one-time
        ECharts runtime injection). See create_pie_chart() for the full set of optional kwargs.

        Args:
            data (list): slice list, e.g. [{"name": "Pass", "value": 80}, ...].
            title (str): chart title.
            **kwargs: any other create_pie_chart() option (subtitle, chart_id, legend, ...).

        Returns:
            None
        """
        if not self._echarts_runtime_emitted:
            self.html += _ECHARTS_RUNTIME_JS
            self._echarts_runtime_emitted = True
        self.html += create_pie_chart(data, title=title, **kwargs)

    def build_info_card(self, title, items, icon=None, card_id=None):
        """Adds a create_info_card() card directly to the report. See create_info_card()
        for the full option set.

        Args:
            title (str): card header text.
            items (list): [{"icon": ..., "label": ..., "value": ...}, ...].
            icon: optional inline HTML for the card header's own icon badge.
            card_id (str): optional DOM id for the card.

        Returns:
            None
        """
        self.html += create_info_card(title, items, icon=icon, card_id=card_id)

    def build_findings_card(self, title, findings, card_id=None):
        """Adds a create_findings_card() card directly to the report. See create_findings_card()
        for the full option set.

        Args:
            title (str): card header text.
            findings (list): [{"type": ..., "text": ...}, ...].
            card_id (str): optional DOM id for the card.

        Returns:
            None
        """
        self.html += create_findings_card(title, findings, card_id=card_id)

    def build_device_summary_card(self, devices, **kwargs):
        """Adds a create_device_summary_card() card directly to the report (also handles the
        one-time ECharts + search-table runtime injection). See create_device_summary_card()
        for the full option set.

        Args:
            devices (list): [{"name": ..., "platform": ...}, ...].
            **kwargs: any other create_device_summary_card() option (name_field,
                platform_field, columns, platform_icons, page_size, card_id, title).

        Returns:
            None
        """
        if not self._echarts_runtime_emitted:
            self.html += _ECHARTS_RUNTIME_JS
            self._echarts_runtime_emitted = True
        if not self._table_runtime_emitted:
            self.html += _TABLE_RUNTIME_JS
            self._table_runtime_emitted = True
        self.html += create_device_summary_card(devices, **kwargs)


def _chart_markup(chart_id, chart_type, payload, title="", y_name="", x_name="", description=""):
    """Builds the <div class='chart-card'>...</div> markup (chart container + inline script
    invoking the shared JS renderer) for one chart. Used by lf_report.build_echarts_chart()
    and by the lf_bar_graph/lf_bar_graph_horizontal/lf_line_graph classes below.

    Args:
        chart_id (str): unique DOM id for the chart container.
        chart_type (str): one of "line", "bar", "horizontal_bar", "connectivity_timeline", "pie".
        payload (dict): data in the shape the matching JS renderer expects.
        title (str): chart title.
        y_name (str): y-axis label.
        x_name (str): x-axis label.
        description (str): optional text rendered under the title, inside the same card.

    Returns:
        str: the chart-card HTML.
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
        extra_args = ", {x}, {y}".format(x=json.dumps(x_name), y=json.dumps(y_name))

    return """
            <div class='chart-card'>
              {title_html}
              {description_html}
              <div id='{chart_id}' class='chart'></div>
              <script>
                window.__lfModernReport.{renderer}({chart_id_json}, {payload}{extra_args});
              </script>
            </div>
            """.format(
        title_html=("<h3>{}</h3>".format(title) if title else ""),
        description_html=("<p align='left'>{}</p>".format(description) if description else ""),
        chart_id=chart_id,
        chart_id_json=json.dumps(chart_id),
        renderer=renderer,
        payload=json.dumps(payload),
        extra_args=extra_args,
    )


def _sanitize_pie_slices(data):
    """Cleans up a pie-chart data list so it's safe to use: drops bad entries and fixes bad
    values instead of crashing. Never raises -- worst case it returns an empty list.

    Args:
        data (list): slices, e.g. [{"name": "Pass", "value": 80}, ...].

    Returns:
        list: cleaned slices, each {"name": str, "value": float}.
    """
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
    """Builds one pie/donut chart card. Any report section that needs a pie chart should use
    this instead of writing its own chart markup. Bad or empty data shows a "no data" card
    instead of crashing.

    Args:
        data (list): slices, e.g. [{"name": "Pass", "value": 80}, {"name": "Fail", "value": 15}].
        title (str): chart title.
        subtitle (str): one-line text shown under the title.
        chart_id (str): id for the chart container; auto-generated if left blank.
        legend (bool): show the bottom legend.
        show_percentage (bool): show the percent on each slice's label.
        show_labels (bool): show the on-slice text labels at all.
        center_label: text for the middle of the donut hole (a string, or {"main": ..., "sub": ...}).
        tooltip_formatter (str): custom ECharts tooltip format string.
        label_formatter (str): custom ECharts label format string.
        colors (list): one CSS color per slice, in data order.
        item_details (dict): {slice_name: [detail line, ...]} shown in that slice's tooltip.
        width: chart width (a number of pixels, or a CSS size like "60%").
        height: chart height (a number of pixels, or a CSS size like "300px").
        radius (list): inner/outer radius, e.g. ["0%", "70%"] for a solid pie.
        center (list): [x, y] position of the chart within its box.
        empty_message (str): message shown when there's no data to plot.

    Returns:
        str: the chart-card HTML.
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
    """Builds a titled card showing a grid of icon + label + value blocks, e.g. a test's
    configuration summary.

    Args:
        title (str): card header text.
        items (list): [{"icon": ..., "label": ..., "value": ...}, ...]; items with no value are skipped.
        icon: icon shown next to the card's own title, not the individual items.
        card_id (str): optional id for the card.

    Returns:
        str: the card HTML.
    """
    rows = []
    for item in items or []:
        value = item.get("value")
        # Callers commonly pass str(some_attr) straight through, so an unset
        # attribute (Python None) arrives here as the literal text "None"
        # rather than an empty string -- treat that the same as empty.
        if value is None or str(value).strip() == "" or str(value).strip().lower() == "none":
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
    """Builds a "Key Findings" card: a short bulleted list of plain-English observations, each
    tagged with a severity marker (checkmark/dot/warning/cross).

    Args:
        title (str): card header text.
        findings (list): [{"type": "positive"|"neutral"|"warning"|"critical", "text": ...}, ...],
            most important first.
        card_id (str): optional id for the card.

    Returns:
        str: the card HTML, or a plain "no findings" message if the list is empty.
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


# Inline artwork keeps platform badges available in offline HTML and PDF reports.
_PLATFORM_ICON_SHAPES = {
    "Android": '<g fill="#3d9b35"><path d="M5 10a7 7 0 0 1 14 0Z"/>'
               '<rect x="5" y="11" width="14" height="8" rx="2"/>'
               '<path d="M7 18h3v4H7zm7 0h3v4h-3z"/>'
               '<rect x="1" y="10" width="3" height="9" rx="1.5"/>'
               '<rect x="20" y="10" width="3" height="9" rx="1.5"/></g>'
               '<path d="m7 4-2-3m12 3 2-3" stroke="#3d9b35" stroke-linecap="round"/>'
               '<g fill="white"><circle cx="9" cy="7" r="1"/><circle cx="15" cy="7" r="1"/></g>',
    "Windows": '<path fill="#0078d4" d="M2 4 11 2.8V11H2Zm11-1.5L22 1v10h-9Z'
               'M2 13h9v8.2L2 20Zm11 0h9v10l-9-1.5Z"/>',
    "Linux": '<path fill="#202938" d="M7 10V7a5 5 0 0 1 10 0v3l4 9-5 2H8l-5-2Z"/>'
             '<ellipse cx="12" cy="15" rx="5" ry="6" fill="white"/>'
             '<g fill="white"><ellipse cx="10" cy="7" rx="1.5" ry="2"/>'
             '<ellipse cx="14" cy="7" rx="1.5" ry="2"/></g>'
             '<g fill="#202938"><circle cx="10.5" cy="7" r=".7"/>'
             '<circle cx="13.5" cy="7" r=".7"/></g>'
             '<path fill="#f5b522" d="m9 10 3-2 3 2-3 2ZM2 20l5-2 3 4H2Zm12 2 3-4 5 2v2Z"/>',
    "macOS": '<path fill="#374151" d="M16.8 1c.2 2-1.4 4-3.5 4.2C13 3.3 14.7 1.3 16.8 1Z'
             'M20.5 7.5c-1.1-1.6-2.7-2.3-4.2-2.3-1.8 0-2.7 1-4.1 1-1.3 0-2.4-1-4-1'
             'C5.4 5.2 3 7.6 3 11.3c0 4.7 3.3 10.7 6 10.7 1.5 0 2.1-.9 3.8-.9'
             's2.1.9 3.7.9c2 0 4-3.4 4.8-5.5-4.1-1.7-4.7-6.5-.8-9Z"/>',
}
_PLATFORM_ICONS = {
    name.lower(): '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
                  'width="24" height="24" style="width:24px;height:24px;display:block" '
                  'aria-hidden="true" focusable="false">' + shapes + '</svg>'
    for name, shapes in _PLATFORM_ICON_SHAPES.items()
}
_PLATFORM_ICONS["ios"] = _PLATFORM_ICONS["macos"]
for _alias in ("mac", "mac os", "mac os x", "osx", "darwin", "macbook"):
    _PLATFORM_ICONS[_alias] = _PLATFORM_ICONS["macos"]
for _alias in ("win", "win32", "win64"):
    _PLATFORM_ICONS[_alias] = _PLATFORM_ICONS["windows"]


def create_device_summary_card(devices, name_field="name", platform_field="platform",
                               columns=None, platform_icons=None, page_size=10,
                               card_id=None, title="Devices"):
    """Builds a device summary card: total/per-category counts, a donut breakdown, and a
    searchable, paginated table.

    Args:
        devices (list): dicts, e.g. [{"name": "vivo V12", "platform": "Android"}, ...].
        name_field (str): key in each device dict holding its display name.
        platform_field (str): key in each device dict holding its category, used for the counts/donut.
        columns (list): table columns, e.g. [{"key": ..., "label": ...}, ...]; defaults to name + platform.
        platform_icons (dict): {category_value: icon} shown next to that category's count.
        page_size (int): initial rows-per-page for the table.
        card_id (str): id prefix for the card; auto-generated if left blank.
        title (str): card header text.

    Returns:
        str: the card HTML. Going through lf_report.build_device_summary_card() instead of
        calling this directly also gets you the JS runtimes it needs, for free.
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
            """.format(icon=platform_icons.get(p, _PLATFORM_ICONS.get(str(p).strip().lower(), "&bull;")), count=platform_counts[p], label=p)
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
        rows_payload.append({"cellsHtml": cells})
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
    """Turns matplotlib short color codes (like 'r' or 'g') into CSS color names.

    Args:
        c: a color, e.g. 'r' or '#1f6f58'.

    Returns:
        the matching CSS color name, or c unchanged if it wasn't a short code.
    """
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
                 _extra_payload=None,
                 _description=""
                 ):
        """Stores the bar chart data and options.

        Args:
            _data_set (list): one list of values per series/bar group.
            _xaxis_name (str): x-axis label.
            _yaxis_name (str): y-axis label.
            _xaxis_categories (list): tick values shown on the x-axis.
            _xaxis_label (list): tick text shown on the x-axis instead of _xaxis_categories,
                if it's the same length as the data.
            _graph_title (str): chart title.
            _graph_image_name (str): chart id, and the CSV file name when _enable_csv is True.
            _label (list): one name per series, used in the legend.
            _color (list): one color per series/bar; falls back to _color_name.
            _color_name (list): palette to use when _color isn't given.
            _enable_csv (bool): also save the data as a CSV file.
            _stacked (bool): stack the bars instead of placing them side by side.
            _extra_payload (dict): extra chart options merged into the chart payload.
            _description (str): text shown under the chart title.

            Most other options (_bar_width, _color_edge, _font_weight, _figsize,
            _show_bar_value, _xaxis_step, _xticks_font, _xaxis_value_location,
            _xticks_rotation, _text_font, _text_rotation, _grp_title, _legend_*, _dpi,
            _remove_border, _alignment, _title_size) are matplotlib-only: they're accepted so
            old callers keep working, but this interactive version doesn't use them.

        Returns:
            None
        """
        if _data_set is None:
            _data_set = [[30.4, 55.3, 69.2, 37.1], [45.1, 67.2, 34.3, 22.4], [22.5, 45.6, 12.7, 34.8]]
        if _xaxis_categories is None:
            _xaxis_categories = [1, 2, 3, 4]
        # No demo default for _xaxis_label -- unlike _xaxis_categories, this is an opt-in
        # override (build_bar_graph() only uses it if a caller explicitly supplies one whose
        # length matches the data). A truthy placeholder here would silently replace a caller's
        # real _xaxis_categories whenever the category count happened to match its length.
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
        self.description = _description

    def build_bar_graph(self):
        """Returns the interactive bar chart as HTML for set_graph_image().
        Also saves <graph_image_name>.csv when _enable_csv is True."""
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
                               title=self.title, x_name=self.xaxis_name, y_name=self.yaxis_name,
                               description=self.description)

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
                 _stacked=False,
                 _description=""
                 ):
        """Stores the horizontal bar chart data and options.

        Args:
            _data_set (list): one list of values per series/bar group.
            _xaxis_name (str): x-axis label.
            _yaxis_name (str): y-axis label.
            _yaxis_categories (list): tick values shown on the y-axis.
            _yaxis_label (list): tick text shown on the y-axis instead of _yaxis_categories,
                if it's the same length as the data.
            _graph_title (str): chart title.
            _graph_image_name (str): chart id, and the CSV file name when _enable_csv is True.
            _label (list): one name per series, used in the legend.
            _color (list): one color per series/bar; falls back to _color_name.
            _color_name (list): palette to use when _color isn't given.
            _enable_csv (bool): also save the data as a CSV file.
            _stacked (bool): stack the bars instead of placing them side by side.
            _description (str): text shown under the chart title.

            Most other options (_bar_height, _color_edge, _font_weight, _figsize,
            _show_bar_value, _yaxis_step, _yticks_font, _yaxis_value_location,
            _yticks_rotation, _text_font, _text_rotation, _grp_title, _legend_*, _dpi,
            _remove_border, _alignment, _title_size) are matplotlib-only: they're accepted so
            old callers keep working, but this interactive version doesn't use them.

        Returns:
            None
        """
        if _data_set is None:
            _data_set = [[30.4, 55.3, 69.2, 37.1], [45.1, 67.2, 34.3, 22.4], [22.5, 45.6, 12.7, 34.8]]
        if _yaxis_categories is None:
            _yaxis_categories = [1, 2, 3, 4]
        # No demo default for _yaxis_label -- unlike _yaxis_categories, this is an opt-in
        # override (build_bar_graph_horizontal() only uses it if a caller explicitly supplies
        # one whose length matches the data). A truthy placeholder here would silently replace
        # a caller's real _yaxis_categories whenever the category count happened to match its length.
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
        self.description = _description

    def build_bar_graph_horizontal(self):
        """Returns the interactive horizontal bar chart as HTML for set_graph_image().
        Also saves <graph_image_name>.csv when _enable_csv is True."""
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
                               title=self.title, x_name=self.xaxis_name, y_name=self.yaxis_name, description=self.description)

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
                 _dashed=None,
                 _description=""):
        """Stores the line chart data and options.

        Args:
            _data_set (list): one list of values per line.
            _xaxis_name (str): x-axis label.
            _yaxis_name (str): y-axis label.
            _xaxis_categories (list): tick values shown on the x-axis.
            _xaxis_label (list): tick text shown on the x-axis.
            _graph_title (str): chart title.
            _graph_image_name (str): chart id, and the CSV file name when _enable_csv is True.
            _label (list): one name per line, used in the legend.
            _color (list): one color per line.
            _enable_csv (bool): also save the data as a CSV file.
            _reverse_x (bool): flip the x-axis direction.
            _reverse_y (bool): flip the y-axis direction.
            _dashed (list): one True/False per line, to draw it dashed, e.g. a target line.
            _description (str): text shown under the chart title.

            Most other options (_title_size, _font_weight, _figsize, _xaxis_step,
            _xticks_font, _text_font, _legend_*, _marker, _dpi, _grid) are matplotlib-only:
            they're accepted so old callers keep working, but this interactive version
            doesn't use them.

        Returns:
            None
        """
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
        self.description = _description

    def build_line_graph(self):
        """Returns the interactive line chart as HTML for set_graph_image().
        Also saves <graph_image_name>.csv when _enable_csv is True."""
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
                               title=self.grp_title, x_name=self.xaxis_name, y_name=self.yaxis_name,
                               description=self.description)

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
        """Stores the pie chart values, labels and display options.

        Args:
            _data_set (list): slice values.
            _label (list): one name per slice, parallel to _data_set.
            _graph_title (str): chart title.
            _graph_image_name (str): chart id, and the CSV file name when _enable_csv is True.
            _subtitle (str): one-line text shown under the title.
            _legend (bool): show the bottom legend.
            _show_percentage (bool): show the percent on each slice's label.
            _show_labels (bool): show the on-slice text labels at all.
            _center_label: text for the middle of the donut hole.
            _tooltip_formatter (str): custom ECharts tooltip format string.
            _label_formatter (str): custom ECharts label format string.
            _colors (list): one CSS color per slice.
            _item_details (dict): {slice_name: [detail line, ...]} shown in that slice's tooltip.
            _radius (list): inner/outer radius, e.g. ["0%", "70%"] for a solid pie.
            _center (list): [x, y] position of the chart within its box.
            _figsize (tuple): (width, height) in pixels; kept for signature parity with the
                other graph classes' matplotlib _figsize.
            _empty_message (str): message shown when there's no data to plot.
            _enable_csv (bool): also save the data as a CSV file.

        Returns:
            None
        """
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
        """Returns the interactive pie chart as HTML for set_graph_image().
        Also saves <graph_image_name>.csv when _enable_csv is True."""
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


if __name__ == "__main__" and _IS_PDF_WORKER:
    _run_pdf_worker()
    sys.exit(0)


# Unit Test
if __name__ == "__main__":
    help_summary = '''\
     Builds LANforge test reports (HTML and PDF) with graphs, tables and an objective/description
     section. Modern-report-styled drop-in replacement for lf_report.py -- same API, new look.
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
