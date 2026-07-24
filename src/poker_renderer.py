"""Pillow renderer for the six-seat Discord Hold'em table."""

from __future__ import annotations

from functools import lru_cache
from io import BytesIO
from pathlib import Path
from typing import Mapping

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

from src.holdem import (
    FINISHED,
    FLOP,
    PREFLOP,
    RIVER,
    TURN,
    WAITING,
    Card,
    HoldemGame,
)


ROOT = Path(__file__).resolve().parents[1]
BACKGROUND_PATH = ROOT / "assets" / "images" / "poker_table.png"
DIVIDER_PATH = ROOT / "assets" / "images" / "poker_divider.png"
CARDS_PATH = ROOT / "ref" / "cards"
ROLE_ICONS_PATH = ROOT / "ref" / "icons" / "Casino"
FONT_PATHS = {
    "lino": ROOT / "docs" / "fonts" / "RDRLino.ttf",
    "gothica": ROOT / "docs" / "fonts" / "RDRGothica.ttf",
    "body": ROOT / "docs" / "fonts" / "DroidSerifPro.ttf",
}

WIDTH = 1152
HEIGHT = 864
CARD_SIZE = (48, 96)
BOARD_CARD_SIZE = (54, 108)
AVATAR_SIZE = 88

SEAT_CENTERS = {
    0: (576, 735),
    1: (232, 656),
    2: (232, 208),
    3: (576, 128),
    4: (920, 208),
    5: (920, 656),
}

STAGE_NAMES = {
    WAITING: "Ожидание игроков",
    PREFLOP: "Префлоп",
    FLOP: "Флоп",
    TURN: "Тёрн",
    RIVER: "Ривер",
    FINISHED: "Раздача завершена",
}

SUIT_FILE_NAMES = {
    "♠": "spades",
    "♥": "hearts",
    "♦": "diamonds",
    "♣": "clubs",
}


@lru_cache(maxsize=32)
def _font(size: int, family: str = "body"):
    try:
        return ImageFont.truetype(str(FONT_PATHS[family]), size)
    except OSError:
        return ImageFont.load_default()


@lru_cache(maxsize=1)
def _background() -> Image.Image:
    image = Image.open(BACKGROUND_PATH).convert("RGB")
    return ImageOps.fit(image, (WIDTH, HEIGHT), method=Image.Resampling.LANCZOS)


@lru_cache(maxsize=1)
def _divider() -> Image.Image:
    image = Image.open(DIVIDER_PATH).convert("RGBA")
    alpha = image.getchannel("A").point(lambda value: 0 if value < 10 else value)
    image.putalpha(alpha)
    alpha_box = alpha.getbbox()
    if alpha_box:
        image = image.crop(alpha_box)
    target_width = 320
    target_height = max(1, round(image.height * target_width / image.width))
    return image.resize((target_width, target_height), Image.Resampling.LANCZOS)


def _card_path(card: Card | None) -> Path:
    if card is None:
        return CARDS_PATH / "back.png"
    rank, suit = card
    return CARDS_PATH / f"{SUIT_FILE_NAMES[suit]}_{rank.lower()}.png"


@lru_cache(maxsize=160)
def _card_image(card: Card | None, size: tuple[int, int]) -> Image.Image:
    image = Image.open(_card_path(card)).convert("RGBA")
    return image.resize(size, Image.Resampling.LANCZOS)


@lru_cache(maxsize=8)
def _role_icon(name: str, size: int = 44) -> Image.Image:
    image = Image.open(ROLE_ICONS_PATH / f"{name}_icon.png").convert("RGBA")
    return image.resize((size, size), Image.Resampling.LANCZOS)


def _rounded_panel(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    *,
    fill=(12, 13, 11, 205),
    outline=(181, 137, 65, 230),
    width=2,
    radius=12,
) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def _fit_text(text: str, max_chars: int) -> str:
    text = str(text)
    return text if len(text) <= max_chars else text[: max_chars - 1] + "…"


