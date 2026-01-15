"""
Card Generator - Creates visual cards for welcome, goodbye, and profile

Uses Pillow to generate high-quality images with:
- User avatar
- Custom/default backgrounds
- Text overlays
- Gradient effects
- Circular avatars with borders
"""

import io
import aiohttp
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
from typing import Optional, Tuple
import os

# Font paths
FONT_DIR = "/usr/share/fonts/truetype/dejavu"
FONT_BOLD = f"{FONT_DIR}/DejaVuSans-Bold.ttf"
FONT_REGULAR = f"{FONT_DIR}/DejaVuSans.ttf"

# Default card dimensions
WELCOME_CARD_WIDTH = 800
WELCOME_CARD_HEIGHT = 300
PROFILE_CARD_WIDTH = 934
PROFILE_CARD_HEIGHT = 400

# Color schemes
COLORS = {
    "primary": (88, 101, 242),      # Discord blurple
    "secondary": (114, 137, 218),   # Light blurple
    "success": (87, 242, 135),      # Green
    "warning": (254, 231, 92),      # Yellow
    "danger": (237, 66, 69),        # Red
    "white": (255, 255, 255),
    "light_gray": (185, 185, 185),
    "dark_gray": (50, 50, 60),
    "darker": (35, 39, 42),
    "darkest": (23, 26, 32),
}


async def download_image(url: str) -> Optional[Image.Image]:
    """Download an image from URL and return as PIL Image"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.read()
                    return Image.open(io.BytesIO(data)).convert("RGBA")
    except Exception:
        pass
    return None


def get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Get a font with fallback to default"""
    try:
        font_path = FONT_BOLD if bold else FONT_REGULAR
        return ImageFont.truetype(font_path, size)
    except:
        return ImageFont.load_default()


def create_circular_image(image: Image.Image, size: int, border_width: int = 4, border_color: Tuple = COLORS["primary"]) -> Image.Image:
    """Create a circular image with optional border"""
    # Resize image
    image = image.resize((size, size), Image.Resampling.LANCZOS)

    # Create circular mask
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, size, size), fill=255)

    # Apply mask to create circular image
    output = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    output.paste(image, mask=mask)

    # Add border
    if border_width > 0:
        border_size = size + (border_width * 2)
        bordered = Image.new("RGBA", (border_size, border_size), (0, 0, 0, 0))
        border_draw = ImageDraw.Draw(bordered)

        # Draw border circle
        border_draw.ellipse(
            (0, 0, border_size - 1, border_size - 1),
            fill=border_color + (255,)
        )

        # Paste circular image on top
        bordered.paste(output, (border_width, border_width), output)
        return bordered

    return output


def create_gradient_background(width: int, height: int, color1: Tuple, color2: Tuple, direction: str = "diagonal") -> Image.Image:
    """Create a gradient background image"""
    image = Image.new("RGBA", (width, height), (0, 0, 0, 255))

    for y in range(height):
        for x in range(width):
            if direction == "diagonal":
                ratio = (x + y) / (width + height)
            elif direction == "horizontal":
                ratio = x / width
            elif direction == "vertical":
                ratio = y / height
            else:
                ratio = (x + y) / (width + height)

            r = int(color1[0] + (color2[0] - color1[0]) * ratio)
            g = int(color1[1] + (color2[1] - color1[1]) * ratio)
            b = int(color1[2] + (color2[2] - color1[2]) * ratio)
            image.putpixel((x, y), (r, g, b, 255))

    return image


def add_rounded_rectangle(draw: ImageDraw.Draw, xy: Tuple, radius: int, fill: Tuple = None, outline: Tuple = None, width: int = 1):
    """Draw a rounded rectangle"""
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def add_glow(image: Image.Image, color: Tuple, radius: int = 20) -> Image.Image:
    """Add a glow effect around an image"""
    # Create glow layer
    glow_size = (image.width + radius * 2, image.height + radius * 2)
    glow = Image.new("RGBA", glow_size, (0, 0, 0, 0))

    # Create glow circle/shape
    glow_draw = ImageDraw.Draw(glow)
    glow_draw.ellipse(
        (0, 0, glow_size[0] - 1, glow_size[1] - 1),
        fill=color + (100,)
    )

    # Blur the glow
    glow = glow.filter(ImageFilter.GaussianBlur(radius))

    # Composite
    result = Image.new("RGBA", glow_size, (0, 0, 0, 0))
    result.paste(glow, (0, 0))
    result.paste(image, (radius, radius), image)

    return result


# ============================================
# WELCOME CARD GENERATOR
# ============================================

