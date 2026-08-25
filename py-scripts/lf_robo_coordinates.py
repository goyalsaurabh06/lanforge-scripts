"""
Renders robot-id markers onto the testhouse automation Web-GUI's floor-plan
images.

Reusable across scripts: any script that has a `robo_coordinates_json` blob
(see `add_robo_coordinates_to_image` docstring for the expected shape) can
import this module and call `add_robo_coordinates_to_image(...)` directly -
it does not depend on any test script's class/state.

Example:
    from lf_robo_coordinates import add_robo_coordinates_to_image

    rendered = add_robo_coordinates_to_image(robo_coordinates_json, output_dir)
    # rendered == [(floor_id, "/path/to/robo_coordinates_floor_f1.png"), ...]
"""
import ast
import json
import logging
import os

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

# Background floor-plan images used by the testhouse automation Web-GUI.
ROBO_COORDINATES_IMAGE_ASSETS_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../local/interop-webGUI/resources/static/resources/assets/images/"))

# Visual spec mirrors the Web-GUI's `.coordinate` marker CSS:
#   width/height: 40px, background/border: #3c4b64, border: 4px solid,
#   white bold centered text, ~1rem (16px) font.
ROBO_MARKER_DIAMETER = 40
ROBO_MARKER_COLOR = (60, 75, 100)  # #3c4b64
ROBO_MARKER_BORDER_WIDTH = 4
ROBO_MARKER_TEXT_COLOR = (255, 255, 255)  # white
ROBO_MARKER_FONT_SIZE = 16


