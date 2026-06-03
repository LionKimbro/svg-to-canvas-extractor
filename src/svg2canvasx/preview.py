import json
from pathlib import Path
import tkinter
import tkinter.font

from .flow import create_toplevel_for_flow
from .flow import load_flow_file
from .flow import flow_to_preview_data


kDEFAULT_WIDTH = 1100
kDEFAULT_HEIGHT = 900
kBBOX_OUTLINE = "#66a3ff"
kID_FILL = "#444444"
kANNOTATION_OUTLINE = "#1a8f8f"
kANNOTATION_FILL = ""


def preview_json_file(path, width=None, height=None, scale=1.0, font_scale=0.75, show_bboxes=False, show_ids=False, show_annotations=False):
    input_path = Path(path)
    data = json.loads(input_path.read_text(encoding="utf-8"))
    if data.get("format") == "svg2canvasx-flow":
        if show_annotations:
            data = flow_to_preview_data(data)
        else:
            return preview_flow_data(
                data,
                title="svg2canvasx preview - " + input_path.name,
                width=width,
                height=height,
            )
    preview_data(
        data,
        title="svg2canvasx preview - " + input_path.name,
        width=width,
        height=height,
        scale=scale,
        font_scale=font_scale,
        show_bboxes=show_bboxes,
        show_ids=show_ids,
        show_annotations=show_annotations,
    )


def preview_flow_file(path, title=None, width=None, height=None):
    input_path = Path(path)
    data = load_flow_file(path)
    return preview_flow_data(
        data,
        title=title or ("svg2canvasx preview - " + input_path.name),
        width=width,
        height=height,
    )


def preview_flow_data(data, title, width=None, height=None):
    root = tkinter.Tk()
    root.title(title)
    created = create_toplevel_for_flow(root, data)
    toplevel = created["toplevel"]
    canvas = created["canvas"]
    toplevel.title(title)
    canvas_width = width or _safe_int((data.get("canvas") or {}).get("width"))
    canvas_height = height or _safe_int((data.get("canvas") or {}).get("height"))
    if canvas_width:
        canvas.configure(width=canvas_width)
    if canvas_height:
        canvas.configure(height=canvas_height)
    root.withdraw()
    configure_preview_close_behavior(root, toplevel)
    root.mainloop()
    return created


def preview_data(data, title, width=None, height=None, scale=1.0, font_scale=0.75, show_bboxes=False, show_ids=False, show_annotations=False):
    svg_info = data.get("svg", {})
    canvas_width = width or _safe_int(svg_info.get("width")) or kDEFAULT_WIDTH
    canvas_height = height or _safe_int(svg_info.get("height")) or kDEFAULT_HEIGHT
    world_width = sx(canvas_width, scale)
    world_height = sx(canvas_height, scale)

    root = tkinter.Tk()
    root.title(title)

    frame = tkinter.Frame(root)
    frame.pack(fill="both", expand=True)

    canvas = tkinter.Canvas(
        frame,
        width=canvas_width,
        height=canvas_height,
        background="white",
        scrollregion=(0, 0, world_width, world_height),
    )
    x_scroll = tkinter.Scrollbar(frame, orient="horizontal", command=canvas.xview)
    y_scroll = tkinter.Scrollbar(frame, orient="vertical", command=canvas.yview)
    canvas.configure(xscrollcommand=x_scroll.set, yscrollcommand=y_scroll.set)

    y_scroll.pack(side="right", fill="y")
    x_scroll.pack(side="bottom", fill="x")
    canvas.pack(side="left", fill="both", expand=True)

    options = {
        "font_scale": font_scale,
        "show_bboxes": show_bboxes,
        "show_ids": show_ids,
    }
    render_objects(canvas, data.get("objects", []), scale, options)
    if show_annotations:
        render_annotations(canvas, data.get("annotations", []), scale, options)

    configure_preview_close_behavior(root, root)
    root.mainloop()


def render_objects(canvas, objects, scale, options):
    for obj in objects:
        render_single_object(canvas, obj, scale, options, annotation_mode=False)


def render_annotations(canvas, annotations, scale, options):
    for obj in annotations:
        render_single_object(canvas, obj, scale, options, annotation_mode=True)


def render_single_object(canvas, obj, scale, options, annotation_mode=False):
    kind = obj.get("kind")
    try:
        render_target = annotation_style_object(obj) if annotation_mode else obj
        if kind == "rect":
            render_rect(canvas, render_target, scale, options)
        elif kind in ("line", "polyline", "polygon", "path"):
            render_pathlike(canvas, render_target, scale, options)
        elif kind in ("circle", "ellipse"):
            render_ellipse(canvas, render_target, scale, options)
        elif kind == "text":
            render_text(canvas, render_target, scale, options)
        else:
            print("Skipping unsupported object kind: " + str(kind))
            return

        if options.get("show_bboxes"):
            render_bbox(canvas, render_target, scale)
        if options.get("show_ids"):
            if annotation_mode:
                render_annotation_id(canvas, obj, scale)
            else:
                render_id(canvas, obj, scale)
    except Exception as exc:
        print("Preview warning for {kind} {name}: {exc}".format(
            kind=kind,
            name=obj.get("svg_id") or obj.get("uid"),
            exc=exc,
        ))


