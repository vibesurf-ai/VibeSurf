import base64
import io
import logging
from typing import Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from browser_use.dom.views import DOMSelectorMap
from browser_use.observability import observe_debug

import math
import base64
import os
import logging
import binascii  # Import specifically for the error type
import pdb

from PIL import Image, ImageDraw, ImageFont
import random
import colorsys
import numpy as np
from typing import Optional, Tuple, List, Any
import io

from vibe_surf.logger import get_logger

logger = get_logger(__name__)


# List of common font file names (Prioritize preferred ones first)
# Consider adding fonts known for broad Unicode coverage early (like Noto)
COMMON_FONT_FILES = [
    "simsun.ttc",
    "seguisb.ttf",  # Segoe UI Semibold (Good UI Font on Windows)
    "arial.ttf",  # Arial (Very common, good compatibility)
    "verdana.ttf",  # Verdana (Good readability)
    "tahoma.ttf",  # Tahoma (Common Windows UI font)
    "calibri.ttf",  # Calibri (Modern default in Office)
    "NotoSans-Regular.ttf",  # Noto Sans Regular (Broad Unicode, often default name)
    "NotoSansCJK-Regular.otf",  # Google Noto Fonts (covers CJK) - OpenType
    "DejaVuSans.ttf",  # Common Linux font (Good coverage)
    "ubuntu-regular.ttf",  # Ubuntu font (Common on Ubuntu Linux)
    " liberation-sans.ttf",  # Liberation Sans (Common Linux alternative to Arial)
    "msyh.ttc", "msyh.ttf",  # Microsoft YaHei (Chinese - Simplified) - TTC or TTF
    "simhei.ttf",  # SimHei (Chinese - Simplified - often present)
    "wqy-zenhei.ttc",  # WenQuanYi Zen Hei (Linux Chinese) - TTC
    "wqy-microhei.ttc",  # WenQuanYi Micro Hei (Linux Chinese) - TTC
    # Add Japanese, Korean, etc. specific fonts if needed
    "msgothic.ttc",  # MS Gothic (Japanese - older Windows) - TTC
    "malgun.ttf",  # Malgun Gothic (Korean - Windows)
    "gulim.ttc",  # Gulim (Korean - older Windows) - TTC
    "AppleGothic.ttf",  # Apple Gothic (macOS Korean)
    "ヒラギノ角ゴ ProN W3.otf",  # Hiragino Kaku Gothic ProN (macOS Japanese) - Use actual name if known
    "songti.ttf",  # Songti (Less common nowadays)
]

# --- Font Directory Discovery ---

FONT_DIRS = []
if os.name == 'nt':  # Windows
    system_root = os.environ.get('SYSTEMROOT', 'C:\\Windows')
    FONT_DIRS.append(os.path.join(system_root, 'Fonts'))
    # User-installed fonts
    local_app_data = os.environ.get('LOCALAPPDATA')
    if local_app_data:
        FONT_DIRS.append(os.path.join(local_app_data, 'Microsoft\\Windows\\Fonts'))
elif os.name == 'posix':
    # Common system-wide locations (Linux, macOS)
    posix_system_dirs = [
        '/usr/share/fonts',
        '/usr/local/share/fonts',
        '/Library/Fonts',  # macOS system
        '/System/Library/Fonts',  # macOS system (usually contains essential fonts)
    ]
    # User-specific locations (Linux, macOS)
    posix_user_dirs = [
        os.path.expanduser('~/.fonts'),
        os.path.expanduser('~/.local/share/fonts'),
        os.path.expanduser('~/Library/Fonts'),  # macOS user
    ]

    # Add existing system directories
    for d in posix_system_dirs:
        if os.path.isdir(d):
            FONT_DIRS.append(d)
            # Also check common subdirectories like truetype, opentype etc.
            for subdir_type in ['truetype', 'opentype', 'TTF', 'OTF', 'type1', 'bitmap']:
                potential_subdir = os.path.join(d, subdir_type)
                if os.path.isdir(potential_subdir):
                    FONT_DIRS.append(potential_subdir)

    # Add existing user directories
    for d in posix_user_dirs:
        if os.path.isdir(d):
            FONT_DIRS.append(d)

