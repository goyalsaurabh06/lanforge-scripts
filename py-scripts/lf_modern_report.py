#!/usr/bin/env python3
"""
NAME: lf_modern_report.py

PURPOSE:

- Drop-in replacement for lf_report.py: same `lf_report` class API, so
  existing scripts only need to change `from lf_report import lf_report`
  to `from lf_modern_report import lf_report`.
- Generates HTML reports with a modern stylesheet (artifacts/modern-report.css)
  and a self-hosted Apache ECharts runtime (artifacts/echarts.min.js) for
  interactive charts (see build_echarts_chart).
- Existing matplotlib-PNG charts (from lf_graph.py or elsewhere) still work
  unchanged, just shown inside a modern chart-card container.
- Its own interactive chart classes (lf_bar_graph, lf_bar_graph_horizontal,
  lf_line_graph, lf_pie_graph) live in lf_modern_graph.py. lf_modern_graph.py
  itself has no dependency on this file (mirrors how lf_graph.py has no
  dependency on lf_report.py), but this file imports lf_pie_graph from it so
  build_device_summary_card() can share its pie-slice payload building
  instead of duplicating it.

EXAMPLE:
    from lf_modern_report import lf_report

    report = lf_report(_title="My Test Report")
    report.build_banner()
    report.set_table_dataframe(dataframe)
    report.build_table()
    report.build_footer()
    report.write_html()
    report.write_pdf()

LICENSE:
    Free to distribute and modify. LANforge systems must be licensed.
    Copyright (C) 2020-2026 Candela Technologies Inc

INCLUDE_IN_README
"""
# CAUTION: adding imports to this file which are not in update_dependencies.py is not advised
import argparse
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
import traceback
from pathlib import Path

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
    lf_pie_graph = importlib.import_module("py-scripts.lf_modern_graph").lf_pie_graph
    os_name = platform.system()

__all__ = ["lf_report"]

# ECharts styling conventions below are lifted verbatim (palette, baseOption,
# tooltip/legend/axis/dataZoom conventions, named-series coloring) from the
# existing modern report sample so any interactive chart added through this
# module looks consistent with that established visual language.
_ECHARTS_PALETTE = ["#1f6f58", "#f1b24a", "#2f80ed", "#1d9a8a", "#d95f5f", "#d48b1f"]

# Auto-assigned DOM ids for charts created without an explicit chart_id (e.g.
# build_device_summary_card(devices=...) with no card_id kwarg), so multiple
# charts can be dropped into the same report without the caller having to
# invent/track unique ids themselves.
_chart_id_counter = 0