def _text_center(
    draw: ImageDraw.ImageDraw,
    position: tuple[int, int],
    text: str,
    *,
    font,
    fill,
    stroke_width=0,
    stroke_fill=None,
) -> None:
    box = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
    x = int(position[0] - (box[0] + box[2]) / 2)
    y = int(position[1] - (box[1] + box[3]) / 2)
    draw.text(
        (x, y),
        text,
        font=font,
        fill=fill,
        stroke_width=stroke_width,
        stroke_fill=stroke_fill,
    )


def _text_top_center(
    draw: ImageDraw.ImageDraw,
    position: tuple[int, int],
    text: str,
    *,
    font,
    fill,
    stroke_width=0,
    stroke_fill=None,
) -> None:
    """Draw text with an exact visible top edge and horizontal center."""
    box = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
    x = int(position[0] - (box[0] + box[2]) / 2)
    y = int(position[1] - box[1])
    draw.text(
        (x, y),
        text,
        font=font,
        fill=fill,
        stroke_width=stroke_width,
        stroke_fill=stroke_fill,
    )


def _visible_player_action(action: str) -> str:
    """Hide redundant role labels because their icons are already rendered."""
    normalized = action.strip().casefold()
    hidden_prefixes = ("малый блайнд", "большой блайнд", "дилер")
    return "" if normalized.startswith(hidden_prefixes) else action