# Remove duplicates and ensure directories exist (defensive check)
_unique_dirs = []
for d in FONT_DIRS:
    if d not in _unique_dirs and os.path.isdir(d):  # Check existence again just in case
        _unique_dirs.append(d)
FONT_DIRS = _unique_dirs
# print(f"Searching for fonts in: {FONT_DIRS}") # Optional: for debugging


# --- Caching ---

# Cache found font paths (case-insensitive name -> actual path or None)
_font_path_cache = {}
# Cache loaded font objects ((actual_path, size) -> font_object)
_loaded_font_cache = {}


# --- Core Functions ---

def find_font_path(font_name):
    """
    Tries to find the full path for a given font file name, case-insensitively.
    Uses a cache to store results of previous searches.
    """
    search_name_lower = font_name.lower()

    # 1. Check cache first
    if search_name_lower in _font_path_cache:
        return _font_path_cache[search_name_lower]  # Return cached path or None

    # 2. Search in font directories
    for font_dir in FONT_DIRS:
        try:
            # Use os.scandir for potentially better performance than os.listdir+os.path.isfile
            # It yields DirEntry objects with useful attributes/methods.
            # We still need os.walk for subdirectories. Let's stick to os.walk for simplicity
            # unless performance on flat directories becomes a major issue.
            for root, _, files in os.walk(font_dir, topdown=True):  # topdown=True might find it faster if shallow
                for file in files:
                    if file.lower() == search_name_lower:
                        found_path = os.path.join(root, file)
                        # Verify it's actually a file (os.walk should only list files, but belts and suspenders)
                        if os.path.isfile(found_path):
                            # Cache the successful result (using lowercase name as key)
                            _font_path_cache[search_name_lower] = found_path
                            # print(f"DEBUG: Found '{font_name}' at '{found_path}'") # Optional debug
                            return found_path
        except OSError as e:
            # logger.debug(f"Permission error or issue accessing {font_dir}: {e}") # Optional debug
            continue  # Ignore inaccessible directories or subdirectories

    # 3. If not found after searching all directories, cache the failure (None)
    # logger.debug(f"DEBUG: Could not find font '{font_name}' in any search directory.") # Optional debug
    _font_path_cache[search_name_lower] = None
    return None


def get_font(font_size):
    """
    Loads a preferred font from the COMMON_FONT_FILES list at the specified size.
    Performs case-insensitive search and caches loaded fonts for efficiency.
    Falls back to Pillow's default font if none of the preferred fonts are found/loadable.
    """
    global _loaded_font_cache  # Allow modification of the global cache

    # 1. Iterate through the preferred font list
    for font_name in COMMON_FONT_FILES:
        font_path = find_font_path(font_name)  # Uses the case-insensitive search + path cache

        if font_path:
            # 2. Check loaded font cache ((path, size) -> font object)
            cache_key = (font_path, font_size)
            if cache_key in _loaded_font_cache:
                # print(f"DEBUG: Cache hit for {font_path} size {font_size}") # Optional debug
                return _loaded_font_cache[cache_key]

            # 3. Try to load the font if found and not in cache
            try:
                font = ImageFont.truetype(font_path, font_size)
                _loaded_font_cache[cache_key] = font  # Cache the loaded font object
                # logger.info(f"Loaded font: {font_path} at size {font_size}") # Info level might be too verbose
                # print(f"Loaded font: {font_path} at size {font_size}") # Use print for simple feedback
                return font
            except IOError as e:
                logger.warning(
                    f"Could not load font file '{font_path}' (found for '{font_name}') at size {font_size}. Reason: {e}")
            except Exception as e:
                logger.error(f"Unexpected error loading font {font_name} ({font_path}): {e}")
                # Continue to next font
                continue

    # 4. Fallback to Pillow's default font if loop completes without success
    # Use a specific key for the default font in the cache
    default_cache_key = ("_pillow_default_", font_size)  # Pillow's default doesn't really resize well
    if default_cache_key in _loaded_font_cache:
        return _loaded_font_cache[default_cache_key]

    try:
        logger.warning(
            f"No suitable font found from preferred list in system paths. Using Pillow's default font (size {font_size} requested, but default font may not scale).")
        # Note: Default font might not support all characters or sizing well.
        font = ImageFont.load_default()
        _loaded_font_cache[default_cache_key] = font  # Cache the default font object
        return font
    except IOError as e:
        logger.critical(
            f"CRITICAL ERROR: Could not load any preferred fonts AND failed to load Pillow's default font! Reason: {e}")
        return None


