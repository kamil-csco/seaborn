from __future__ import annotations
from dataclasses import dataclass
from typing import ClassVar

import numpy as np
import matplotlib as mpl

from seaborn._marks.base import (
    Mark,
    Mappable,
    MappableFloat,
    MappableString,
    MappableColor,
    resolve_properties,
    resolve_color,
)
from seaborn.external.version import Version


@dataclass
class Path(Mark):
    """
    A mark connecting data points in the order they appear.
    """
    color: MappableColor = Mappable("C0")
    alpha: MappableFloat = Mappable(1)
    linewidth: MappableFloat = Mappable(rc="lines.linewidth")
    linestyle: MappableString = Mappable(rc="lines.linestyle")
    marker: MappableString = Mappable(rc="lines.marker")
    pointsize: MappableFloat = Mappable(rc="lines.markersize")
    fillcolor: MappableColor = Mappable(depend="color")
    edgecolor: MappableColor = Mappable(depend="color")
    edgewidth: MappableFloat = Mappable(rc="lines.markeredgewidth")

    _sort: ClassVar[bool] = False

    def _plot(self, split_gen, scales, orient):

        for keys, data, ax in split_gen(keep_na=not self._sort):

            vals = resolve_properties(self, keys, scales)
            vals["color"] = resolve_color(self, keys, scales=scales)
            vals["fillcolor"] = resolve_color(self, keys, prefix="fill", scales=scales)
            vals["edgecolor"] = resolve_color(self, keys, prefix="edge", scales=scales)

            # https://github.com/matplotlib/matplotlib/pull/16692
            if Version(mpl.__version__) < Version("3.3.0"):
                vals["marker"] = vals["marker"]._marker

            if self._sort:
                data = data.sort_values(orient)

            artist_kws = self.artist_kws.copy()
            self._handle_capstyle(artist_kws, vals)

            line = mpl.lines.Line2D(
                data["x"].to_numpy(),
                data["y"].to_numpy(),
                color=vals["color"],
                linewidth=vals["linewidth"],
                linestyle=vals["linestyle"],
                marker=vals["marker"],
                markersize=vals["pointsize"],
                markerfacecolor=vals["fillcolor"],
                markeredgecolor=vals["edgecolor"],
                markeredgewidth=vals["edgewidth"],
                **artist_kws,
            )
            ax.add_line(line)

    def _legend_artist(self, variables, value, scales):

        keys = {v: value for v in variables}
        vals = resolve_properties(self, keys, scales)
        vals["color"] = resolve_color(self, keys, scales=scales)
        vals["fillcolor"] = resolve_color(self, keys, prefix="fill", scales=scales)
        vals["edgecolor"] = resolve_color(self, keys, prefix="edge", scales=scales)

        # https://github.com/matplotlib/matplotlib/pull/16692
        if Version(mpl.__version__) < Version("3.3.0"):
            vals["marker"] = vals["marker"]._marker

        artist_kws = self.artist_kws.copy()
        self._handle_capstyle(artist_kws, vals)

        return mpl.lines.Line2D(
            [], [],
            color=vals["color"],
            linewidth=vals["linewidth"],
            linestyle=vals["linestyle"],
            marker=vals["marker"],
            markersize=vals["pointsize"],
            markerfacecolor=vals["fillcolor"],
            markeredgecolor=vals["edgecolor"],
            markeredgewidth=vals["edgewidth"],
            **artist_kws,
        )

    def _handle_capstyle(self, kws, vals):

        # Work around for this matplotlib issue:
        # https://github.com/matplotlib/matplotlib/issues/23437
        if vals["linestyle"][1] is None:
            capstyle = kws.get("solid_capstyle", mpl.rcParams["lines.solid_capstyle"])
            kws["dash_capstyle"] = capstyle


@dataclass
class Line(Path):
    """
    A mark connecting data points with sorting along the orientation axis.
    """
    _sort: ClassVar[bool] = True


