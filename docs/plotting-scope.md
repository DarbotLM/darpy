# Native plotting scope and Matplotlib parity target

DARPy includes a dependency-free SVG plotting foundation in `darpy.plot`.
It currently implements one numeric, linear, two-dimensional chart per figure.
It is **not a full Matplotlib replacement**. Feature, behavior, and functionality
parity with **Matplotlib 3.11.2** is the broader target, separate from DARPy's
Python 3.14 runtime baseline. Work toward that target must preserve explicit
capability declarations and reference tests instead of claiming unsupported APIs.

## Use the native renderer

```python
from darpy.plot import subplots

figure, axes = subplots(width=720, height=440)
axes.plot([1, 2, 3, 4], [4, 3, 2, 1], label="Training loss")
axes.scatter([1, 2, 3, 4], [4.3, 3.2, 2.4, 1.4], label="Validation loss")
axes.set_title("Experiment progress")
axes.set_xlabel("Iteration")
axes.set_ylabel("Loss")
axes.legend()
figure.savefig("progress.svg")
svg_text = figure.to_svg()
```

No Matplotlib, NumPy, GUI backend, font download, or network request is needed.
The SVG is a standalone UTF-8 document containing native SVG geometry and text.
Open it in an SVG-capable browser or editor. Rendering uses the viewer's local
`sans-serif` font, so text appearance can vary between viewers.

## Implemented API and behavior

| API | Current native contract |
| --- | --- |
| `subplots(width=640, height=400)` | Return one `(Figure, Axes)` pair; no global pyplot state. |
| `Figure(width=640, height=400)` | Construct a blank figure. Width is 240–10000 and height 180–10000 integer SVG pixels. |
| `Figure.add_subplot()` | Add the sole Axes; a second call raises `NotImplementedError`. |
| `figure.axes`, `axes.series` | Read-only tuples of the contained objects/immutable series handles. |
| `axes.plot(x, y, color=None, label=None, linewidth=2)` | One connected line; keyword-only style arguments. Return a one-element `list[Series]`. |
| `axes.plot(y, ...)` | Use integer x positions starting at zero. |
| `axes.scatter(x, y, color=None, label=None, s=36)` | Circular markers; `s` is a positive area in **square SVG pixels**. Return `Series`. |
| `axes.bar(x, height, width=0.8, bottom=0, color=None, label=None)` | Centered vertical bars; widths/baselines are scalars or equal-length numeric iterables. Widths are positive; heights can be negative or zero. Return `Series`. |
| `axes.hist(values, bins=10, color=None, label=None)` | One unweighted count histogram; integer bins or explicit increasing edges. Return `(tuple[int, ...], tuple[float, ...], Series)`. |
| `set_title(text)`, `set_xlabel(text)`, `set_ylabel(text)` | Literal Unicode labels, safely XML-escaped. Return `None`. |
| `set_xlim(left, right)`, `set_ylim(bottom, top)` | Finite, strictly increasing numeric limits; return the accepted pair. Series are clipped to the Axes rectangle. |
| `get_xlim()`, `get_ylim()` | Return explicit limits or calculated data extents. |
| `set_xscale("linear")`, `set_yscale("linear")` | Linear is the only supported scale; other values raise `NotImplementedError`. |
| `axes.legend()` | Enable a fixed upper-right legend for nonempty labels in insertion order. Return `None`. |
| `figure.to_svg()` | Return deterministic SVG text for unchanged figure contents. |
| `figure.savefig(path)` | Write `.svg` only, explicitly UTF-8; reject other suffixes before writing. Return `None`. |

`Series` is DARPy's frozen dataclass containing copied tuples `x`, `y`, a `kind`,
`color`, and `label`, plus style information. Bar handles additionally contain
per-bar `width` and `bottom` tuples. Histogram handles preserve an additional
`edges` tuple as the authority for bounds and rendering, so rounded centers do
not shift narrow bins. Changing original input lists after a plot
call cannot change a chart. Updating a returned handle is unsupported.

These are **native return types**, not Matplotlib `Line2D`, `PathCollection`,
`BarContainer`, `Text`, or other Artist objects. Familiar method names cover only
the documented signatures. Unlisted keyword arguments and format strings are
not accepted. Native width/height/line width use SVG pixels; Matplotlib figures
use inches and DPI, and its scatter size is expressed in square typographic
points. The two renderers therefore do not promise identical visual output.

## Numerical and rendering contract

- Input is a finite, one-dimensional iterable of Python `int`/`float` values,
  copied and converted to finite Python floats. Booleans, nested arrays,
  strings, NaN, infinities, and integers too large for float conversion are
  rejected. Integer precision beyond the float mantissa is not retained.
- Line/scatter coordinates and bar centers/heights must have matching lengths.
  Empty series are valid. Invalid additions do not append partial series.
- Automatic limits use the combined data extents without a percentage margin.
  Bars include their horizontal edges and vertical baselines. An empty axis
  spans `[0, 1]`. Constant data expands by the greater of 5% of its magnitude
  and 0.5; at the largest finite float it expands in the representable direction.
- Tick marks are deterministic, with up to five equally spaced representable
  values. This is not Matplotlib's tick locator or autoscaling algorithm.