def check_overlap(box1: Tuple[float, float, float, float],
                  box2: Tuple[float, float, float, float]) -> bool:
    """Checks if two rectangular boxes overlap. (Logic unchanged)"""
    l1, t1, r1, b1 = box1
    l2, t2, r2, b2 = box2
    # Check for non-overlap conditions (original logic)
    if r1 <= l2 or r2 <= l1 or b1 <= t2 or b2 <= t1:
        return False
    # Otherwise, they overlap
    return True


def generate_distinct_colors(n):
    """
    Generates n visually distinct colors in RGB format using HSV color space.
    Reorders the generated list deterministically by interleaving even-indexed
    colors with reverse-ordered odd-indexed colors to improve adjacent contrast.
    Example: [0, 1, 2, 3, 4, 5] -> [0, 5, 2, 3, 4, 1]

    Args:
        n: The number of distinct colors to generate.

    Returns:
        A list of n tuples, where each tuple represents an RGB color (int 0-255).
        Returns an empty list if n <= 0.
    """
    if n <= 0:
        return []

    # --- Step 1: Generate colors based on Hue in HSV space ---
    initial_colors = []
    for i in range(n):
        hue = i / n
        # Use high saturation and value for bright colors (parameters from original code)
        saturation = 0.7
        value = 0.8
        rgb_float = colorsys.hsv_to_rgb(hue, saturation, value)
        rgb_int = tuple(int(c * 255) for c in rgb_float)
        initial_colors.append(rgb_int)

    # Handle cases with 0 or 1 color where reordering is not needed/possible
    if n <= 1:
        return initial_colors

    # --- Step 2: Separate into even and odd indexed lists ---
    # Colors originally at even indices (0, 2, 4, ...)
    even_indexed_colors = initial_colors[::2]
    # Colors originally at odd indices (1, 3, 5, ...)
    odd_indexed_colors = initial_colors[1::2]

    # --- Step 3: Reverse the odd indexed list ---
    odd_indexed_colors.reverse()  # Reverse in-place is efficient here

    # --- Step 4: Interleave the lists ---
    reordered_colors = []
    len_odds = len(odd_indexed_colors)
    len_evens = len(even_indexed_colors)

    # Iterate up to the length of the shorter list (which is odd_indexed_colors)
    for i in range(len_odds):
        reordered_colors.append(even_indexed_colors[i])
        reordered_colors.append(odd_indexed_colors[i])

    # --- Step 5: Add any remaining element from the longer list ---
    # If n is odd, the even_indexed_colors list will have one more element
    if len_evens > len_odds:
        reordered_colors.append(even_indexed_colors[-1])  # Append the last even element
    random.shuffle(reordered_colors)
    return reordered_colors

