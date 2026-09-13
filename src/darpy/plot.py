"""Native, deterministic SVG charts with a small Matplotlib-style interface.

Only one rectangular Axes, finite numeric data, and linear scales are supported.
This is not a Matplotlib replacement. See ``docs/plotting-scope.md`` for the
supported signatures, native return types, rendering units, and parity roadmap.
"""

from __future__ import annotations

import math
import re
from bisect import bisect_right
from collections.abc import Iterable
from dataclasses import dataclass
from os import PathLike
from pathlib import Path
from typing import Literal, cast
from xml.etree.ElementTree import Element, SubElement, tostring

__all__ = ["Axes", "Figure", "Series", "subplots"]

_PALETTE = ("#2563eb", "#dc2626", "#059669", "#9333ea", "#ea580c", "#0891b2")
_COLORS = {"black", "white", "red", "green", "blue", "orange", "purple", "gray", "grey"}
_LEFT, _RIGHT, _TOP, _BOTTOM = 76, 28, 48, 64


def _number(value: object, name: str) -> float:
    if type(value) not in (int, float):
        raise TypeError(f"{name} must contain Python int or float values; bool is unsupported")
    try:
        result = float(cast(int | float, value))
    except OverflowError as exc:
        raise ValueError(f"{name} must fit a finite Python float") from exc
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def _values(values: Iterable[int | float], name: str) -> tuple[float, ...]:
    if isinstance(values, (str, bytes)):
        raise TypeError(f"{name} must be a one-dimensional numeric iterable")
    return tuple(_number(value, name) for value in values)