- Explicit limits clip visible series geometry without modifying stored data.
  Coordinates outside the limits remain mathematically transformed before
  SVG clipping; points are not individually clamped onto the boundary.
- Linear transforms normalize extreme ranges to avoid simple subtraction
  overflow. Unrepresentable transformed geometry, collapsed positive bar
  widths or nonzero heights, or bin edges that cannot remain distinct raise `ValueError` rather
  than producing NaN/Infinity in SVG. Native finite floats do not imply support
  for every possible ratio between a datum and manually selected limits.
- Histogram bins are half-open except for the last bin, which includes its
  right edge. Explicit edges discard samples outside the supplied range.
  Integer bins use equal-width edges between the minimum and maximum sample;
  a constant sample range expands by 0.5 on each side. Empty integer-bin input
  spans `[0, 1]`. Integer bin counts are limited to 1–10000. Automatically
  named bin estimators, weights, density, stacking, and cumulative histograms
  are not implemented.
- Colors are `#RGB`, `#RRGGBB`, or one of `black`, `white`, `red`, `green`,
  `blue`, `orange`, `purple`, `gray`, `grey`. A deterministic native palette
  supplies omitted colors. CSS expressions, external URLs, and raw SVG markup
  are rejected. Labels remain literal text; XML 1.0 control/surrogate characters
  are rejected. There are no scripts or external image/font references.
- Layout uses fixed margins and an optional legend. Text wrapping, font
  measurement, collision avoidance, tight/constrained layout, and automatic
  legend placement are not implemented. Long labels or numerous legend entries
  can overlap or exceed the figure; callers should use concise labels and a
  suitable figure size. SVG coordinates serialize to 12 significant digits.

## Cost and resource ownership

For a fixed number of ticks, constructing and rendering line/scatter/bar data
uses time and storage proportional to the number of points. Histogram counting
uses binary search over bin edges: `O(n log b)` time and `O(n + b)` storage.
Output size is proportional to generated geometry plus label text. There are
no performance benchmark claims against Matplotlib.

Callers own iterable termination and input size. This API deliberately does not
impose a point/series/text budget, run an untrusted-input sandbox, or silently
sample data. A very large or infinite iterable can exhaust resources. Hosts
accepting remote plotting requests must enforce their own bounded schema and
execution budget before invoking native plotting.

## Current capability matrix and parity roadmap

| Capability | Native now | Matplotlib 3.11.2 parity work |
| --- | --- | --- |
| Figure/Axes interface | One Axes, fixed dimensions, explicit state | Subplot grids, sharing, secondary/inset axes, constrained layouts, complete signatures. |
| Line/scatter/bar/histogram | Documented numeric subset above | Full formatting, marker/cycler rules, collection/container behavior, weighted/density/multiple histograms. |
| Scales and units | Increasing linear numeric axes | Log/symlog/logit and custom scales, inverse axes, dates, units and categorical converters. |
| Text and decorations | Literal text, basic ticks/grid, fixed legend | Locators/formatters, full legends, annotations, math text, font/layout compatibility. |
| Other plot families | Unsupported | Error bars, areas/steps, distributions, images, contours, meshes, vectors, polar and 3D plots. |
| Artist model | Native immutable Series only | Artist hierarchy, transforms, properties, events, callbacks and object lifetime behavior. |
| Rendering/export | Deterministic standalone SVG | Raster rendering, PNG/PDF and remaining formats, DPI/font handling, clipping and visual fidelity. |
| Interactive environments | Export only | Notebook representations, GUI backends, pan/zoom/picking, animations and event integration. |
| Ecosystem compatibility | Explicit module imports; no Matplotlib alias | Optional adapters for existing Matplotlib objects and a measured migration path. |

The optional `visualization` extra includes Matplotlib for existing ecosystem
workflows and reference testing. That dependency remains separate from
`darpy.plot`; installing it does not turn native plotting into full parity.
Interoperability work must support explicit, documented conversion/adapters
without installing a misleading `matplotlib` shadow package or silently
forwarding unsupported native calls. Retained external functionality must remain
identifiable in capability reports until replacement is verified.

Parity acceptance should progress by capability group with public-API reference
tests pinned to a declared Matplotlib version, numerical tolerances where
appropriate, output-format validation, and rendered visual comparisons.
Current tests check copied data, exact mapped coordinates, negative/zero bar
geometry, histogram boundary assignments, empty/constant/extreme data, escaping,
clipping, deterministic exports, and explicit rejection paths. An optional
Matplotlib reference test compares supported line/scatter data, bar geometry,
and explicit/constant/empty histogram counts and edges. It does not establish
complete Matplotlib or pixel-level rendering parity.

## Primary references

- [Matplotlib 3.11.2 distribution](https://pypi.org/project/matplotlib/3.11.2/)
- [Matplotlib Axes.plot](https://matplotlib.org/stable/api/_as_gen/matplotlib.axes.Axes.plot.html)
- [Matplotlib Axes.bar](https://matplotlib.org/stable/api/_as_gen/matplotlib.axes.Axes.bar.html)
- [Matplotlib Axes.hist](https://matplotlib.org/stable/api/_as_gen/matplotlib.axes.Axes.hist.html)

Reference semantics were reviewed on 2026-09-13; these links describe the full
upstream API, not a claim that DARPy implements it all.