def _next_chart_id(prefix):
    """Returns a new unique chart id like '<prefix>-3', so charts on one page never clash.

    Args:
        prefix (str): text to put before the counter, e.g. "pie-chart".

    Returns:
        str: a new id such as "pie-chart-3".

    Example:
        chart_id = _next_chart_id("pie-chart")
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

def ensure_dependencies():
    """Locates the Chromium browser playwright needs for PDF export. Installed by
    update_dependencies.py's install_playwright_browser() (the playwright pip
    package alone doesn't include the browser binary) -- this only locates it,
    it doesn't install anything.

    Returns:
        str: path to the Chromium executable.

    Example:
        chromium_path = ensure_dependencies()
    """
    configured = os.environ.get('PLAYWRIGHT_BROWSERS_PATH')
    if configured == '0':
        raise RuntimeError('Use a persistent directory for PLAYWRIGHT_BROWSERS_PATH, not 0')
    browser_dir = Path(configured).expanduser().resolve() if configured else (
        Path.home() / '.cache' / 'lanforge' / 'report-browsers')
    os.environ['PLAYWRIGHT_BROWSERS_PATH'] = str(browser_dir)
    sync_playwright = importlib.import_module('playwright.sync_api').sync_playwright
    with sync_playwright() as playwright:
        override = os.environ.get('LF_REPORT_CHROMIUM_EXECUTABLE')
        executable = Path(override).expanduser().resolve() if override else Path(playwright.chromium.executable_path)
    if not executable.is_file():
        raise RuntimeError(
            f'Chromium not found at {executable}. Run update_dependencies.py to install PDF export '
            'dependencies (or set LF_REPORT_CHROMIUM_EXECUTABLE to point at an existing Chromium).')
    return str(executable)

def export_pdf(source, destination, page_size='A4', orientation='Portrait', page_width=None, page_height=None):
    """Render a saved HTML report with headless Chromium.

    Args:
        source (str): path to the report HTML file to render.
        destination (str): path the PDF should be written to.
        page_size (str): one of 'A4', 'A3', 'Letter', 'Legal'. Ignored when page_width/page_height are set.
        orientation (str): 'Portrait' or 'Landscape'.
        page_width (str): custom page width, e.g. '210mm'. Requires page_height to also be set.
        page_height (str): custom page height, e.g. '297mm'. Requires page_width to also be set.

    Example:
        export_pdf("outfile.html", "outfile.pdf", page_size="A4", orientation="Landscape")
    """
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
    """Parse the isolated PDF worker command line and export the report.

    Example:
        python lf_modern_report.py --pdf-worker outfile.html outfile.pdf --page-size A4
    """
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
    Same API as the old lf_report.py; only the look is modernized.

    Example:
        report = lf_report(_title="My Test Report")
        report.build_banner()
        report.build_footer()
        report.write_html()
        report.write_pdf()
    """
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

        Example:
            label, color = lf_report.classify_score_rating(85)
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

        Example:
            report = lf_report(_path="/home/lanforge/html-reports", _title="My Test Report",
                                _results_dir_name="LANforge_Test_Results")
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
        """Copies the banner image into the report folder.

        Example:
            report.copy_banner()
        """
        banner_src_file = str(self.current_path) + '/' + str(self.banner_directory) + '/' + str(self.banner_file_name)
        banner_dst_file = str(self.path_date_time) + '/' + str(self.banner_file_name)
        shutil.copy(banner_src_file, banner_dst_file)

    def copy_css(self):
        """Copies the stylesheet (saved as report.css), custom.css and the report font into the report folder.

        Example:
            report.copy_css()
        """
        # modern report stylesheet is copied to the same output filename ("report.css")
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
        """Copies the ECharts library (used by the interactive charts) into the report folder.

        Example:
            report.copy_echarts()
        """
        echarts_src_file = str(self.current_path) + '/' + str(self.banner_directory) + '/' + str(self.echarts_file)
        echarts_dst_file = str(self.path_date_time) + '/' + str(self.echarts_file)
        shutil.copy(echarts_src_file, echarts_dst_file)

    def copy_logo(self):
        """Copies the header logo into the report folder.

        Example:
            report.copy_logo()
        """
        logo_src_file = str(self.current_path) + '/' + str(self.logo_directory) + '/' + str(self.logo_file_name)
        logo_dst_file = str(self.path_date_time) + '/' + str(self.logo_file_name)
        shutil.copy(logo_src_file, logo_dst_file)

    def copy_logo_footer(self):
        """Copies the small footer logo into the report folder.

        Example:
            report.copy_logo_footer()
        """
        logo_footer_src_file = str(self.current_path) + '/' + str(self.logo_directory) + '/' + str(
            self.logo_footer_file_name)
        logo_footer_dst_file = str(self.path_date_time) + '/' + str(self.logo_footer_file_name)
        shutil.copy(logo_footer_src_file, logo_footer_dst_file)

    def move_graph_image(self, ):
        """Moves the current graph PNG into the report folder.
        Does nothing for interactive charts, since those are HTML and not a file.

        Example:
            report.move_graph_image()
        """
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
        """Moves the current CSV file (set by set_csv_filename) into the report folder.

        Example:
            report.move_csv_file()
        """
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

        Example:
            report.set_date_time_directory("2026-01-01-12-00-00", "LANforge_Test_Results")
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
        Falls back to a folder next to this script if the path can't be created.

        Example:
            report.build_date_time_directory()
        """
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
        """Creates the 'log' sub-folder inside the report folder; exits if that fails.

        Example:
            report.build_log_directory()
        """
        if self.log_directory == "":
            self.log_directory = os.path.join(self.path_date_time, "log")
        try:
            if not os.path.exists(self.log_directory):
                os.mkdir(self.log_directory)
        except Exception as x:
            traceback.print_exception(Exception, x, x.__traceback__, chain=True)
            logger.critical("exception making {}".format(self.log_directory))
            exit(1)

    def set_title(self, _title):
        """Sets the report title shown in the banner.

        Args:
            _title (str): report title.

        Example:
            report.set_title("My Test Report")
        """
        self.title = _title

    def set_table_title(self, _table_title):
        """Sets the heading used by the next build_table_title() call.

        Args:
            _table_title (str): table heading.

        Example:
            report.set_table_title("Station Results")
        """
        self.table_title = _table_title

    # sets the csv file name as graph title
    def set_csv_filename(self, _graph_title):
        """Sets the CSV file name to the graph name with a .csv extension.

        Args:
            _graph_title (str): name to base the CSV file name on.

        Example:
            report.set_csv_filename("throughput-graph")
        """
        fname, ext = os.path.splitext(_graph_title)
        self.csv_file_name = fname + ".csv"

    # The _date is set when class is enstanciated / created so this set_date should be used with caution, used to synchronize results

    def set_table_dataframe(self, _dataframe):
        """Sets the table (pandas DataFrame) used by the next build_table() call.

        Args:
            _dataframe (DataFrame): table to store.

        Example:
            report.set_table_dataframe(dataframe)
        """
        self.dataframe = _dataframe

    # TODO

    def set_custom_html(self, _custom_html):
        """Sets raw HTML to add with the next build_custom() call.

        Args:
            _custom_html (str): raw HTML to store.

        Example:
            report.set_custom_html("<p>Custom section</p>")
        """
        self.custom_html = _custom_html

    def set_obj_html(self, _obj_title, _obj):
        """Sets the heading and text for the next build_objective() section.

        Args:
            _obj_title (str): objective heading.
            _obj (str): objective body text.

        Example:
            report.set_obj_html("Objective", "Verify throughput under load.")
        """
        self.objective = _obj
        self.obj_title = _obj_title

    def set_graph_image(self, _graph_image):
        """Sets the graph (a PNG path or interactive chart HTML) used by the next build_graph() call.

        Args:
            _graph_image (str): PNG file path, or interactive chart HTML.

        Example:
            report.set_graph_image("throughput.png")
        """
        self.graph_image = _graph_image

    def get_path(self):
        """Returns the base folder the report folder is created under.

        Returns:
            str: the base report folder path.

        Example:
            base_path = report.get_path()
        """
        return self.path

    # get_path_date_time, get_report_path and need to be the same
    def get_path_date_time(self):
        """Returns the full path of this report's folder.

        Returns:
            str: the full path to this report's '<date>_<results_dir_name>' folder.

        Example:
            report_folder = report.get_path_date_time()
        """
        return self.path_date_time


    def write_html(self):
        """Writes the report HTML to the report folder and returns the file path.

        Returns:
            str: full path to the written HTML file, or None if no HTML file name was set.

        Example:
            html_file = report.write_html()
        """
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

    @staticmethod
    def _write_pdf_file(input_html, output_pdf, options, configuration=None):
        """Export HTML through Chromium or the legacy wkhtmltopdf backend.

        Args:
            input_html (str): path to the source HTML report.
            output_pdf (str): path the PDF should be written to.
            options (dict): PDF options from _pdf_options(), or wkhtmltopdf-style options.
            configuration: optional pdfkit.configuration() object (wkhtmltopdf backend only).

        Example:
            lf_report._write_pdf_file("outfile.html", "outfile.pdf", {"page-size": "A4", "orientation": "Portrait"})
        """
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
        """Build options shared by both PDF output methods.

        Args:
            page_size (str): one of 'A4', 'A3', 'Letter', 'Legal'. Ignored when page_width/page_height are set.
            orientation (str): 'Portrait' or 'Landscape'.
            page_width (str): custom page width, e.g. '210mm'. Requires page_height to also be set.
            page_height (str): custom page height, e.g. '297mm'. Requires page_width to also be set.

        Returns:
            dict: options for pdfkit/the Chromium worker.

        Example:
            options = lf_report._pdf_options("A4", "Portrait", None, None)
        """
        if (page_width is None) != (page_height is None):
            raise ValueError('Custom PDF size requires both page width and height')
        options = {'enable-local-file-access': None, 'orientation': orientation}
        if page_width is None:
            options['page-size'] = page_size
        else:
            options.update({'page-width': page_width, 'page-height': page_height})
        return options

    def write_pdf(self, _page_size='A4', _orientation='Portrait', _page_width=None, _page_height=None):
        """Write the report PDF to the report folder.

        Args:
            _page_size (str): one of 'A4', 'A3', 'Letter', 'Legal'. Ignored when _page_width/_page_height are set.
            _orientation (str): 'Portrait' or 'Landscape'.
            _page_width (str): custom page width, e.g. '210mm'. Requires _page_height to also be set.
            _page_height (str): custom page height, e.g. '297mm'. Requires _page_width to also be set.

        Example:
            report.write_pdf(_page_size="A4", _orientation="Landscape")
        """
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


    _ASSET_MIME_TYPES = {".css": "text/css", ".js": "text/javascript", ".png": "image/png", ".woff": "font/woff"}

    def _read_report_asset(self, filename):
        """Reads a file already copied into this report's folder. Returns "" if it's missing,
        so a report still builds (just without that one piece) instead of crashing.

        Args:
            filename (str): asset file name, relative to the report folder.

        Returns:
            str: the file's contents, or "" if it's missing.

        Example:
            css_text = report._read_report_asset("report.css")
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

        Example:
            logo_uri = report._report_asset_as_data_uri("yellow.png")
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

        Example:
            head_html = report.get_html_head(title="My Test Report")
        """
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
        """Starts the page and adds the top banner with the title, date and logo on the right.

        Example:
            report.build_banner()
        """
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

    def build_table_title(self):
        """Adds the table heading set by set_table_title().

        Example:
            report.set_table_title("Station Results")
            report.build_table_title()
        """
        self.table_title_html = """
                    <!-- Table Title-->
                    <h3 align='left'>{title}</h3>
                    """.format(title=self.table_title)
        self.html += self.table_title_html

    def start_content_div(self):
        """Opens a 'contentDiv' section; close it with end_content_div().

        Example:
            report.start_content_div()
        """
        self.html += "\n<div class='contentDiv'>\n"

    @staticmethod
    def _keep_identifiers_on_one_line(table_html, dataframe):
        """Mark SSID, BSSID, and MAC cells so print CSS keeps their values intact.

        Args:
            table_html (str): HTML produced by DataFrame.to_html() for the table.
            dataframe (DataFrame): the table the HTML was generated from, used to find
                which columns are SSID/BSSID/MAC identifier columns.

        Returns:
            str: the table HTML with identifier cells tagged with class="network-identifier".

        Example:
            html = lf_report._keep_identifiers_on_one_line(table_html, dataframe)
        """
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
        """Adds the current table (set by set_table_dataframe) to the report.

        Example:
            report.set_table_dataframe(dataframe)
            report.build_table()
        """
        self.dataframe_html = self.dataframe.to_html(index=False, justify='center', classes='data-table')
        self.dataframe_html = self._keep_identifiers_on_one_line(self.dataframe_html, self.dataframe)
        self.html += "<div class='table-wrap'>" + self.dataframe_html + "</div>"

    def rating_build_table(self, rating_column, rating_colors):
        """Like pass_failed_build_table(), but for any column of rating labels (e.g.
        "Excellent"/"Good"/"Average"/"Poor") instead of a fixed Success/Failed pair.

        Args:
            rating_column (str): name of the column to show as colored badges.
            rating_colors (dict): maps each label to a CSS color; labels missing from it
                stay plain text.

        Example:
            report.set_table_dataframe(dataframe)
            report.rating_build_table("Rating", {"Excellent": "#1e7e34", "Poor": "#e74c3c"})
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

    def build_footer(self):
        """Adds the footer with the Candela logo and closes the page layout.

        Example:
            report.build_footer()
        """
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

    def build_custom(self):
        """Adds the raw HTML set by set_custom_html().

        Example:
            report.set_custom_html("<p>Custom section</p>")
            report.build_custom()
        """
        self.html += self.custom_html

    def build_objective(self):
        """Adds a heading and paragraph section, using the text from set_obj_html().

        Example:
            report.set_obj_html("Objective", "Verify throughput under load.")
            report.build_objective()
        """
        self.obj_html = """
            <!-- Test Objective -->
            <div class='chart-card' style='text-align:left;'>
              <h3 align='left'>{title}</h3>
              <p align='left' width='900'>{objective}</p>
            </div>
            """.format(title=self.obj_title,
                       objective=self.objective)
        self.html += self.obj_html

    def build_graph(self):
        """Adds the graph set by set_graph_image(): a PNG inside a chart card,
        or an interactive chart as it is.

        Example:
            report.set_graph_image("throughput.png")
            report.build_graph()
        """
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

    def end_content_div(self):
        """Closes a section opened with start_content_div() or start_content_div2().

        Example:
            report.end_content_div()
        """
        self.html += "\n</div><!-- end contentDiv -->\n"

    def build_chart_title(self, chart_title):
        """Adds a chart heading.

        Args:
            chart_title (str): heading text.

        Example:
            report.build_chart_title("Throughput Over Time")
        """
        self.chart_title_html = """
            <div class='HeaderStyle'>
                <h3 class='TitleFontPrint'>{title}</h3>
            """.format(title=chart_title)
        self.html += self.chart_title_html

    def build_info_card(self, title, items, icon=None, card_id=None):
        """Adds a titled card showing a grid of icon + label + value blocks, e.g. a test's
        configuration summary.

        Args:
            title (str): card header text.
            items (list): [{"icon": ..., "label": ..., "value": ...}, ...]; items with no value are skipped.
            icon: icon shown next to the card's own title, not the individual items.
            card_id (str): optional DOM id for the card.

        Example:
            report.build_info_card("Test Configuration", [
                {"icon": "&#9881;", "label": "SSID", "value": "my-ssid"},
                {"icon": "&#128225;", "label": "Band", "value": "5 GHz"},
            ])
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

        self.html += """
                <div class='info-card'{id_attr}>
                  <div class='info-card-header'>{header_icon}{title}</div>
                  <div class='info-grid'>{rows}</div>
                </div>
                """.format(id_attr=id_attr, header_icon=header_icon_html, title=title, rows="".join(rows))

    def build_findings_card(self, title, findings, card_id=None):
        """Adds a "Key Findings" card: a short bulleted list of plain-English observations,
        each tagged with a severity marker (checkmark/dot/warning/cross).

        Args:
            title (str): card header text.
            findings (list): [{"type": "positive"|"neutral"|"warning"|"critical", "text": ...}, ...],
                most important first.
            card_id (str): optional DOM id for the card.

        Example:
            report.build_findings_card("Key Findings", [
                {"type": "positive", "text": "Throughput met the target on all stations."},
                {"type": "warning", "text": "One station dropped connectivity briefly."},
            ])
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
            self.html += """
                <div class='info-card'{id_attr}>
                  <div class='info-card-header'>{title}</div>
                  <p style='color:var(--muted);'>No findings available for this data.</p>
                </div>
                """.format(id_attr=id_attr, title=title)
            return

        self.html += """
                <div class='info-card'{id_attr}>
                  <div class='info-card-header'>{title}</div>
                  <ul class='findings-list'>{items}</ul>
                </div>
                """.format(id_attr=id_attr, title=title, items="".join(items))

    def build_device_summary_card(self, devices, name_field="name", platform_field="platform",
                                  columns=None, platform_icons=None, page_size=10,
                                  card_id=None, title="Devices"):
        """Adds a device summary card: total/per-category counts, a donut breakdown, and a
        searchable, paginated table. Also handles the one-time ECharts + search-table
        runtime injection.

        Args:
            devices (list): dicts, e.g. [{"name": "vivo V12", "platform": "Android"}, ...].
            name_field (str): key in each device dict holding its display name.
            platform_field (str): key in each device dict holding its category, used for the counts/donut.
            columns (list): table columns, e.g. [{"key": ..., "label": ...}, ...]; defaults to name + platform.
            platform_icons (dict): {category_value: icon} shown next to that category's count.
            page_size (int): initial rows-per-page for the table.
            card_id (str): id prefix for the card; auto-generated if left blank.
            title (str): card header text.

        Example:
            report.build_device_summary_card([
                {"name": "vivo V12", "platform": "Android"},
                {"name": "iPhone 13", "platform": "iOS"},
            ])
        """
        if not self._echarts_runtime_emitted:
            self.html += _ECHARTS_RUNTIME_JS
            self._echarts_runtime_emitted = True
        if not self._table_runtime_emitted:
            self.html += _TABLE_RUNTIME_JS
            self._table_runtime_emitted = True

        devices = devices or []
        card_id = card_id or _next_chart_id("device-summary")
        columns = columns or [{"key": name_field, "label": "Device Name"}, {"key": platform_field, "label": "OS type"}]
        platform_icons = platform_icons or {}

        if not devices:
            self.html += """
                <div class='info-card' id='{card_id}'>
                  <div class='info-card-header'>{title}</div>
                  <p style='color:var(--muted);'>No devices to show.</p>
                </div>
                """.format(card_id=card_id, title=title)
            return

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

        legend_items = []
        for i, p in enumerate(ordered_platforms):
            count = platform_counts[p]
            pct = count / total * 100
            color = _ECHARTS_PALETTE[i % len(_ECHARTS_PALETTE)]
            legend_items.append("""
                <div class='device-legend-item'>
                  <span class='device-legend-dot' style='background:{color}'></span>
                  <span class='device-legend-name'>{name} ({count})</span>
                  <span class='device-legend-pct'>{pct:.1f}%</span>
                </div>
                """.format(color=color, name=p, count=count, pct=pct))

        # Shares lf_pie_graph's slice/payload building instead of re-implementing it here --
        # bare chart_id+payload (no card/title/legend), since this donut is embedded in its
        # own stats/donut/table layout with a custom legend, not a standalone chart-card.
        donut_pie = lf_pie_graph(
            _data_set=[platform_counts[p] for p in ordered_platforms],
            _label=ordered_platforms,
            _legend=False,
            _show_labels=False,
            _tooltip_formatter="{b}: {c} ({d}%)",
        )
        donut_id, donut_payload = donut_pie.build_pie_payload(chart_id="{}-donut".format(card_id))
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

        self.html += """
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

_FINDING_TYPE_ICON = {"positive": "&#10003;", "neutral": "&bull;", "warning": "&#9888;", "critical": "&#10007;"}

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
    "iOS": '<rect x="7" y="1" width="10" height="22" rx="2.2" fill="#374151"/>'
           '<rect x="7.9" y="3.3" width="8.2" height="16.6" fill="white"/>'
           '<circle cx="12" cy="20.7" r="1" fill="#374151"/>',
}
_PLATFORM_ICONS = {
    name.lower(): '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
                  'width="24" height="24" style="width:24px;height:24px;display:block" '
                  'aria-hidden="true" focusable="false">' + shapes + '</svg>'
    for name, shapes in _PLATFORM_ICON_SHAPES.items()
}
for _alias in ("mac", "mac os", "mac os x", "osx", "darwin", "macbook"):
    _PLATFORM_ICONS[_alias] = _PLATFORM_ICONS["macos"]
for _alias in ("win", "win32", "win64"):
    _PLATFORM_ICONS[_alias] = _PLATFORM_ICONS["windows"]

_CHART_MARKUP_SENTINEL = "<div class='chart-card'>"

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

    # lf_pie_graph demo: class-based counterpart to lf_bar_graph/lf_line_graph
    # above (parallel _data_set/_label lists instead of {"name","value"} dicts).
    pie = lf_pie_graph(_data_set=[40, 45, 15],
                       _label=["2.4 GHz", "5 GHz", "6 GHz"],
                       _graph_title="Band Distribution",
                       _graph_image_name="demo-band-distribution")
    report.set_graph_image(pie.build_pie_graph())
    report.build_graph()

    report.build_footer()

    html_file = report.write_html()
    logger.info("returned file ")
    logger.info(html_file)
    report.write_pdf()

    logger.info("report path {}".format(report.get_path()))