def _avatar(data: bytes | None, name: str) -> Image.Image:
    if data:
        try:
            source = Image.open(BytesIO(data)).convert("RGB")
            source = ImageOps.fit(
                source,
                (AVATAR_SIZE, AVATAR_SIZE),
                method=Image.Resampling.LANCZOS,
            )
        except (OSError, ValueError):
            source = Image.new("RGB", (AVATAR_SIZE, AVATAR_SIZE), (69, 62, 45))
    else:
        source = Image.new("RGB", (AVATAR_SIZE, AVATAR_SIZE), (69, 62, 45))

    mask = Image.new("L", (AVATAR_SIZE, AVATAR_SIZE), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, AVATAR_SIZE - 1, AVATAR_SIZE - 1), fill=255)
    result = Image.new("RGBA", (AVATAR_SIZE, AVATAR_SIZE), (0, 0, 0, 0))
    result.paste(source, (0, 0), mask)

    if not data:
        draw = ImageDraw.Draw(result)
        initial = (name.strip()[:1] or "?").upper()
        _text_center(
            draw,
            (AVATAR_SIZE // 2, AVATAR_SIZE // 2 - 2),
            initial,
            font=_font(38),
            fill=(239, 219, 169, 255),
        )
    return result


def _paste_card(
    canvas: Image.Image,
    card: Card | None,
    xy: tuple[int, int],
    *,
    size=CARD_SIZE,
    dim=False,
) -> None:
    image = _card_image(card, size).copy()
    if dim:
        alpha = image.getchannel("A")
        image = ImageEnhance.Brightness(image.convert("RGB")).enhance(0.42).convert("RGBA")
        image.putalpha(alpha.point(lambda value: int(value * 0.72)))
    shadow = Image.new("RGBA", (size[0] + 8, size[1] + 8), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle(
        (5, 5, size[0] + 4, size[1] + 4),
        radius=6,
        fill=(0, 0, 0, 105),
    )
    canvas.alpha_composite(shadow, (xy[0] - 4, xy[1] - 4))
    canvas.alpha_composite(image, xy)


def _paste_fan_card(
    canvas: Image.Image,
    card: Card | None,
    center: tuple[int, int],
    *,
    angle: float,
    size: tuple[int, int] = CARD_SIZE,
    dim: bool = False,
) -> None:
    """Paste a hole card rotated counter-clockwise into a left-facing fan."""
    image = _card_image(card, size).copy()
    if dim:
        alpha = image.getchannel("A")
        image = ImageEnhance.Brightness(image.convert("RGB")).enhance(0.42).convert("RGBA")
        image.putalpha(alpha.point(lambda value: int(value * 0.72)))

    padding = 12
    layer = Image.new(
        "RGBA",
        (image.width + padding * 2, image.height + padding * 2),
        (0, 0, 0, 0),
    )
    alpha = image.getchannel("A")
    shadow_alpha = alpha.filter(ImageFilter.GaussianBlur(3))
    shadow = Image.new("RGBA", image.size, (0, 0, 0, 0))
    shadow.putalpha(shadow_alpha.point(lambda value: int(value * 0.48)))
    layer.alpha_composite(shadow, (padding + 4, padding + 5))
    layer.alpha_composite(image, (padding, padding))
    rotated = layer.rotate(
        angle,
        resample=Image.Resampling.BICUBIC,
        expand=True,
    )
    canvas.alpha_composite(
        rotated,
        (
            int(center[0] - rotated.width / 2),
            int(center[1] - rotated.height / 2),
        ),
    )


def _role_icons(game: HoldemGame, index: int) -> list[str]:
    names = []
    if index == game.dealer_index:
        names.append("dealer")
    if index == game.small_blind_index:
        names.append("smallblind")
    if index == game.big_blind_index:
        names.append("bigblind")
    return names


def render_table(
    game: HoldemGame,
    avatar_bytes: Mapping[int, bytes] | None = None,
) -> BytesIO:
    """Render the public table. Hole cards stay hidden until showdown."""
    avatar_bytes = avatar_bytes or {}
    canvas = _background().copy().convert("RGBA")
    draw = ImageDraw.Draw(canvas, "RGBA")

    # Pot and street sit directly on the felt, separated by the supplied
    # ornament. Strong outlines keep both lines readable without a panel.
    _text_center(
        draw,
        (576, 330),
        f"БАНК   {game.pot}",
        font=_font(30, "lino"),
        fill=(245, 218, 146, 255),
        stroke_width=3,
        stroke_fill=(10, 7, 4, 240),
    )
    divider = _divider()
    divider_x = (WIDTH - divider.width) // 2
    divider_y = 349
    divider_shadow = Image.new("RGBA", divider.size, (0, 0, 0, 0))
    divider_shadow.putalpha(
        divider.getchannel("A")
        .filter(ImageFilter.GaussianBlur(2))
        .point(lambda value: int(value * 0.6))
    )
    canvas.alpha_composite(divider_shadow, (divider_x + 2, divider_y + 2))
    canvas.alpha_composite(divider, (divider_x, divider_y))
    _text_center(
        draw,
        (576, 390),
        STAGE_NAMES.get(game.stage, game.stage),
        font=_font(20, "gothica"),
        fill=(242, 229, 196, 255),
        stroke_width=3,
        stroke_fill=(10, 7, 4, 240),
    )

    board_start = 576 - ((BOARD_CARD_SIZE[0] * 5 + 9 * 4) // 2)
    board_y = 410
    for index in range(5):
        x = board_start + index * (BOARD_CARD_SIZE[0] + 9)
        if index < len(game.board):
            _paste_card(canvas, game.board[index], (x, board_y), size=BOARD_CARD_SIZE)
        else:
            draw.rounded_rectangle(
                (x, board_y, x + BOARD_CARD_SIZE[0], board_y + BOARD_CARD_SIZE[1]),
                radius=7,
                fill=(7, 33, 19, 90),
                outline=(199, 159, 79, 90),
                width=2,
            )

    reveal = game.stage == FINISHED and bool(game.showdown_results)
    for index, player in enumerate(game.players):
        center_x, center_y = SEAT_CENTERS.get(player.seat, SEAT_CENTERS[index])
        is_turn = game.current_index == index
        outline = (238, 192, 86, 255) if is_turn else (139, 105, 54, 225)

        # Cards sit well to the left and behind the avatar so the player's
        # face remains unobstructed while the hand still reads as a fan.
        if player.hole:
            show_cards = reveal and not player.folded
            fan_cards = player.hole if show_cards else [None, None]
            for card, card_center, angle in (
                (fan_cards[0], (center_x - 92, center_y + 8), 15),
                (fan_cards[1], (center_x - 58, center_y + 5), 6),
            ):
                _paste_fan_card(
                    canvas,
                    card,
                    card_center,
                    angle=angle,
                    dim=player.folded,
                )

        avatar = _avatar(avatar_bytes.get(player.user_id), player.name)
        if player.folded:
            alpha = avatar.getchannel("A")
            avatar = ImageEnhance.Brightness(avatar.convert("RGB")).enhance(0.35).convert("RGBA")
            avatar.putalpha(alpha)
        avatar_x = center_x - AVATAR_SIZE // 2
        avatar_y = center_y - 35
        if is_turn:
            for spread, alpha in ((8, 70), (5, 130)):
                draw.ellipse(
                    (
                        avatar_x - spread,
                        avatar_y - spread,
                        avatar_x + AVATAR_SIZE + spread,
                        avatar_y + AVATAR_SIZE + spread,
                    ),
                    outline=(244, 196, 82, alpha),
                    width=3,
                )
        canvas.alpha_composite(avatar, (avatar_x, avatar_y))
        draw.ellipse(
            (avatar_x - 2, avatar_y - 2, avatar_x + AVATAR_SIZE + 2, avatar_y + AVATAR_SIZE + 2),
            outline=outline,
            width=4 if is_turn else 3,
        )

        roles = _role_icons(game, index)
        if roles:
            icon_size = 44
            icon_x = center_x + 52
            icon_y = center_y - 59
            for offset, role in enumerate(roles):
                icon = _role_icon(role, icon_size)
                canvas.alpha_composite(
                    icon,
                    (icon_x + offset * 31, icon_y + offset * 3),
                )

        # Player labels have no panel: strong outlines preserve readability
        # over both the felt and the wooden rail.
        name = _fit_text(player.name, 16)
        _text_center(
            draw,
            (center_x, center_y - 65),
            name,
            font=_font(22, "lino"),
            fill=(247, 235, 204, 255),
            stroke_width=3,
            stroke_fill=(12, 9, 6, 245),
        )
        stack_text = f"{player.stack} фишек"
        if player.round_bet:
            stack_text += f"  ·  ставка {player.round_bet}"
        _text_top_center(
            draw,
            (center_x, avatar_y + AVATAR_SIZE + 7),
            stack_text,
            font=_font(15, "gothica"),
            fill=(224, 218, 200, 255),
            stroke_width=2,
            stroke_fill=(12, 9, 6, 245),
        )
        visible_action = _visible_player_action(player.last_action)
        if visible_action:
            _text_center(
                draw,
                (center_x, center_y + 101),
                _fit_text(visible_action, 24),
                font=_font(16, "gothica"),
                fill=(248, 198, 99, 255),
                stroke_width=2,
                stroke_fill=(10, 7, 5, 245),
            )

    if not game.players:
        _text_center(
            draw,
            (576, 620),
            "Нажмите «Сесть за стол»",
            font=_font(28, "lino"),
            fill=(242, 220, 164, 255),
            stroke_width=2,
            stroke_fill=(0, 0, 0, 210),
        )

    output = BytesIO()
    canvas.convert("RGB").save(output, format="JPEG", quality=88, optimize=True)
    output.seek(0)
    return output


def render_private_hand(game: HoldemGame, user_id: int) -> BytesIO:
    player = game.player_by_id(user_id)
    if player is None or not player.hole:
        raise ValueError("Player has no cards")

    canvas = Image.new("RGBA", (520, 300), (19, 54, 31, 255))
    draw = ImageDraw.Draw(canvas, "RGBA")
    draw.rounded_rectangle(
        (12, 12, 508, 288),
        radius=24,
        fill=(20, 68, 38, 255),
        outline=(195, 151, 75, 255),
        width=4,
    )
    _text_center(
        draw,
        (260, 48),
        _fit_text(player.name, 22),
        font=_font(28, "lino"),
        fill=(247, 232, 192, 255),
        stroke_width=2,
        stroke_fill=(8, 7, 5, 230),
    )
    private_size = (82, 164)
    _paste_fan_card(
        canvas,
        player.hole[0],
        (230, 161),
        angle=15,
        size=private_size,
    )
    _paste_fan_card(
        canvas,
        player.hole[1],
        (300, 154),
        angle=6,
        size=private_size,
    )
    _text_center(
        draw,
        (260, 267),
        game.combination_for(user_id),
        font=_font(21, "gothica"),
        fill=(246, 202, 101, 255),
        stroke_width=2,
        stroke_fill=(8, 7, 5, 230),
    )

    output = BytesIO()
    canvas.convert("RGB").save(output, format="JPEG", quality=90, optimize=True)
    output.seek(0)
    return output