async def create_welcome_card(
    avatar_url: str,
    username: str,
    member_count: int,
    server_name: str,
    background_url: Optional[str] = None,
    custom_message: Optional[str] = None
) -> Image.Image:
    """
    Create a welcome card image

    Args:
        avatar_url: URL to user's avatar
        username: User's display name
        member_count: Server member count
        server_name: Name of the server
        background_url: Optional custom background image URL
        custom_message: Optional custom welcome text

    Returns:
        PIL Image object
    """
    width = WELCOME_CARD_WIDTH
    height = WELCOME_CARD_HEIGHT

    # Create background
    if background_url:
        background = await download_image(background_url)
        if background:
            # Resize and darken background
            background = background.resize((width, height), Image.Resampling.LANCZOS)
            enhancer = ImageEnhance.Brightness(background)
            background = enhancer.enhance(0.4)  # Darken
        else:
            background = create_gradient_background(width, height, COLORS["darkest"], COLORS["darker"])
    else:
        background = create_gradient_background(width, height, COLORS["darkest"], COLORS["darker"])

    # Create card base
    card = background.convert("RGBA")
    draw = ImageDraw.Draw(card)

    # Add subtle overlay
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 100))
    card = Image.alpha_composite(card, overlay)
    draw = ImageDraw.Draw(card)

    # Add border
    add_rounded_rectangle(
        draw,
        [(5, 5), (width - 6, height - 6)],
        radius=15,
        outline=COLORS["primary"] + (150,),
        width=3
    )

    # Download and process avatar
    avatar = await download_image(avatar_url)
    if avatar is None:
        # Create default avatar
        avatar = Image.new("RGBA", (128, 128), COLORS["primary"] + (255,))
        avatar_draw = ImageDraw.Draw(avatar)
        font = get_font(60, bold=True)
        letter = username[0].upper()
        bbox = avatar_draw.textbbox((0, 0), letter, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        avatar_draw.text(
            ((128 - text_width) // 2, (128 - text_height) // 2 - 10),
            letter,
            fill=COLORS["white"],
            font=font
        )

    # Create circular avatar with glow
    avatar_size = 140
    circular_avatar = create_circular_image(avatar, avatar_size, border_width=4, border_color=COLORS["primary"])

    # Position avatar
    avatar_x = 50
    avatar_y = (height - circular_avatar.height) // 2

    # Add glow behind avatar
    glowing_avatar = add_glow(circular_avatar, COLORS["primary"], radius=15)
    glow_offset = 15
    card.paste(glowing_avatar, (avatar_x - glow_offset, avatar_y - glow_offset), glowing_avatar)

    # Text positioning
    text_x = avatar_x + circular_avatar.width + 40

    # WELCOME text
    welcome_font = get_font(24, bold=True)
    draw.text((text_x, 50), "WELCOME", fill=COLORS["primary"], font=welcome_font)

    # Username
    username_font = get_font(42, bold=True)
    username_display = username[:25] + "..." if len(username) > 25 else username
    draw.text((text_x, 80), username_display, fill=COLORS["white"], font=username_font)

    # Server name
    server_font = get_font(20)
    draw.text((text_x, 140), f"to {server_name}", fill=COLORS["light_gray"], font=server_font)

    # Member count
    member_font = get_font(18)
    member_text = f"You are member #{member_count:,}"
    draw.text((text_x, 175), member_text, fill=COLORS["light_gray"], font=member_font)

    # Custom message if provided
    if custom_message:
        msg_font = get_font(16)
        # Truncate if too long
        if len(custom_message) > 60:
            custom_message = custom_message[:57] + "..."
        draw.text((text_x, 210), custom_message, fill=COLORS["secondary"], font=msg_font)

    # Decorative elements - dots
    for i in range(5):
        x = width - 100 + (i * 15)
        y = height // 2
        radius = 3
        draw.ellipse(
            [(x - radius, y - radius), (x + radius, y + radius)],
            fill=COLORS["primary"] + (100 + i * 30,)
        )

    return card


# ============================================
# GOODBYE CARD GENERATOR
# ============================================

async def create_goodbye_card(
    avatar_url: str,
    username: str,
    server_name: str,
    background_url: Optional[str] = None
) -> Image.Image:
    """
    Create a goodbye card image

    Similar to welcome card but with different styling
    """
    width = WELCOME_CARD_WIDTH
    height = WELCOME_CARD_HEIGHT

    # Create background with warmer/sadder tones
    if background_url:
        background = await download_image(background_url)
        if background:
            background = background.resize((width, height), Image.Resampling.LANCZOS)
            enhancer = ImageEnhance.Brightness(background)
            background = enhancer.enhance(0.3)
        else:
            background = create_gradient_background(width, height, (40, 30, 50), (60, 40, 70))
    else:
        background = create_gradient_background(width, height, (40, 30, 50), (60, 40, 70))

    card = background.convert("RGBA")
    draw = ImageDraw.Draw(card)

    # Add overlay
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 80))
    card = Image.alpha_composite(card, overlay)
    draw = ImageDraw.Draw(card)

    # Add border (orange/red tint for goodbye)
    border_color = (200, 100, 80)
    add_rounded_rectangle(
        draw,
        [(5, 5), (width - 6, height - 6)],
        radius=15,
        outline=border_color + (150,),
        width=3
    )

    # Avatar
    avatar = await download_image(avatar_url)
    if avatar is None:
        avatar = Image.new("RGBA", (128, 128), border_color + (255,))
        avatar_draw = ImageDraw.Draw(avatar)
        font = get_font(60, bold=True)
        letter = username[0].upper()
        bbox = avatar_draw.textbbox((0, 0), letter, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        avatar_draw.text(
            ((128 - text_width) // 2, (128 - text_height) // 2 - 10),
            letter,
            fill=COLORS["white"],
            font=font
        )

    avatar_size = 140
    circular_avatar = create_circular_image(avatar, avatar_size, border_width=4, border_color=border_color)

    avatar_x = 50
    avatar_y = (height - circular_avatar.height) // 2

    # Grayscale effect on avatar
    circular_avatar = circular_avatar.convert("LA").convert("RGBA")

    glowing_avatar = add_glow(circular_avatar, border_color, radius=15)
    glow_offset = 15
    card.paste(glowing_avatar, (avatar_x - glow_offset, avatar_y - glow_offset), glowing_avatar)

    # Text
    text_x = avatar_x + circular_avatar.width + 40

    goodbye_font = get_font(24, bold=True)
    draw.text((text_x, 60), "GOODBYE", fill=border_color, font=goodbye_font)

    username_font = get_font(42, bold=True)
    username_display = username[:25] + "..." if len(username) > 25 else username
    draw.text((text_x, 90), username_display, fill=COLORS["white"], font=username_font)

    server_font = get_font(20)
    draw.text((text_x, 160), f"has left {server_name}", fill=COLORS["light_gray"], font=server_font)

    message_font = get_font(16)
    draw.text((text_x, 200), "We'll miss you!", fill=COLORS["light_gray"], font=message_font)

    return card


# ============================================
# PROFILE CARD GENERATOR
# ============================================

async def create_profile_card(
    avatar_url: str,
    username: str,
    level: int,
    xp: int,
    xp_needed: int,
    balance: int,
    reputation: int,
    rank: int,
    achievements_unlocked: int,
    total_achievements: int,
    messages: int,
    voice_hours: int,
    accent_color: Tuple = COLORS["primary"]
) -> Image.Image:
    """
    Create a comprehensive profile card showing all user stats

    Args:
        avatar_url: URL to user's avatar
        username: User's display name
        level: Current level
        xp: Current XP in level
        xp_needed: XP needed for next level
        balance: Coin balance
        reputation: Rep points
        rank: Server rank
        achievements_unlocked: Number of unlocked achievements
        total_achievements: Total achievements available
        messages: Total messages sent
        voice_hours: Total voice chat hours
        accent_color: Custom accent color

    Returns:
        PIL Image object
    """
    width = PROFILE_CARD_WIDTH
    height = PROFILE_CARD_HEIGHT

    # Create gradient background
    card = create_gradient_background(width, height, COLORS["darkest"], COLORS["darker"])
    draw = ImageDraw.Draw(card)

    # Add border
    add_rounded_rectangle(
        draw,
        [(3, 3), (width - 4, height - 4)],
        radius=20,
        outline=accent_color + (180,),
        width=3
    )

    # Download avatar
    avatar = await download_image(avatar_url)
    if avatar is None:
        avatar = Image.new("RGBA", (128, 128), accent_color + (255,))
        avatar_draw = ImageDraw.Draw(avatar)
        font = get_font(60, bold=True)
        letter = username[0].upper()
        bbox = avatar_draw.textbbox((0, 0), letter, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        avatar_draw.text(
            ((128 - text_width) // 2, (128 - text_height) // 2 - 10),
            letter,
            fill=COLORS["white"],
            font=font
        )

    # Create circular avatar
    avatar_size = 120
    circular_avatar = create_circular_image(avatar, avatar_size, border_width=4, border_color=accent_color)

    # Position avatar
    avatar_x = 40
    avatar_y = 40
    card.paste(circular_avatar, (avatar_x, avatar_y), circular_avatar)

    # Username and rank
    text_x = avatar_x + avatar_size + 30

    username_font = get_font(32, bold=True)
    username_display = username[:25] + "..." if len(username) > 25 else username
    draw.text((text_x, 50), username_display, fill=COLORS["white"], font=username_font)

    # Rank badge
    rank_font = get_font(18)
    rank_text = f"Rank #{rank}"
    draw.text((text_x, 90), rank_text, fill=COLORS["light_gray"], font=rank_font)

    # Level badge (top right)
    level_x = width - 150
    level_label_font = get_font(16)
    level_font = get_font(48, bold=True)
    draw.text((level_x, 35), "LEVEL", fill=COLORS["light_gray"], font=level_label_font)
    draw.text((level_x, 55), str(level), fill=accent_color, font=level_font)

    # XP Progress bar
    bar_x = 40
    bar_y = 180
    bar_width = width - 80
    bar_height = 25

    # Background bar
    add_rounded_rectangle(
        draw,
        [(bar_x, bar_y), (bar_x + bar_width, bar_y + bar_height)],
        radius=bar_height // 2,
        fill=COLORS["dark_gray"]
    )

    # Progress fill
    progress = min((xp / xp_needed) * 100, 100)
    fill_width = int((bar_width - 4) * (progress / 100))
    if fill_width > 10:
        add_rounded_rectangle(
            draw,
            [(bar_x + 2, bar_y + 2), (bar_x + 2 + fill_width, bar_y + bar_height - 2)],
            radius=(bar_height - 4) // 2,
            fill=accent_color
        )

    # XP text
    xp_font = get_font(14)
    xp_text = f"{xp:,} / {xp_needed:,} XP"
    xp_bbox = draw.textbbox((0, 0), xp_text, font=xp_font)
    xp_width = xp_bbox[2] - xp_bbox[0]
    draw.text((bar_x + bar_width - xp_width - 10, bar_y + 5), xp_text, fill=COLORS["white"], font=xp_font)

    # Progress percentage
    progress_text = f"{progress:.1f}%"
    draw.text((bar_x + 10, bar_y + 5), progress_text, fill=COLORS["white"], font=xp_font)

    # Stats section
    stats_y = 230
    stat_width = (width - 80) // 4
    stat_font = get_font(14)
    stat_value_font = get_font(24, bold=True)

    stats = [
        ("BALANCE", f"{balance:,}", COLORS["warning"]),
        ("REPUTATION", f"{reputation:,}", COLORS["success"]),
        ("MESSAGES", f"{messages:,}", COLORS["primary"]),
        ("VOICE TIME", f"{voice_hours}h", COLORS["secondary"]),
    ]

    for i, (label, value, color) in enumerate(stats):
        x = 40 + (i * stat_width)

        # Stat box
        add_rounded_rectangle(
            draw,
            [(x, stats_y), (x + stat_width - 10, stats_y + 80)],
            radius=10,
            fill=COLORS["darker"] + (200,),
            outline=color + (100,),
            width=1
        )

        # Label
        draw.text((x + 10, stats_y + 10), label, fill=COLORS["light_gray"], font=stat_font)

        # Value
        draw.text((x + 10, stats_y + 35), value, fill=color, font=stat_value_font)

    # Achievements section
    achievements_y = 330
    achievements_font = get_font(16)
    achievements_text = f"Achievements: {achievements_unlocked}/{total_achievements}"
    draw.text((40, achievements_y), achievements_text, fill=COLORS["light_gray"], font=achievements_font)

    # Achievement progress bar
    ach_bar_x = 40
    ach_bar_y = achievements_y + 25
    ach_bar_width = 200
    ach_bar_height = 10

    add_rounded_rectangle(
        draw,
        [(ach_bar_x, ach_bar_y), (ach_bar_x + ach_bar_width, ach_bar_y + ach_bar_height)],
        radius=5,
        fill=COLORS["dark_gray"]
    )

    ach_progress = (achievements_unlocked / max(total_achievements, 1)) * 100
    ach_fill_width = int((ach_bar_width - 2) * (ach_progress / 100))
    if ach_fill_width > 3:
        add_rounded_rectangle(
            draw,
            [(ach_bar_x + 1, ach_bar_y + 1), (ach_bar_x + 1 + ach_fill_width, ach_bar_y + ach_bar_height - 1)],
            radius=4,
            fill=COLORS["warning"]
        )

    # Footer with branding
    footer_font = get_font(12)
    footer_text = "Gojo Bot • Profile Card"
    draw.text((width - 150, height - 25), footer_text, fill=COLORS["light_gray"], font=footer_font)

    return card


def image_to_bytes(image: Image.Image, format: str = "PNG") -> io.BytesIO:
    """Convert PIL Image to bytes buffer for Discord"""
    buffer = io.BytesIO()
    image.save(buffer, format=format)
    buffer.seek(0)
    return buffer