@dataclass
class Paths(Mark):
    """
    A faster but less-flexible mark for drawing many paths.
    """
    color: MappableColor = Mappable("C0")
    alpha: MappableFloat = Mappable(1)
    linewidth: MappableFloat = Mappable(rc="lines.linewidth")
    linestyle: MappableString = Mappable(rc="lines.linestyle")

    _sort: ClassVar[bool] = False

    def __post_init__(self):

        # LineCollection artists have a capstyle property but don't source its value
        # from the rc, so we do that manually here. Unfortunately, because we add
        # only one LineCollection, we have the use the same capstyle for all lines
        # even when they are dashed. It's a slight inconsistency, but looks fine IMO.
        self.artist_kws.setdefault("capstyle", mpl.rcParams["lines.solid_capstyle"])

    def _setup_lines(self, split_gen, scales, orient):

        line_data = {}

        for keys, data, ax in split_gen(keep_na=not self._sort):

            if ax not in line_data:
                line_data[ax] = {
                    "segments": [],
                    "colors": [],
                    "linewidths": [],
                    "linestyles": [],
                }

            vals = resolve_properties(self, keys, scales)
            vals["color"] = resolve_color(self, keys, scales=scales)

            if self._sort:
                data = data.sort_values(orient)

            # Column stack to avoid block consolidation
            xy = np.column_stack([data["x"], data["y"]])
            line_data[ax]["segments"].append(xy)
            line_data[ax]["colors"].append(vals["color"])
            line_data[ax]["linewidths"].append(vals["linewidth"])
            line_data[ax]["linestyles"].append(vals["linestyle"])

        return line_data

    def _plot(self, split_gen, scales, orient):

        line_data = self._setup_lines(split_gen, scales, orient)

        for ax, ax_data in line_data.items():
            lines = mpl.collections.LineCollection(**ax_data, **self.artist_kws)
            # Handle datalim update manually
            # https://github.com/matplotlib/matplotlib/issues/23129
            ax.add_collection(lines, autolim=False)
            xy = np.concatenate(ax_data["segments"])
            ax.update_datalim(xy)

    def _legend_artist(self, variables, value, scales):

        key = resolve_properties(self, {v: value for v in variables}, scales)

        artist_kws = self.artist_kws.copy()
        capstyle = artist_kws.pop("capstyle")
        artist_kws["solid_capstyle"] = capstyle
        artist_kws["dash_capstyle"] = capstyle

        return mpl.lines.Line2D(
            [], [],
            color=key["color"],
            linewidth=key["linewidth"],
            linestyle=key["linestyle"],
            **artist_kws,
        )


@dataclass
class Lines(Paths):
    """
    A faster but less-flexible mark for drawing many lines.
    """
    _sort: ClassVar[bool] = True


@dataclass
class Range(Paths):
    """
    An oriented line mark drawn between min/max values.
    """
    def _setup_lines(self, split_gen, scales, orient):

        line_data = {}

        other = {"x": "y", "y": "x"}[orient]

        for keys, data, ax in split_gen(keep_na=not self._sort):

            if ax not in line_data:
                line_data[ax] = {
                    "segments": [],
                    "colors": [],
                    "linewidths": [],
                    "linestyles": [],
                }

            vals = resolve_properties(self, keys, scales)
            vals["color"] = resolve_color(self, keys, scales=scales)

            cols = [orient, f"{other}min", f"{other}max"]
            data = data[cols].melt(orient, value_name=other)[["x", "y"]]
            segments = [d.to_numpy() for _, d in data.groupby(orient)]

            line_data[ax]["segments"].extend(segments)

            n = len(segments)
            line_data[ax]["colors"].extend([vals["color"]] * n)
            line_data[ax]["linewidths"].extend([vals["linewidth"]] * n)
            line_data[ax]["linestyles"].extend([vals["linestyle"]] * n)

        return line_data
