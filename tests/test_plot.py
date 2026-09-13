"""Behavioral checks of native plot data, mathematical geometry, and safe SVG export."""

import math
from dataclasses import FrozenInstanceError
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from darpy.plot import Axes, Figure, subplots

NS = {"s": "http://www.w3.org/2000/svg"}


def test_line_and_scatter_transform_data_copy_and_svg_export(tmp_path: Path) -> None:
    figure, axes = subplots(width=400, height=300)
    x, y = [0, 10], [-5, 5]
    (line,) = axes.plot(x, y, color="#123456", label="trend")
    point = axes.scatter([5], [0], s=4 * math.pi, color="red")
    axes.set_xlim(0, 10)
    axes.set_ylim(-5, 5)
    x[0], y[1] = 999, 999
    assert line.x == (0.0, 10.0)
    assert line.y == (-5.0, 5.0)
    assert point.x == (5.0,)
    assert figure.axes == (axes,)
    assert axes.series == (line, point)
    with pytest.raises(FrozenInstanceError):
        line.color = "blue"

    rendered = figure.to_svg()
    assert rendered == figure.to_svg()
    root = ET.fromstring(rendered)
    polyline = root.find(".//s:polyline", NS)
    assert polyline is not None
    assert polyline.attrib == {
        "points": "76,236 372,48",
        "fill": "none",
        "stroke": "#123456",
        "stroke-width": "2",
        "stroke-linejoin": "round",
        "stroke-linecap": "round",
    }
    circle = root.find(".//s:circle", NS)
    assert circle is not None
    assert circle.attrib == {"cx": "224", "cy": "142", "r": "2", "fill": "red"}
    target = tmp_path / "chart.svg"
    figure.savefig(target)
    assert target.read_text(encoding="utf-8") == rendered


def test_bar_geometry_retains_negative_heights_zero_heights_and_baselines() -> None:
    figure, axes = subplots(width=400, height=300)
    bars = axes.bar([1, 2, 3], [2, -3, 0], width=1, bottom=1)
    assert axes.get_xlim() == (0.5, 3.5)
    assert axes.get_ylim() == (-2, 3)
    assert bars.width == (1, 1, 1)
    assert bars.bottom == (1, 1, 1)
    axes.set_xlim(0, 4)
    axes.set_ylim(-2, 3)
    root = ET.fromstring(figure.to_svg())
    rectangles = root.findall(".//s:g[@class='bar']/s:rect", NS)
    geometry = [{key: float(rect.attrib[key]) for key in ("x", "y", "width", "height")} for rect in rectangles]
    assert geometry == [
        {"x": 113, "y": 48, "width": 74, "height": 75.2},
        {"x": 187, "y": 123.2, "width": 74, "height": 112.8},
        {"x": 261, "y": 123.2, "width": 74, "height": 0},
    ]


def test_histogram_boundary_assignment_variable_bins_and_empty_or_constant_data() -> None:
    figure, axes = subplots()
    counts, edges, bars = axes.hist([-1, 0, 0.5, 1, 2, 4, 5], bins=[0, 1, 2, 4])
    assert counts == (2, 1, 2)
    assert edges == (0, 1, 2, 4)
    assert bars.x == (0.5, 1.5, 3)
    assert bars.y == counts
    assert bars.width == (1, 1, 2)
    assert axes.get_xlim() == (0, 4)
    assert axes.get_ylim() == (0, 2)
    root = ET.fromstring(figure.to_svg())
    rectangles = root.findall(".//s:g[@class='bar']/s:rect", NS)
    assert [float(rect.attrib["width"]) for rect in rectangles] == [134, 134, 268]
    assert Axes().hist([], bins=2)[:2] == ((0, 0), (0, 0.5, 1))
    assert Axes().hist([100, 100], bins=2)[:2] == ((0, 2), (99.5, 100, 100.5))