def _text(value: str, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if any(
        not (
            char in "\t\n\r"
            or 0x20 <= ord(char) <= 0xD7FF
            or 0xE000 <= ord(char) <= 0xFFFD
            or 0x10000 <= ord(char) <= 0x10FFFF
        )
        for char in value
    ):
        raise ValueError(f"{name} contains characters invalid in XML 1.0")
    return value


def _positive(value: object, name: str) -> float:
    result = _number(value, name)
    if result <= 0:
        raise ValueError(f"{name} must be positive")
    return result


def _broadcast(value: int | float | Iterable[int | float], count: int, name: str) -> tuple[float, ...]:
    values = (_number(value, name),) * count if isinstance(value, (int, float)) else _values(value, name)
    if len(values) != count:
        raise ValueError(f"{name} must be a scalar or have the same length as x")
    return values


def _limits(low: int | float, high: int | float) -> tuple[float, float]:
    lower, upper = _number(low, "lower limit"), _number(high, "upper limit")
    if lower >= upper:
        raise ValueError("limits must be strictly increasing; inverted axes are unsupported")
    return lower, upper


def _extent(values: Iterable[float]) -> tuple[float, float]:
    iterator = iter(values)
    first = next(iterator, None)
    if first is None:
        return 0.0, 1.0
    low = high = first
    for value in iterator:
        low, high = min(low, value), max(high, value)
    if low == high:
        padding = max(abs(low) * 0.05, 0.5)
        lower, upper = low - padding, high + padding
        # At the float boundary, expand only in the representable direction.
        low = lower if math.isfinite(lower) else low
        high = upper if math.isfinite(upper) else high
    return low, high


def _lerp(low: float, high: float, fraction: float) -> float:
    return low * (1 - fraction) + high * fraction


def _unit(value: float, limits: tuple[float, float]) -> float:
    low, high = limits
    scale = max(abs(low), abs(high))
    # Normalizing first avoids overflow for ranges such as [-1e308, 1e308].
    denominator = high / scale - low / scale
    if denominator == 0:
        raise ValueError("limits are too close to resolve with floating-point scaling")
    result = (value / scale - low / scale) / denominator
    if not math.isfinite(result):
        raise ValueError("data and limits have an unrepresentable floating-point dynamic range")
    return result


def _fmt(value: float) -> str:
    if not math.isfinite(value):
        raise ValueError("render geometry must be finite; choose less extreme data or limits")
    return format(0.0 if value == 0 else value, ".12g")


def _ticks(limits: tuple[float, float]) -> tuple[tuple[float, str], ...]:
    values = tuple(dict.fromkeys(_lerp(*limits, index / 4) for index in range(5)))
    labels = [format(value, ".17g") for value in values]
    for precision in (6, 9, 12):
        candidates = [format(value, f".{precision}g") for value in values]
        if len(set(candidates)) == len(values):
            labels = candidates
            break
    return tuple(zip(values, labels, strict=True))


def _node(parent: Element, tag: str, **attributes: str | float) -> Element:
    return SubElement(
        parent,
        tag,
        {key.replace("_", "-"): value if isinstance(value, str) else _fmt(value) for key, value in attributes.items()},
    )


def _label(parent: Element, text: str, x: float, y: float, **attributes: str) -> None:
    _node(parent, "text", x=x, y=y, **attributes).text = text


@dataclass(frozen=True, slots=True)
class Series:
    """Immutable native handle; data is copied to tuples of Python floats.

    ``x``/``y`` are points, or bar centers/heights. Bar ``width`` and ``bottom``
    have one value per bar. ``size`` is scatter marker area in square SVG pixels.
    Handles are inspectable but do not implement Matplotlib's Artist API.
    """

    kind: Literal["line", "scatter", "bar"]
    x: tuple[float, ...]
    y: tuple[float, ...]
    color: str
    label: str | None
    linewidth: float = 2.0
    size: float = 36.0
    width: tuple[float, ...] = ()
    bottom: tuple[float, ...] = ()
    edges: tuple[float, ...] = ()


class Axes:
    """An accumulating chart with numeric linear axes and fixed SVG layout."""

    def __init__(self) -> None:
        self._series: list[Series] = []
        self._title = self._xlabel = self._ylabel = ""
        self._xlim: tuple[float, float] | None = None
        self._ylim: tuple[float, float] | None = None
        self._legend = False

    @property
    def series(self) -> tuple[Series, ...]:
        return tuple(self._series)

    def _style(self, color: str | None, label: str | None) -> tuple[str, str | None]:
        color = _PALETTE[len(self._series) % len(_PALETTE)] if color is None else _text(color, "color")
        if color not in _COLORS and re.fullmatch(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})", color) is None:
            raise ValueError("color must be a supported named color or #RGB/#RRGGBB; CSS expressions are unsupported")
        return color, None if label is None else _text(label, "label")

    def plot(
        self,
        x: Iterable[int | float],
        y: Iterable[int | float] | None = None,
        *,
        color: str | None = None,
        label: str | None = None,
        linewidth: float = 2,
    ) -> list[Series]:
        """Append one line; ``plot(y)`` supplies integer x positions. Return [Series]."""
        xs = _values(x, "x")
        xs, ys = (tuple(float(index) for index in range(len(xs))), xs) if y is None else (xs, _values(y, "y"))
        if len(xs) != len(ys):
            raise ValueError("x and y must have equal lengths")
        color, label = self._style(color, label)
        series = Series("line", xs, ys, color, label, linewidth=_positive(linewidth, "linewidth"))
        self._series.append(series)
        return [series]

    def scatter(
        self,
        x: Iterable[int | float],
        y: Iterable[int | float],
        *,
        color: str | None = None,
        label: str | None = None,
        s: float = 36,
    ) -> Series:
        """Append circular markers; ``s`` is positive area in square SVG pixels."""
        xs, ys = _values(x, "x"), _values(y, "y")
        if len(xs) != len(ys):
            raise ValueError("x and y must have equal lengths")
        color, label = self._style(color, label)
        series = Series("scatter", xs, ys, color, label, size=_positive(s, "s"))
        self._series.append(series)
        return series

    def bar(
        self,
        x: Iterable[int | float],
        height: Iterable[int | float],
        *,
        width: int | float | Iterable[int | float] = 0.8,
        bottom: int | float | Iterable[int | float] = 0,
        color: str | None = None,
        label: str | None = None,
    ) -> Series:
        """Append centered vertical bars, including negative heights and custom baselines."""
        xs, ys = _values(x, "x"), _values(height, "height")
        if len(xs) != len(ys):
            raise ValueError("x and height must have equal lengths")
        if isinstance(width, (int, float)):
            _positive(width, "width")
        widths, bottoms = _broadcast(width, len(xs), "width"), _broadcast(bottom, len(xs), "bottom")
        for center, value, span, base in zip(xs, ys, widths, bottoms, strict=True):
            _positive(span, "width")
            left, right, top = center - span / 2, center + span / 2, base + value
            if not all(math.isfinite(edge) for edge in (left, right, top)) or left >= right:
                raise ValueError("bar edges must be finite and have a representable positive width")
            if value != 0 and top == base:
                raise ValueError("nonzero bar height is too small to represent relative to its bottom")
        color, label = self._style(color, label)
        series = Series("bar", xs, ys, color, label, width=widths, bottom=bottoms)
        self._series.append(series)
        return series

    def hist(
        self,
        values: Iterable[int | float],
        bins: int | Iterable[int | float] = 10,
        *,
        color: str | None = None,
        label: str | None = None,
    ) -> tuple[tuple[int, ...], tuple[float, ...], Series]:
        """Count samples in half-open bins, with the final right edge included.

        Return native ``(counts, edges, Series)``. Explicit edges discard samples
        outside their range. Empty integer-bin input spans [0, 1].
        """
        data = _values(values, "values")
        if type(bins) is int:
            if not 1 <= bins <= 10_000:
                raise ValueError("integer bins must be between 1 and 10000")
            low, high = min(data, default=0.0), max(data, default=1.0)
            if low == high:
                low, high = low - 0.5, high + 0.5
            edges = tuple(_lerp(low, high, index / bins) for index in range(bins + 1))
        else:
            edges = _values(cast(Iterable[int | float], bins), "bins")
        if len(edges) < 2 or any(left >= right for left, right in zip(edges, edges[1:])):
            raise ValueError("bin edges must be strictly increasing with at least two values")
        counts = [0] * (len(edges) - 1)
        for value in data:
            if edges[0] <= value <= edges[-1]:
                counts[min(bisect_right(edges, value) - 1, len(counts) - 1)] += 1
        centers = tuple(left / 2 + right / 2 for left, right in zip(edges, edges[1:]))
        widths = tuple(right - left for left, right in zip(edges, edges[1:]))
        for width in widths:
            _positive(width, "bin width")
        color, label = self._style(color, label)
        # Keep authoritative edges: a rounded center/width cannot reconstruct
        # every pair of finite edges, particularly adjacent large floats.
        series = Series(
            "bar",
            centers,
            tuple(float(count) for count in counts),
            color,
            label,
            width=widths,
            bottom=(0.0,) * len(counts),
            edges=edges,
        )
        self._series.append(series)
        return tuple(counts), edges, series

    def set_title(self, title: str) -> None:
        self._title = _text(title, "title")

    def set_xlabel(self, label: str) -> None:
        self._xlabel = _text(label, "xlabel")

    def set_ylabel(self, label: str) -> None:
        self._ylabel = _text(label, "ylabel")

    def set_xlim(self, left: int | float, right: int | float) -> tuple[float, float]:
        self._xlim = _limits(left, right)
        return self._xlim

    def set_ylim(self, bottom: int | float, top: int | float) -> tuple[float, float]:
        self._ylim = _limits(bottom, top)
        return self._ylim

    def set_xscale(self, scale: str) -> None:
        if scale != "linear":
            raise NotImplementedError("only linear x scales are supported")

    def set_yscale(self, scale: str) -> None:
        if scale != "linear":
            raise NotImplementedError("only linear y scales are supported")

    def legend(self) -> None:
        """Show labeled series in insertion order, in the upper right of the Axes."""
        self._legend = True

    def get_xlim(self) -> tuple[float, float]:
        return self._xlim or _extent(
            edge
            for series in self._series
            for index, x in enumerate(series.x)
            for edge in (
                series.edges[index : index + 2]
                if series.edges
                else ((x - series.width[index] / 2, x + series.width[index] / 2) if series.kind == "bar" else (x,))
            )
        )

    def get_ylim(self) -> tuple[float, float]:
        return self._ylim or _extent(
            edge
            for series in self._series
            for index, y in enumerate(series.y)
            for edge in ((series.bottom[index], series.bottom[index] + y) if series.kind == "bar" else (y,))
        )

    def _render(self, root: Element, width: int, height: int) -> None:
        xlim, ylim = self.get_xlim(), self.get_ylim()
        left, top = float(_LEFT), float(_TOP)
        right, bottom = float(width - _RIGHT), float(height - _BOTTOM)

        def tx(value: float) -> float:
            return left + _unit(value, xlim) * (right - left)

        def ty(value: float) -> float:
            return bottom - _unit(value, ylim) * (bottom - top)

        grid = _node(root, "g", stroke="#e2e8f0", stroke_width="1")
        tick_labels = _node(root, "g", fill="#475569", font_size="11")
        for value, label in _ticks(xlim):
            x = tx(value)
            _node(grid, "line", x1=x, x2=x, y1=top, y2=bottom)
            _label(tick_labels, label, x, bottom + 20, text_anchor="middle")
        for value, label in _ticks(ylim):
            y = ty(value)
            _node(grid, "line", x1=left, x2=right, y1=y, y2=y)
            _label(tick_labels, label, left - 10, y + 4, text_anchor="end")
        clip_id = f"darpy-clip-{width}-{height}"
        clip = _node(_node(root, "defs"), "clipPath", id=clip_id)
        _node(clip, "rect", x=left, y=top, width=right - left, height=bottom - top)
        data = _node(root, "g", clip_path=f"url(#{clip_id})", **{"class": "darpy-series"})
        for series in self._series:
            group = _node(data, "g", **{"class": series.kind, "aria-label": series.label or series.kind})
            if series.kind == "line":
                points = " ".join(f"{_fmt(tx(x))},{_fmt(ty(y))}" for x, y in zip(series.x, series.y, strict=True))
                _node(
                    group,
                    "polyline",
                    points=points,
                    fill="none",
                    stroke=series.color,
                    stroke_width=series.linewidth,
                    stroke_linejoin="round",
                    stroke_linecap="round",
                )
            elif series.kind == "scatter":
                for x, y in zip(series.x, series.y, strict=True):
                    _node(group, "circle", cx=tx(x), cy=ty(y), r=math.sqrt(series.size / math.pi), fill=series.color)
            else:
                for index, (x, y, span, base) in enumerate(
                    zip(series.x, series.y, series.width, series.bottom, strict=True)
                ):
                    start, end = series.edges[index : index + 2] if series.edges else (x - span / 2, x + span / 2)
                    x0, x1, y0, y1 = tx(start), tx(end), ty(base), ty(base + y)
                    _node(group, "rect", x=x0, y=min(y0, y1), width=x1 - x0, height=abs(y1 - y0), fill=series.color)
        _node(
            root,
            "rect",
            x=left,
            y=top,
            width=right - left,
            height=bottom - top,
            fill="none",
            stroke="#64748b",
            stroke_width="1",
        )
        labels = _node(root, "g", fill="#0f172a", text_anchor="middle")
        _label(labels, self._title, (left + right) / 2, 26.0, font_size="18", font_weight="600")
        _label(labels, self._xlabel, (left + right) / 2, float(height - 16), font_size="13")
        middle = (top + bottom) / 2
        _label(labels, self._ylabel, 18.0, middle, font_size="13", transform=f"rotate(-90 18 {_fmt(middle)})")
        if self._legend:
            entries = [series for series in self._series if series.label]
            legend = _node(root, "g", **{"class": "darpy-legend"})
            legend_width = min(
                right - left - 16, 44.0 + max((len(series.label or "") * 7 for series in entries), default=0)
            )
            legend_left = right - legend_width - 8
            if entries:
                _node(
                    legend,
                    "rect",
                    x=legend_left,
                    y=top + 8,
                    width=legend_width,
                    height=float(len(entries) * 20 + 8),
                    fill="white",
                    stroke="#e2e8f0",
                )
            for index, series in enumerate(entries):
                y = top + 24 + index * 20
                _node(
                    legend,
                    "line",
                    x1=legend_left + 8,
                    x2=legend_left + 28,
                    y1=y,
                    y2=y,
                    stroke=series.color,
                    stroke_width="3",
                )
                _label(legend, series.label or "", legend_left + 36, y + 4, fill="#0f172a", font_size="12")