def calculate_label_placement(
        corner: str,
        outline_box: Tuple[float, float, float, float],
        text_width: float,  # Original name: width of the background box
        text_height: float,  # Original name: height of the background box
        box_width: float,  # Original name: width of the element's outline box
        box_height: float,  # Original name: height of the element's outline box
        img_width: int,
        img_height: int
) -> Tuple[Optional[Tuple[float, float, float, float]], Optional[Tuple[float, float]]]:
    """
    Calculates the potential background box and text position reference for a label.
    (Logic and parameters identical to original class method).

    Returns:
        A tuple containing:
        - The calculated background box (l, t, r, b) clamped to image bounds, or None if invalid.
        - The calculated reference position (x, y) (top-left of background), or None if invalid.
    """
    l_outline, t_outline, r_outline, b_outline = outline_box

    # Determine if text should ideally be placed outside (Original Logic)
    move_text_outside = (text_height >= (box_height * 0.5) or text_width >= (
            box_width * 0.5)) and box_height > 0 and box_width > 0

    bg_left, bg_top, bg_right, bg_bottom = 0.0, 0.0, 0.0, 0.0
    # Text offset calculation is handled by the caller based on the returned reference point
    # text_x_offset, text_y_offset = 0, 0 # Original logic didn't use these this way

    # --- Calculate base positions based on corner (Original Logic) ---
    if corner == 'top_right':
        if move_text_outside:  # Outside Top-Right
            bg_left = r_outline
            bg_top = t_outline - text_height
        else:  # Inside Top-Right
            bg_left = r_outline - text_width
            bg_top = t_outline
        bg_right = bg_left + text_width
        bg_bottom = bg_top + text_height

    elif corner == 'bottom_right':
        if move_text_outside:  # Outside Bottom-Right
            bg_left = r_outline
            bg_top = b_outline
        else:  # Inside Bottom-Right
            bg_left = r_outline - text_width
            bg_top = b_outline - text_height
        bg_right = bg_left + text_width
        bg_bottom = bg_top + text_height

    elif corner == 'bottom_left':
        if move_text_outside:  # Outside Bottom-Left
            bg_left = l_outline - text_width
            bg_top = b_outline
        else:  # Inside Bottom-Left
            bg_left = l_outline
            bg_top = b_outline - text_height
        bg_right = bg_left + text_width
        bg_bottom = bg_top + text_height

    elif corner == 'top_left':
        if move_text_outside:  # Outside Top-Left
            bg_left = l_outline - text_width
            bg_top = t_outline - text_height
        else:  # Inside Top-Left
            bg_left = l_outline
            bg_top = t_outline
        bg_right = bg_left + text_width
        bg_bottom = bg_top + text_height
    else:
        logger.error(f"Invalid corner specified: {corner}")
        return None, None

    # --- Clamp background box to IMAGE boundaries (Original Logic) ---
    final_bg_left = max(0.0, bg_left)
    final_bg_top = max(0.0, bg_top)
    final_bg_right = min(float(img_width), bg_right)
    final_bg_bottom = min(float(img_height), bg_bottom)

    # Check if clamping made the box invalid (Original Logic)
    if final_bg_right <= final_bg_left or final_bg_bottom <= final_bg_top:
        return None, None  # Indicate invalid placement

    # --- Calculate reference text position (Top-left of background box) ---
    # The actual draw position will be offset slightly by the caller using '+1, +1' per original code
    final_text_ref_x = final_bg_left
    final_text_ref_y = final_bg_top

    final_bg_box = (final_bg_left, final_bg_top, final_bg_right, final_bg_bottom)
    final_text_ref_pos = (final_text_ref_x, final_text_ref_y)

    return final_bg_box, final_text_ref_pos