def _coerce_coordinate(value):
    """Best-effort float conversion; returns None for missing/invalid values."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _load_marker_font(size):
    for font_name in ("DejaVuSans-Bold.ttf", "Arial Bold.ttf", "arialbd.ttf"):
        try:
            return ImageFont.truetype(font_name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def add_robo_coordinates_to_image(robo_coordinates_json, output_dir):
    """
    Draws robot-id markers onto each floor's background floor-plan image and
    saves one annotated PNG per floor that has usable robo_coordinates.

    This is the single, isolated, reusable entry point for mapping/rendering
    robo_coordinates onto floor-plan images - it is not mixed into any
    report/image-generation flow; callers decide when/whether to invoke it
    (e.g. only when do_bandsteering is enabled and this JSON was supplied).

    Expected `robo_coordinates_json` shape:
        {
            "floors": {
                "<floor_id>": {
                    "robo_coordinates": {
                        "<robot_id>": {"x": <num>, "y": <num>, ...}, ...
                    },
                    "image_details": {"bg_img": <str>, "width": <int>, "height": <int>},
                    ...
                }, ...
            },
            "background_image_details": {"bg_img": <str>, "width": <int>, "height": <int>}
        }

    Per floor: `image_details` is used when present, falling back to the
    top-level `background_image_details` for `bg_img`/`width`/`height`. The
    background image is loaded from ROBO_COORDINATES_IMAGE_ASSETS_PATH.
    `x`/`y` are used as-is as the marker's top-left corner (no scaling),
    matching the Web-GUI's `top`/`left` CSS positioning.

    Safely no-ops (skips, logs a warning, continues with other floors) on:
    missing `floors`, missing/empty `robo_coordinates`, missing/invalid x or
    y on individual robots, and missing/unreadable background image files.

    Returns a list of (floor_id, saved_image_path) tuples, one per floor that
    was actually rendered - empty if nothing usable was found.
    """
    rendered_images = []

    floors = robo_coordinates_json.get('floors') if isinstance(robo_coordinates_json, dict) else None
    if not isinstance(floors, dict):
        return rendered_images

    fallback_image_details = robo_coordinates_json.get('background_image_details')
    if not isinstance(fallback_image_details, dict):
        fallback_image_details = {}

    for floor_id, floor_data in floors.items():
        if not isinstance(floor_data, dict):
            continue

        robo_coordinates = floor_data.get('robo_coordinates')
        if not isinstance(robo_coordinates, dict) or not robo_coordinates:
            continue

        image_details = floor_data.get('image_details')
        if not isinstance(image_details, dict):
            image_details = {}

        bg_img = image_details.get('bg_img') or fallback_image_details.get('bg_img')
        if not bg_img:
            logger.warning("Skipping robot-coordinate rendering for floor '%s': no background image configured.", floor_id)
            continue

        image_path = os.path.join(ROBO_COORDINATES_IMAGE_ASSETS_PATH, bg_img)
        if not os.path.exists(image_path):
            logger.warning("Skipping robot-coordinate rendering for floor '%s': background image not found at '%s'.", floor_id, image_path)
            continue

        try:
            with Image.open(image_path) as floor_image:
                annotated_image = floor_image.convert("RGBA")
                draw = ImageDraw.Draw(annotated_image)
                font = _load_marker_font(ROBO_MARKER_FONT_SIZE)

                for robo_id, coord in robo_coordinates.items():
                    if not isinstance(coord, dict):
                        continue

                    left = _coerce_coordinate(coord.get('x'))
                    top = _coerce_coordinate(coord.get('y'))
                    if left is None or top is None:
                        continue

                    right = left + ROBO_MARKER_DIAMETER
                    bottom = top + ROBO_MARKER_DIAMETER
                    draw.ellipse(
                        [left, top, right, bottom],
                        fill=ROBO_MARKER_COLOR,
                        outline=ROBO_MARKER_COLOR,
                        width=ROBO_MARKER_BORDER_WIDTH,
                    )

                    label = str(robo_id)
                    text_bbox = draw.textbbox((0, 0), label, font=font)
                    text_width = text_bbox[2] - text_bbox[0]
                    text_height = text_bbox[3] - text_bbox[1]
                    text_x = left + (ROBO_MARKER_DIAMETER - text_width) / 2 - text_bbox[0]
                    text_y = top + (ROBO_MARKER_DIAMETER - text_height) / 2 - text_bbox[1]
                    draw.text((text_x, text_y), label, fill=ROBO_MARKER_TEXT_COLOR, font=font)
        except Exception as e:
            logger.warning("Skipping robot-coordinate rendering for floor '%s': failed to load/annotate '%s' (%s).", floor_id, image_path, e)
            continue

        os.makedirs(output_dir, exist_ok=True)
        out_path = os.path.join(output_dir, f"robo_coordinates_floor_{floor_id}.png")
        annotated_image.convert("RGB").save(out_path, "PNG")
        rendered_images.append((floor_id, out_path))

    return rendered_images


def robo_coordinates_json_has_usable_data(robo_coordinates_json):
    """
    True if `robo_coordinates_json` contains at least one floor with at least
    one robo_coordinate entry that has valid numeric x/y values. Callers use
    this to decide whether add_robo_coordinates_to_image() is worth calling
    at all (e.g. only when do_bandsteering is enabled AND this returns True).
    """
    if not isinstance(robo_coordinates_json, dict):
        return False

    floors = robo_coordinates_json.get('floors')
    if not isinstance(floors, dict) or not floors:
        return False

    for floor_data in floors.values():
        if not isinstance(floor_data, dict):
            continue
        robo_coordinates = floor_data.get('robo_coordinates')
        if not isinstance(robo_coordinates, dict):
            continue
        for coord in robo_coordinates.values():
            if not isinstance(coord, dict):
                continue
            if _coerce_coordinate(coord.get('x')) is not None and _coerce_coordinate(coord.get('y')) is not None:
                return True

    return False


def parse_robo_coordinates_json(value):
    """
    Normalizes a robo_coordinates_json value - however a caller/CLI happens to
    hand it over - into a dict, or None if it can't be parsed / is empty.

    Accepts:
      - a dict: returned as-is.
      - a path to an existing JSON file: read and parsed.
      - a valid JSON string: parsed with json.loads.
      - a Python dict-literal string (e.g. what `str(some_dict)` produces -
        single-quoted keys, `None`/`True`/`False` instead of
        `null`/`true`/`false`): parsed with ast.literal_eval as a fallback,
        since some callers (e.g. a Web-GUI backend) stringify the object
        with `str()`/an f-string instead of `json.dumps()`.

    Logs a warning and returns None on anything unparseable, rather than
    raising, so a malformed value never breaks the rest of the report flow.
    """
    if not value:
        return None
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        logger.warning("Unsupported robo_coordinates_json type %s; robot markers will not be rendered.", type(value).__name__)
        return None

    if os.path.exists(value):
        try:
            with open(value) as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("Could not read/parse robo_coordinates_json file '%s': %s", value, e)
            return None

    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        pass

    try:
        parsed = ast.literal_eval(value)
    except (ValueError, SyntaxError):
        logger.warning("Could not parse robo_coordinates_json as a file path, JSON, or Python literal; robot markers will not be rendered.")
        return None

    if not isinstance(parsed, dict):
        logger.warning("Parsed robo_coordinates_json is not a dict (got %s); robot markers will not be rendered.", type(parsed).__name__)
        return None
    return parsed