def test_adjacent_float_histogram_edges_remain_the_rendering_authority() -> None:
    figure, axes = subplots(width=400, height=300)
    low, high = 1.0, math.nextafter(1.0, math.inf)
    counts, edges, bars = axes.hist([low, high], bins=[low, high])
    assert counts == (2,) and edges == (low, high)
    assert bars.edges == edges
    assert axes.get_xlim() == edges
    axes.set_xlim(low, high)
    root = ET.fromstring(figure.to_svg())
    rectangle = root.find(".//s:g[@class='bar']/s:rect", NS)
    assert rectangle is not None
    assert rectangle.attrib == {"x": "76", "y": "48", "width": "296", "height": "188", "fill": "#2563eb"}


def test_xml_escaping_unicode_labels_legend_and_explicit_clipping() -> None:
    figure, axes = subplots(width=400, height=300)
    title = '<script>alert("chart")</script> & café 🌍'
    axes.set_title(title)
    axes.set_xlabel('x < y & "units"')
    axes.set_ylabel("測定値")
    axes.plot([-5, 15], [0, 0], label='<a href="evil">series</a>')
    axes.set_xlim(0, 10)
    axes.set_ylim(-5, 5)
    axes.legend()
    source = figure.to_svg()
    root = ET.fromstring(source)
    assert root.attrib["aria-label"] == title
    assert root.findtext("s:title", namespaces=NS) == title
    assert "<script>" not in source and "<a href=" not in source
    text = [element.text for element in root.findall(".//s:text", NS)]
    assert title in text and 'x < y & "units"' in text and "測定値" in text
    assert '<a href="evil">series</a>' in text
    clip = root.find(".//s:clipPath/s:rect", NS)
    assert clip is not None and clip.attrib == {"x": "76", "y": "48", "width": "296", "height": "188"}
    group = root.find(".//s:g[@class='darpy-series']", NS)
    assert group is not None and group.attrib["clip-path"] == "url(#darpy-clip-400-300)"
    line = root.find(".//s:polyline", NS)
    assert line is not None and line.attrib["points"] == "-72,142 520,142"


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        ([], (0, 1)),
        ([0], (-0.5, 0.5)),
        ([100], (95, 105)),
        ([-1e308, 1e308], (-1e308, 1e308)),
        ([5e-324, 1e-323], (5e-324, 1e-323)),
        ([math.nextafter(1.0, 0), 1.0], (math.nextafter(1.0, 0), 1.0)),
    ],
)
def test_autoscale_handles_empty_constant_and_extreme_finite_data(
    data: list[float], expected: tuple[float, float]
) -> None:
    figure, axes = subplots()
    axes.plot(data, data)
    assert axes.get_xlim() == expected
    assert axes.get_ylim() == expected
    root = ET.fromstring(figure.to_svg())
    line = root.find(".//s:polyline", NS)
    assert line is not None
    coordinates = [float(value) for pair in line.attrib["points"].split() for value in pair.split(",")]
    assert all(math.isfinite(value) for value in coordinates)


def test_implicit_x_positions_iterators_and_empty_figure() -> None:
    axes = Axes()
    (line,) = axes.plot(iter([3, 2, 1]))
    assert line.x == (0, 1, 2) and line.y == (3, 2, 1)
    assert ET.fromstring(Figure().to_svg()).attrib["viewBox"] == "0 0 640 400"
    axes.set_xscale("linear")
    axes.set_yscale("linear")