class Figure:
    """One chart exported as standalone SVG; dimensions are integer SVG pixels."""

    def __init__(self, *, width: int = 640, height: int = 400) -> None:
        if type(width) is not int or type(height) is not int:
            raise TypeError("figure width and height must be Python integers")
        if not 240 <= width <= 10_000 or not 180 <= height <= 10_000:
            raise ValueError("figure width must be 240..10000 and height 180..10000 pixels")
        self._width, self._height = width, height
        self._axes: list[Axes] = []

    @property
    def axes(self) -> tuple[Axes, ...]:
        return tuple(self._axes)

    def add_subplot(self) -> Axes:
        if self._axes:
            raise NotImplementedError("only one Axes per Figure is currently supported")
        axes = Axes()
        self._axes.append(axes)
        return axes

    def to_svg(self) -> str:
        """Render escaped XML without timestamps, external assets, or third-party imports."""
        title = self._axes[0]._title if self._axes else ""
        root = Element(
            "svg",
            {
                "xmlns": "http://www.w3.org/2000/svg",
                "width": str(self._width),
                "height": str(self._height),
                "viewBox": f"0 0 {self._width} {self._height}",
                "role": "img",
                "aria-label": title or "DARPy chart",
                "font-family": "sans-serif",
            },
        )
        SubElement(root, "title").text = title or "DARPy chart"
        _node(root, "rect", width="100%", height="100%", fill="white")
        for axes in self._axes:
            axes._render(root, self._width, self._height)
        return '<?xml version="1.0" encoding="utf-8"?>\n' + tostring(root, encoding="unicode") + "\n"

    def savefig(self, path: str | PathLike[str]) -> None:
        """Write UTF-8 SVG to a .svg path. Other formats are explicitly unsupported."""
        target = Path(path)
        if target.suffix.lower() != ".svg":
            raise ValueError("only .svg export is supported; use to_svg() for an in-memory document")
        target.write_text(self.to_svg(), encoding="utf-8", newline="\n")


def subplots(*, width: int = 640, height: int = 400) -> tuple[Figure, Axes]:
    """Create one native Figure/Axes pair without global pyplot state."""
    figure = Figure(width=width, height=height)
    return figure, figure.add_subplot()