def sx(value, scale):
    if value is None:
        return None
    return float(value) * float(scale)


def scale_points(points, scale):
    return [[sx(point[0], scale), sx(point[1], scale)] for point in (points or [])]


def style_fill(style):
    value = (style or {}).get("fill")
    if not value or value == "none":
        return ""
    return value


def style_stroke(style):
    value = (style or {}).get("stroke")
    if not value or value == "none":
        return ""
    return value


def style_width(style, scale):
    value = (style or {}).get("stroke_width")
    if value is None:
        return max(1.0, scale)
    return max(1.0, sx(value, scale))


def style_dash(style, scale):
    values = (style or {}).get("stroke_dasharray_values")
    if not values:
        return None
    output = []
    for value in values:
        scaled = max(1, int(round(sx(value, scale))))
        output.append(scaled)
    return tuple(output) or None


def make_tk_font(style, scale, font_scale=0.75):
    style = style or {}
    family = style.get("font_family") or "Arial"
    size = style.get("font_size") or 12.0
    weight = style.get("font_weight")
    font_style = style.get("font_style")
    parts = [family, max(1, int(round(float(size) * float(scale) * float(font_scale))))]
    modifiers = []
    if is_bold_value(weight):
        modifiers.append("bold")
    if is_italic_value(font_style):
        modifiers.append("italic")
    if modifiers:
        parts.append(" ".join(modifiers))
    return tuple(parts)


def render_rect(canvas, obj, scale, options):
    world = obj.get("world", {})
    style = obj.get("style", {})
    bbox = world.get("bbox")
    points = world.get("points")
    if _is_axis_aligned_rect(obj):
        x0_value, y0_value, x1_value, y1_value = _scale_bbox(bbox, scale)
        canvas.create_rectangle(
            x0_value,
            y0_value,
            x1_value,
            y1_value,
            fill=style_fill(style),
            outline=style_stroke(style),
            width=style_width(style, scale),
            dash=style_dash(style, scale),
        )
        return
    if points:
        flat_points = flatten_points(scale_points(points, scale))
        canvas.create_polygon(
            flat_points,
            fill=style_fill(style),
            outline=style_stroke(style),
            width=style_width(style, scale),
            dash=style_dash(style, scale),
        )
        return
    print("Preview warning: rect missing world geometry: " + str(obj.get("svg_id") or obj.get("uid")))


def render_pathlike(canvas, obj, scale, options):
    world = obj.get("world", {})
    style = obj.get("style", {})
    if obj.get("kind") == "path" and style_fill(style) and not style_stroke(style):
        print("Preview warning: skipping fill-only path: " + str(obj.get("svg_id") or obj.get("uid")))
        return
    points = world.get("points")
    if not points:
        print("Preview warning: path-like object missing world points: " + str(obj.get("svg_id") or obj.get("uid")))
        return
    scaled_points = scale_points(points, scale)
    if obj.get("kind") == "polygon" and scaled_points and scaled_points[0] != scaled_points[-1]:
        scaled_points.append([scaled_points[0][0], scaled_points[0][1]])
    canvas.create_line(
        flatten_points(scaled_points),
        fill=style_stroke(style),
        width=style_width(style, scale),
        dash=style_dash(style, scale),
        smooth=False,
    )


def render_text(canvas, obj, scale, options):
    world = obj.get("world", {})
    style = obj.get("style", {})
    anchor_point = world.get("anchor_point") or [0.0, 0.0]
    anchor_name = obj.get("text_layout", {}).get("suggested_tk_anchor", "sw")
    font_spec = make_tk_font(style, scale, options.get("font_scale", 0.75))
    font_metrics = get_tk_font_metrics(canvas, font_spec)
    x_value, y_value = adjusted_text_position(
        anchor_point,
        scale,
        anchor_name,
        font_metrics,
    )
    fill = style_fill(style) or style_stroke(style) or "black"
    canvas.create_text(
        x_value,
        y_value,
        text=obj.get("text", ""),
        anchor=anchor_name,
        angle=tk_text_angle(world.get("angle_degrees", 0.0)),
        font=font_spec,
        fill=fill,
    )


def render_ellipse(canvas, obj, scale, options):
    world = obj.get("world", {})
    style = obj.get("style", {})
    bbox = world.get("bbox")
    if not bbox:
        print("Preview warning: ellipse missing world bbox: " + str(obj.get("svg_id") or obj.get("uid")))
        return
    x0_value, y0_value, x1_value, y1_value = _scale_bbox(bbox, scale)
    canvas.create_oval(
        x0_value,
        y0_value,
        x1_value,
        y1_value,
        fill=style_fill(style),
        outline=style_stroke(style),
        width=style_width(style, scale),
        dash=style_dash(style, scale),
    )


