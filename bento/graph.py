# import pandas as pd
# import numpy as np
# import datetime as dt
import math
import plotly.graph_objects as go

from bento import util as butil
from bento.resources import geojson
from bento.common import logger, dictutil  # noqa

logging = logger.fancy_logger(__name__)


class Graph:
    @classmethod
    def normal(
        cls,
        idf,
        variant="scatter",
        x_column=None,
        y_column=None,
        x_label=None,
        y_label=None,
        x_scale="linear",
        y_scale="linear",
        opacity=0.7,
        mode="lines+markers",
        line_width=3,
        marker_size=10,
        marker_line_width=0.5,
        marker_line_color="black",
        filters=[],
        transforms=[],
        **kwargs,
    ):

        x_label = x_label or x_column
        y_label = y_label or y_column

        graph_call = getattr(go, variant.title())

        fig = go.Figure()
        if variant in ("pie"):
            fdf = butil.filter_df(idf, filters)
            default_settings = {}
            data_settings = {
                "pie": {"labels": fdf[x_column], "values": fdf[y_column],},
            }
            style_settings = {}
            settings = data_settings.get(variant, default_settings)
            settings.update(style_settings.get(variant, {}))

            fig.add_trace(graph_call(**settings))

        elif variant in ("scatter", "bar", "histogram"):
            traces = butil.prepare_traces(idf, filters)
            traces = butil.trace_analytics(traces, transforms)
            for trace_df in traces:
                default_settings = {
                    "x": trace_df[x_column],
                    "y": trace_df[y_column],
                    "text": trace_df["label"],
                    "name": trace_df.name,
                }

                data_settings = {
                    "histogram": {"x": trace_df[y_column]},
                }

                style_settings = {
                    "scatter": {
                        "opacity": opacity,
                        "mode": mode,
                        "line_width": line_width,
                        "marker_size": marker_size,
                        "marker_line_width": marker_line_width,
                        "marker_line_color": marker_line_color,
                    },
                }

                settings = data_settings.get(variant, default_settings)
                settings.update(style_settings.get(variant, {}))

                fig.add_trace(graph_call(**settings))

        barmode = mode if mode in ["stack", "group", "relative"] else "stack"
        layout = {
            "margin": {
                "l": 16 + 4 * 4,
                "b": 40 + 4 * 4,
                "t": 40 + 4 * 4,
                "r": 40 + 4 * 4,
            },
            "barmode": barmode,
            "legend_x": 0,
            "legend_y": 1,
            "legend_bgcolor": "rgba(0,0,0,0)",
            "legend_font_size": 10,
            "title": f"{butil.titlize(y_label)} vs. {butil.titlize(x_label)}",
            "xaxis": {
                "type": x_scale,
                "title": butil.titlize(x_label),
                # "range": butil.data_range(traces, x_column, x_scale),
            },
            "yaxis": {
                "type": y_scale,
                "title": butil.titlize(y_label),
                # "range": butil.data_range(traces, y_column, y_scale),
            },
        }

        if variant == "pie":
            layout.update({"legend_x": 1, "legend_y": 1})
            pass

        if variant == "histogram":
            layout = {
                "xaxis": {"title": butil.titlize(y_label),},
                "yaxis": {"title": f"Histogram Count of {y_label}",},
            }

        fig.update_layout(layout)
        return fig

    @classmethod
    def map(
        cls,
        idf,
        variant="Scatter",
        z_column=None,
        geo="us_states",
        mapbox_center="default",
        mapbox_style="carto-darkmatter",
        mapbox_zoom=3,
        marker_size=5,
        marker_opacity=0.8,
        marker_line_width=0,
        marker_line_color="black",
        filters=[],
        **kwargs,
    ):
        fig = go.Figure()

        # First, create the single data trace
        base_args = {
            "marker_opacity": marker_opacity,
        }
        pdf = butil.filter_df(idf, filters)

        if variant == "scatter":
            pdf = pdf.groupby(["latitude", "longitude"]).sum().reset_index()
            args = {
                **base_args,
                "lon": pdf["longitude"],
                "lat": pdf["latitude"],
                "marker_size": marker_size,
            }
        elif variant == "choropleth":
            # Leading two digits of fips are state code
            if geo == "us_states":
                pdf["fips"] = pdf["fips"].str.slice(0, 2)
            pdf = pdf.groupby(["fips"]).sum().reset_index()
            args = {
                **base_args,
                "z": pdf[z_column],
                "geojson": geojson[geo],
                "locations": pdf["fips"],
                "marker_line_width": marker_line_width,
                "marker_line_color": marker_line_color,
                "colorscale": butil.log_color_scale("Viridis", base=3),
                "showscale": False,
            }

        trace = getattr(go, f"{variant.capitalize()}mapbox")(args)
        fig.add_trace(trace)

        if mapbox_center == "default":
            if "us" in geo:
                mapbox_center = {"lat": 37.0902, "lon": -95.7129}
                mapbox_zoom = 3
        elif mapbox_center == "auto":
            if variant == "scatter":
                ref_lat, ref_lon, ref_zoom = 25, 60, 3
                midpoint_lat = (pdf["latitude"].min() + pdf["latitude"].max()) / 2
                midpoint_lon = (pdf["longitude"].min() + pdf["longitude"].max()) / 2
                mapbox_center = {"lat": midpoint_lat, "lon": midpoint_lon}

                lat_delta = pdf["latitude"].max() - pdf["latitude"].min()
                lon_delta = pdf["longitude"].max() - pdf["longitude"].min()
                lat_multiple = ref_lat / lat_delta
                lon_multiple = ref_lon / lon_delta
                magnification = min(lat_multiple, lon_multiple)
                mapbox_zoom = ref_zoom + math.log(magnification, 2)

        # Now define the layout
        layout = {
            "margin": {"l": 0, "b": 0, "t": 0, "r": 0},
            "mapbox_style": mapbox_style,
            "mapbox_zoom": mapbox_zoom,
            "mapbox_center": mapbox_center,
        }
        fig.update_layout(layout)
        return fig