@pytest.mark.parametrize(
    "operation",
    [
        lambda ax: ax.plot([True]),
        lambda ax: ax.plot([float("nan")]),
        lambda ax: ax.scatter([1], [float("inf")]),
        lambda ax: ax.plot([10**1000]),
        lambda ax: ax.plot("123"),
        lambda ax: ax.plot([[1]]),
        lambda ax: ax.plot([1], [1, 2]),
        lambda ax: ax.scatter([], [1]),
        lambda ax: ax.bar([1], []),
        lambda ax: ax.plot([1], color='url("https://example.com")'),
        lambda ax: ax.scatter([1], [2], s=0),
        lambda ax: ax.plot([], linewidth=-1),
        lambda ax: ax.bar([], [], width=-1),
        lambda ax: ax.bar([0], [1], width=True),
        lambda ax: ax.bar([0], [1], width=[1, 2]),
        lambda ax: ax.bar([1e308], [1], width=0.8),
        lambda ax: ax.bar([0], [1e308], bottom=1e308),
        lambda ax: ax.bar([0], [1], bottom=1e20),
        lambda ax: ax.hist([1], bins=0),
        lambda ax: ax.hist([1], bins=True),
        lambda ax: ax.hist([1], bins=[0, 0, 2]),
        lambda ax: ax.hist([1], bins=[0]),
        lambda ax: ax.hist([1], bins=[0, float("inf")]),
        lambda ax: ax.set_title("bad\x00text"),
        lambda ax: ax.set_xlabel("bad\ud800text"),
        lambda ax: ax.set_xlim(1, 1),
        lambda ax: ax.set_ylim(2, 1),
        lambda ax: ax.set_xlim(0, float("inf")),
    ],
)
def test_invalid_inputs_fail_without_adding_partial_series(operation) -> None:
    axes = Axes()
    with pytest.raises((TypeError, ValueError)):
        operation(axes)
    assert axes.series == ()


def test_unsupported_scales_formats_layouts_and_unrepresentable_geometry(tmp_path: Path) -> None:
    figure, axes = subplots()
    with pytest.raises(NotImplementedError, match="linear"):
        axes.set_xscale("log")
    with pytest.raises(NotImplementedError, match="linear"):
        axes.set_yscale("symlog")
    with pytest.raises(NotImplementedError, match="one Axes"):
        figure.add_subplot()
    with pytest.raises(ValueError, match="svg"):
        figure.savefig(tmp_path / "chart.png")
    assert not (tmp_path / "chart.png").exists()
    with pytest.raises(TypeError):
        Figure(width=True)
    with pytest.raises(ValueError):
        Figure(height=1)
    axes.plot([1e308], [0])
    axes.set_xlim(0, 5e-324)
    with pytest.raises(ValueError, match="dynamic range"):
        figure.to_svg()


def test_supported_data_and_histogram_semantics_against_optional_matplotlib_reference() -> None:
    """Compare the supported numerical contract through Matplotlib's public Artist API.

    Native plotting needs no third-party imports. This reference check runs when
    the separately installed visualization extra is available; it does not
    assert identical rendering, Artist types, autoscaling, or marker size units.
    """
    reference = pytest.importorskip("matplotlib.figure", reason="optional Matplotlib parity reference")
    reference_axes = reference.Figure().add_subplot()
    axes = Axes()
    (line,) = axes.plot([3, 2, 1])
    (reference_line,) = reference_axes.plot([3, 2, 1])
    assert line.x == tuple(reference_line.get_xdata())
    assert line.y == tuple(reference_line.get_ydata())
    points = axes.scatter([0, 1, 2], [2, -1, 0])
    reference_points = reference_axes.scatter([0, 1, 2], [2, -1, 0])
    assert list(zip(points.x, points.y, strict=True)) == [tuple(point) for point in reference_points.get_offsets()]
    bars = axes.bar([1, 2], [2, -3], width=[0.5, 1.5], bottom=[0, 1])
    reference_bars = reference_axes.bar([1, 2], [2, -3], width=[0.5, 1.5], bottom=[0, 1])
    assert [
        (x - width / 2, base, width, height)
        for x, height, width, base in zip(bars.x, bars.y, bars.width, bars.bottom, strict=True)
    ] == [(patch.get_x(), patch.get_y(), patch.get_width(), patch.get_height()) for patch in reference_bars]
    for data, bins in [([-1, 0, 0.5, 1, 2, 4, 5], [0, 1, 2, 4]), ([100, 100], 2), ([], 2)]:
        counts, edges, _ = axes.hist(data, bins=bins)
        expected_counts, expected_edges, _ = reference_axes.hist(data, bins=bins)
        assert counts == tuple(expected_counts)
        assert edges == tuple(expected_edges)