def render_bbox(canvas, obj, scale):
    bbox = (obj.get("world") or {}).get("bbox")
    if not bbox:
        return
    x0_value, y0_value, x1_value, y1_value = _scale_bbox(bbox, scale)
    canvas.create_rectangle(
        x0_value,
        y0_value,
        x1_value,
        y1_value,
        outline=kBBOX_OUTLINE,
        width=1,
        dash=(2, 2),
    )


def render_id(canvas, obj, scale):
    label = obj.get("svg_id") or obj.get("uid")
    if not label:
        return
    world = obj.get("world") or {}
    anchor_point = world.get("anchor_point")
    bbox = world.get("bbox")
    if anchor_point:
        x_value = sx(anchor_point[0], scale)
        y_value = sx(anchor_point[1], scale)
    elif bbox:
        x_value = sx(bbox[0], scale)
        y_value = sx(bbox[1], scale) - 10
    else:
        return
    canvas.create_text(
        x_value,
        y_value,
        text=label,
        anchor="sw",
        fill=kID_FILL,
        font=("Arial", max(8, int(round(10 * scale)))),
    )


def render_annotation_id(canvas, obj, scale):
    label = annotation_display_label(obj)
    if not label:
        return
    world = obj.get("world") or {}
    bbox = world.get("bbox")
    anchor_point = world.get("anchor_point")
    if anchor_point:
        x_value = sx(anchor_point[0], scale)
        y_value = sx(anchor_point[1], scale)
    elif bbox:
        x_value = sx(bbox[0], scale)
        y_value = sx(bbox[1], scale) - 10
    else:
        return
    canvas.create_text(
        x_value,
        y_value,
        text=label,
        anchor="sw",
        fill=kANNOTATION_OUTLINE,
        font=("Arial", max(8, int(round(10 * scale)))),
    )


def annotation_display_label(obj):
    annotation = obj.get("annotation") or {}
    return annotation.get("name") or annotation.get("raw_label") or obj.get("svg_id") or obj.get("uid")


def flatten_points(points):
    output = []
    for point in points:
        output.extend(point)
    return output


def is_bold_value(value):
    if value is None:
        return False
    text = str(value).strip().lower()
    if text == "bold":
        return True
    try:
        return float(text) >= 700.0
    except ValueError:
        return False


def is_italic_value(value):
    if value is None:
        return False
    text = str(value).strip().lower()
    return text in ("italic", "oblique")


def tk_text_angle(angle):
    if angle is None:
        return 0.0
    return -float(angle)


def adjusted_text_position(anchor_point, scale, anchor_name, font_metrics):
    x_value = sx(anchor_point[0], scale)
    y_value = sx(anchor_point[1], scale)
    return [x_value, y_value + baseline_offset(anchor_name, font_metrics)]


def baseline_offset(anchor_name, font_metrics):
    if anchor_name not in ("sw", "s", "se"):
        return 0.0
    return float((font_metrics or {}).get("descent") or 0.0)


def get_tk_font_metrics(widget, font_spec):
    font_obj = tkinter.font.Font(root=widget, font=font_spec)
    return {
        "ascent": int(font_obj.metrics("ascent")),
        "descent": int(font_obj.metrics("descent")),
        "linespace": int(font_obj.metrics("linespace")),
    }


def configure_preview_close_behavior(root, window):
    def handle_close():
        safe_destroy(window)
        if window is not root:
            safe_destroy(root)

    window.protocol("WM_DELETE_WINDOW", handle_close)
    return handle_close


def safe_destroy(widget):
    try:
        if int(widget.winfo_exists()):
            widget.destroy()
    except Exception:
        pass


def _is_axis_aligned_rect(obj):
    world = obj.get("world", {})
    points = world.get("points")
    matrix = world.get("matrix") or []
    if not points or len(points) != 4 or len(matrix) != 6:
        return bool(world.get("bbox"))
    a_value, b_value, c_value, d_value = matrix[0], matrix[1], matrix[2], matrix[3]
    return abs(b_value) < 1e-6 and abs(c_value) < 1e-6


def _scale_bbox(bbox, scale):
    if not bbox:
        return [0.0, 0.0, 0.0, 0.0]
    return [sx(bbox[0], scale), sx(bbox[1], scale), sx(bbox[2], scale), sx(bbox[3], scale)]


def _safe_int(value):
    if value is None:
        return None
    try:
        return int(round(float(value)))
    except Exception:
        return None


def annotation_style_object(obj):
    clone = dict(obj)
    style = dict(obj.get("style") or {})
    style["fill"] = kANNOTATION_FILL
    style["stroke"] = kANNOTATION_OUTLINE
    style["stroke_width"] = style.get("stroke_width") or 1.0
    if not style.get("stroke_dasharray_values"):
        style["stroke_dasharray_values"] = [4.0, 2.0]
    clone["style"] = style
    return clone