def highlight_screenshot(screenshot_base64: str, elements: List[List[Any]]) -> str:
    """
    Draws highlighted bounding boxes with index numbers (avoiding label overlap)
    on a screenshot, using standalone functions. **Parameters and core logic
    are preserved exactly from the user's provided class-based version.**

    Args:
        screenshot_base64: The screenshot image encoded in base64.
        elements: A list where each item is another list:
                  [highlight_index: int, box_coords: List[float]]
                  Box coordinates are [x1, y1, x2, y2] relative to the screenshot.

    Returns:
        A base64 encoded string of the highlighted screenshot (PNG format),
        or the original base64 string if errors occur or no valid elements
        are provided.
    """
    if not elements:
        logger.warning("No elements provided to highlight.")
        return screenshot_base64

    # Filter elements based on the new list structure - basic validation
    valid_elements = []
    seen_indices = set()
    for i, element_item in enumerate(elements):
        if (isinstance(element_item, (list, tuple)) and len(element_item) >= 2 and
                isinstance(element_item[0], int) and  # Check index type
                isinstance(element_item[1], (list, tuple)) and len(element_item[1]) == 4):  # Check box structure
            try:
                # Validate box coords are numeric and index is unique
                box_coords = [float(c) for c in element_item[1]]
                highlight_index = element_item[0]
                if highlight_index in seen_indices:
                    logger.warning(
                        f"Skipping element at raw index {i} due to duplicate highlight_index: {highlight_index}")
                    continue

                # Check for non-negative index if required (original code didn't explicitly)
                if highlight_index < 0:
                    logger.warning(
                        f"Skipping element at raw index {i} due to negative highlight_index: {highlight_index}")
                    continue

                valid_elements.append([highlight_index, box_coords])  # Use validated coords
                seen_indices.add(highlight_index)
            except (ValueError, TypeError):
                logger.warning(f"Skipping element at raw index {i} due to invalid box coordinates: {element_item[1]}")
        else:
            logger.warning(
                f"Skipping element at raw index {i} due to invalid structure or types. Expected [int, [x1,y1,x2,y2]], got: {element_item}")

    if not valid_elements:
        logger.warning("No valid elements found after filtering.")
        return screenshot_base64

    # Sort elements by highlight_index (first item in inner list) - REQUIRED for consistent color
    # The conversion function already sorts, but doing it again handles direct list input.
    try:
        valid_elements.sort(key=lambda el: el[0])
    except Exception as e:
        logger.error(f"Error sorting elements: {e}. Proceeding unsorted (color assignment may be inconsistent).")

    # --- Image Loading ---
    try:
        image_data = base64.b64decode(screenshot_base64)
        image = Image.open(io.BytesIO(image_data)).convert("RGBA")
    except Exception as e:
        logger.error(f"Error decoding or opening image: {e}")
        return screenshot_base64

    img_width, img_height = image.size
    if img_width <= 0 or img_height <= 0:
        logger.error(f"Invalid image dimensions: {image.size}")
        return screenshot_base64

    # --- Setup Drawing ---
    fill_overlay = Image.new('RGBA', image.size, (255, 255, 255, 0))
    draw_fill = ImageDraw.Draw(fill_overlay)

    num_elements = len(valid_elements)
    colors = generate_distinct_colors(num_elements)
    fill_alpha = int(0.3 * 255)  # ** PARAMETER FROM ORIGINAL CODE **

    # --- Pass 1: Draw semi-transparent fills (Logic unchanged) ---
    for i, element_item in enumerate(valid_elements):
        highlight_index = element_item[0]  # Now index 0
        box_coords = element_item[1]  # Now index 1
        rel_left, rel_top, rel_right, rel_bottom = box_coords

        rel_left = max(min(rel_left, img_width), 0)
        rel_right = max(min(rel_right, img_width), 0)
        rel_top = max(min(rel_top, img_height), 0)
        rel_bottom = max(min(rel_bottom, img_height), 0)

        # Validation and clipping (Logic unchanged)
        if rel_right <= rel_left or rel_bottom <= rel_top:
            logger.debug(
                f"Skipping fill for element index {highlight_index} due to invalid box dimensions: {box_coords}")
            continue
        # if rel_right <= 0 or rel_bottom <= 0 or rel_left >= img_width or rel_top >= img_height:
        #     logger.debug(
        #         f"Skipping fill for element index {highlight_index} as it's outside image bounds: {box_coords}")
        #     continue

        draw_box = (max(0.0, rel_left), max(0.0, rel_top),
                    min(float(img_width), rel_right), min(float(img_height), rel_bottom))

        color_rgb = colors[i % num_elements]  # Use 'i' from loop for color consistency
        fill_color = (*color_rgb, fill_alpha)

        try:
            if draw_box[2] > draw_box[0] and draw_box[3] > draw_box[1]:
                draw_fill.rectangle(draw_box, fill=fill_color)
        except Exception as draw_e:
            logger.error(f"Error drawing fill for element index {highlight_index}, Box: {draw_box}: {draw_e}")

    # --- Composite the fill overlay (Logic unchanged) ---
    try:
        image = Image.alpha_composite(image, fill_overlay)
    except ValueError as e:
        logger.error(f"Error during alpha compositing: {e}. Check image modes.")
        # Fallback: Continue drawing on the original image without the overlay
        # Note: Fills will not be semi-transparent in this fallback case.
        image = Image.open(io.BytesIO(image_data)).convert("RGBA")  # Re-load original
        logger.warning("Compositing failed. Drawing outlines/text on original image.")
        # Intentionally not re-drawing fills here to avoid opaque blocks

    draw_main = ImageDraw.Draw(image)

    # --- Pass 2: Draw outlines and text (Parameters and logic identical to original) ---
    placed_label_boxes: List[Tuple[float, float, float, float]] = []
    corners_to_try = ['top_right', 'bottom_right', 'bottom_left', 'top_left']  # ** PARAMETER FROM ORIGINAL CODE **

    for i, element_item in enumerate(valid_elements):
        highlight_index = element_item[0]
        box_coords = element_item[1]
        label = str(highlight_index)
        color_rgb = colors[i % num_elements]  # Use 'i' from loop for color
        outline_width = 2  # ** PARAMETER FROM ORIGINAL CODE **

        rel_left, rel_top, rel_right, rel_bottom = box_coords

        # Re-validate (Logic unchanged)
        if rel_right <= rel_left or rel_bottom <= rel_top: continue
        if rel_right <= 0 or rel_bottom <= 0 or rel_left >= img_width or rel_top >= img_height: continue

        draw_box_outline = (max(0.0, rel_left), max(0.0, rel_top),
                            min(float(img_width), rel_right),
                            min(float(img_height), rel_bottom))

        box_width = draw_box_outline[2] - draw_box_outline[0]
        box_height = draw_box_outline[3] - draw_box_outline[1]
        if box_width <= 0 or box_height <= 0: continue

        # --- Dynamic Font Size Calculation (Formula from original code) ---
        min_dim = min(box_width, box_height)
        font_size = max(25, min(35, int(min_dim * 0.4)))  # ** FORMULA FROM ORIGINAL CODE **
        font = get_font(font_size)

        if not font:
            logger.warning(f"Could not load font for index {highlight_index}, skipping text label.")
            try:  # Still draw outline
                if draw_box_outline[2] > draw_box_outline[0] and draw_box_outline[3] > draw_box_outline[1]:
                    draw_main.rectangle(draw_box_outline, outline=color_rgb, width=outline_width)
            except Exception as draw_e:
                logger.error(f"Error drawing outline for index {highlight_index} (no font): {draw_e}")
            continue

        # --- Estimate text bounding box size (Logic and padding from original code) ---
        try:
            text_bbox = draw_main.textbbox((0, 0), label, font=font, stroke_width=0, align="center", anchor='lt')
            text_render_width = text_bbox[2] - text_bbox[0]
            text_render_height = text_bbox[3] - text_bbox[1]
            # Padding calculation from original code
            render_width = min(text_render_width, text_render_width)  # Original code had this redundancy
            h_padding = render_width // 6  # ** FORMULA FROM ORIGINAL CODE **
            w_padding = render_width // 6  # ** FORMULA FROM ORIGINAL CODE **
            # Total background dimensions needed
            label_bg_width = text_render_width + w_padding
            label_bg_height = text_render_height + h_padding
        except AttributeError:  # Fallback logic from original code
            logger.debug("Using font.getsize fallback for text dimensions.")
            try:
                text_render_width, text_render_height = draw_main.textlength(label, font=font), font.size
            except AttributeError:
                text_render_width = len(label) * font_size * 0.6
                text_render_height = font_size
            # Padding calculation from original code (repeated)
            render_width = min(text_render_width, text_render_width)
            h_padding = render_width // 6  # ** FORMULA FROM ORIGINAL CODE **
            w_padding = render_width // 6  # ** FORMULA FROM ORIGINAL CODE **
            label_bg_width = text_render_width + w_padding
            label_bg_height = text_render_height + h_padding
        except Exception as tb_e:
            logger.error(f"Error calculating text size for index {highlight_index}: {tb_e}. Using estimate.")
            # Fallback estimate from original code
            label_bg_width = len(label) * font_size * 0.8
            label_bg_height = font_size * 1.5

        # --- Find Non-Overlapping Label Position (Logic unchanged) ---
        chosen_label_bg_box = None
        chosen_text_pos = None  # Final position for draw_main.text()
        found_non_overlapping_spot = False

        for corner_choice in corners_to_try:
            potential_bg_box, potential_text_ref_pos = calculate_label_placement(
                corner=corner_choice,
                outline_box=draw_box_outline,
                text_width=label_bg_width,  # Use calculated background width
                text_height=label_bg_height,  # Use calculated background height
                box_width=box_width,  # Use element box width
                box_height=box_height,  # Use element box height
                img_width=img_width,
                img_height=img_height
            )

            if potential_bg_box is None: continue

            if potential_bg_box[0] < 0 or potential_bg_box[1] < 0 or potential_bg_box[2] >= img_width or \
                    potential_bg_box[3] >= img_height:
                continue

            overlaps = any(check_overlap(potential_bg_box, placed_box) for placed_box in placed_label_boxes)

            if not overlaps:
                chosen_label_bg_box = potential_bg_box
                # Text position adjustment from original code
                chosen_text_pos = (
                    potential_text_ref_pos[0] + w_padding // 2,
                    potential_text_ref_pos[1] + h_padding // 2)  # ** OFFSET FROM ORIGINAL CODE **
                found_non_overlapping_spot = True
                break

        # --- Default if all corners overlap (Logic unchanged) ---
        if not found_non_overlapping_spot:
            # logger.debug(f"Could not avoid label overlap for index {highlight_index}. Defaulting to top-left.")
            chosen_label_bg_box, potential_text_ref_pos = calculate_label_placement(
                corner='top_left',  # Default corner from original code
                outline_box=draw_box_outline,
                text_width=label_bg_width,
                text_height=label_bg_height,
                box_width=box_width,
                box_height=box_height,
                img_width=img_width,
                img_height=img_height
            )
            if chosen_label_bg_box and potential_text_ref_pos:
                # Text position adjustment from original code
                chosen_text_pos = (
                    potential_text_ref_pos[0] + w_padding // 2,
                    potential_text_ref_pos[1] + h_padding // 2)  # ** OFFSET FROM ORIGINAL CODE **
            else:
                # logger.debug(f"Default top-left placement failed for index {highlight_index}. Skipping label.")
                chosen_label_bg_box = None
                chosen_text_pos = None

        # --- Draw Outline, Label Background, and Text (Logic unchanged) ---
        try:
            # 1. Draw Outline
            if draw_box_outline[2] > draw_box_outline[0] and draw_box_outline[3] > draw_box_outline[1]:
                draw_main.rectangle(draw_box_outline, outline=color_rgb, width=outline_width)

            # 2. Draw Label (if valid position found)
            if chosen_label_bg_box and chosen_text_pos:
                # Ensure background box is valid before drawing
                if chosen_label_bg_box[2] > chosen_label_bg_box[0] and chosen_label_bg_box[3] > chosen_label_bg_box[1]:
                    draw_main.rectangle(chosen_label_bg_box, fill=color_rgb)

                    # Check text position is within image bounds before drawing
                    if chosen_text_pos[0] < img_width and chosen_text_pos[1] < img_height:
                        # Text drawing call from original code
                        draw_main.text(chosen_text_pos, label, fill="white", font=font, stroke_width=0, align="center",
                                       anchor='lt')

                    # Add *after* successful drawing attempt (Logic unchanged)
                    placed_label_boxes.append(chosen_label_bg_box)
                else:
                    logger.warning(
                        f"Skipping label for index {highlight_index} due to invalid final background box: {chosen_label_bg_box}")

        except Exception as draw_e:
            logger.error(
                f"Error during final drawing for index {highlight_index}, Box: {draw_box_outline}, LabelBox: {chosen_label_bg_box}): {draw_e}")

    # --- Encode final image (Logic unchanged) ---
    try:
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        highlighted_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
        return highlighted_base64
    except Exception as e:
        logger.error(f"Error encoding final image to base64: {e}")
        return screenshot_base64


@observe_debug(ignore_input=True, ignore_output=True, name='create_highlighted_screenshot')
def create_highlighted_screenshot(
        screenshot_b64: str,
        selector_map: DOMSelectorMap,
        device_pixel_ratio: float = 1.0,
        viewport_offset_x: int = 0,
        viewport_offset_y: int = 0,
) -> str:
    """Create a highlighted screenshot with bounding boxes around interactive elements.
    Args:
        screenshot_b64: Base64 encoded screenshot
        selector_map: Map of interactive elements with their positions
        device_pixel_ratio: Device pixel ratio for scaling coordinates
        viewport_offset_x: X offset for viewport positioning
        viewport_offset_y: Y offset for viewport positioning
    Returns:
        Base64 encoded highlighted screenshot
    """
    try:
        # Decode screenshot
        screenshot_data = base64.b64decode(screenshot_b64)
        image = Image.open(io.BytesIO(screenshot_data)).convert('RGBA')

        # Process each interactive element
        valid_elements = []
        for element_id, element in selector_map.items():
            try:
                # Use snapshot bounds (document coordinates) if available, otherwise absolute_position
                bounds = element.absolute_position

                # Scale coordinates from CSS pixels to device pixels for screenshot
                # The screenshot is captured at device pixel resolution, but coordinates are in CSS pixels
                x1 = int(bounds.x * device_pixel_ratio)
                y1 = int(bounds.y * device_pixel_ratio)
                x2 = int((bounds.x + bounds.width) * device_pixel_ratio)
                y2 = int((bounds.y + bounds.height) * device_pixel_ratio)

                # Ensure coordinates are within image bounds
                img_width, img_height = image.size
                x1 = max(0, min(x1, img_width))
                y1 = max(0, min(y1, img_height))
                x2 = max(x1, min(x2, img_width))
                y2 = max(y1, min(y2, img_height))

                # Skip if bounding box is too small or invalid
                if x2 - x1 < 2 or y2 - y1 < 2:
                    continue

                valid_elements.append([element_id, [x1, y1, x2, y2]])

            except Exception as e:
                logger.debug(f'Failed to draw highlight for element {element_id}: {e}')
                continue

        highlighted_b64 = highlight_screenshot(screenshot_b64, valid_elements)

        logger.debug(f'Successfully created highlighted screenshot with {len(selector_map)} elements')
        return highlighted_b64

    except Exception as e:
        logger.error(f'Failed to create highlighted screenshot: {e}')
        # Return original screenshot on error
        return screenshot_b64


async def get_viewport_info_from_cdp(cdp_session) -> Tuple[float, int, int]:
    """Get viewport information from CDP session.
    Returns:
        Tuple of (device_pixel_ratio, scroll_x, scroll_y)
    """
    try:
        # Get layout metrics which includes viewport info and device pixel ratio
        metrics = await cdp_session.cdp_client.send.Page.getLayoutMetrics(session_id=cdp_session.session_id)

        # Extract viewport information
        visual_viewport = metrics.get('visualViewport', {})
        css_visual_viewport = metrics.get('cssVisualViewport', {})
        css_layout_viewport = metrics.get('cssLayoutViewport', {})

        # Calculate device pixel ratio
        css_width = css_visual_viewport.get('clientWidth', css_layout_viewport.get('clientWidth', 1280.0))
        device_width = visual_viewport.get('clientWidth', css_width)
        device_pixel_ratio = device_width / css_width if css_width > 0 else 1.0

        # Get scroll position in CSS pixels
        scroll_x = int(css_visual_viewport.get('pageX', 0))
        scroll_y = int(css_visual_viewport.get('pageY', 0))

        return float(device_pixel_ratio), scroll_x, scroll_y

    except Exception as e:
        logger.debug(f'Failed to get viewport info from CDP: {e}')
        return 1.0, 0, 0


@observe_debug(ignore_input=True, ignore_output=True, name='create_highlighted_screenshot_async')
async def create_highlighted_screenshot_async(screenshot_b64: str, selector_map: DOMSelectorMap,
                                              cdp_session=None) -> str:
    """Async wrapper for creating highlighted screenshots.
    Args:
        screenshot_b64: Base64 encoded screenshot
        selector_map: Map of interactive elements
        cdp_session: CDP session for getting viewport info
    Returns:
        Base64 encoded highlighted screenshot
    """
    # Get viewport information if CDP session is available
    device_pixel_ratio = 1.0
    viewport_offset_x = 0
    viewport_offset_y = 0

    if cdp_session:
        try:
            device_pixel_ratio, viewport_offset_x, viewport_offset_y = await get_viewport_info_from_cdp(cdp_session)
        except Exception as e:
            logger.debug(f'Failed to get viewport info from CDP: {e}')

    # Create highlighted screenshot (run in thread pool if needed for performance)
    return create_highlighted_screenshot(screenshot_b64, selector_map, device_pixel_ratio, viewport_offset_x,
                                         viewport_offset_y)
