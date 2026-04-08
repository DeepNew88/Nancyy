import os
from io import BytesIO
import httpx
from PIL import (
    Image,
    ImageDraw,
    ImageEnhance,
    ImageFilter,
    ImageFont,
    ImageOps,
)

from anony import logger, config
from anony.helpers import Track


def load_fonts():
    try:
        return {
            "title": ImageFont.truetype("anony/helpers/Raleway-Bold.ttf", 35),
            "artist": ImageFont.truetype("anony/helpers/Inter-Light.ttf", 28),
            "small": ImageFont.truetype("anony/helpers/Inter-Light.ttf", 22),
        }
    except:
        return {
            "title": ImageFont.load_default(),
            "artist": ImageFont.load_default(),
            "small": ImageFont.load_default(),
        }


FONTS = load_fonts()


async def fetch_image(url: str) -> Image.Image:
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(url, timeout=6)
            r.raise_for_status()
            img = Image.open(BytesIO(r.content)).convert("RGBA")

            img = ImageOps.fit(
                img,
                (1280, 720),
                Image.Resampling.LANCZOS
            )

            return img

        except:
            return Image.new("RGBA", (1280, 720), (25, 18, 18, 255))


class Thumbnail:
    async def generate(self, song: Track) -> str:
        try:
            os.makedirs("cache", exist_ok=True)
            save_path = f"cache/{song.id}_final.png"

            thumb = await fetch_image(song.thumbnail)

            width, height = 1280, 720

            # ===== BACKGROUND =====
            bg = thumb.copy()
            bg = bg.filter(ImageFilter.GaussianBlur(18))
            bg = ImageEnhance.Brightness(bg).enhance(0.60)

            # ===== PANEL FRAME =====
            panel_margin_x = 260
            panel_margin_y = 100

            panel_x = panel_margin_x
            panel_y = panel_margin_y

            panel_w = width - (panel_margin_x * 2)
            panel_h = height - (panel_margin_y * 2)

            # ===== NATURAL GLASS EFFECT =====
            panel_area = bg.crop(
                (panel_x, panel_y, panel_x + panel_w, panel_y + panel_h)
            )

            panel_area = panel_area.filter(ImageFilter.GaussianBlur(10))
            panel_area = ImageEnhance.Brightness(panel_area).enhance(0.5)

            mask = Image.new("L", (panel_w, panel_h), 0)
            ImageDraw.Draw(mask).rounded_rectangle(
                (0, 0, panel_w, panel_h),
                radius=35,
                fill=255,
            )

            bg.paste(panel_area, (panel_x, panel_y), mask)

            draw = ImageDraw.Draw(bg)

            # ===== COVER =====
            cover = ImageOps.fit(
                thumb,
                (184, 184),
                Image.Resampling.LANCZOS
            )

            cover_mask = Image.new("L", (184, 184), 0)
            ImageDraw.Draw(cover_mask).rounded_rectangle(
                (0, 0, 184, 184),
                radius=25,
                fill=255
            )

            cover.putalpha(cover_mask)
            bg.paste(cover, (325, 155), cover)

            # ===== SMALL LABEL ABOVE TITLE =====
            draw.text(
                (520, 170),
                "Nancy Music",
                fill=(200, 200, 200),
                font=FONTS["small"],
            )

            # ===== TEXT =====
            title = (song.title or "Unknown Title")[:45]
            artist = (song.channel_name or "Unknown Artist")[:40]

            draw.text(
                (520, 205),
                title,
                fill="white",
                font=FONTS["title"],
            )

            draw.text(
                (520, 260),
                artist,
                fill=(210, 210, 210),
                font=FONTS["artist"],
            )

            # ===== CONTROLS =====
            try:
                controls = Image.open("anony/assets/controls.png").convert("RGBA")
                controls = controls.resize((600, 160), Image.Resampling.LANCZOS)

                bg.paste(
                    controls,
                    (335, 415),
                    controls,
                )
            except:
                pass

            # ===== REMOVE DASH FROM CONTROLS =====
            erase_x = 880
            erase_y = 430
            erase_w = 50
            erase_h = 25

            patch = bg.crop((erase_x, erase_y, erase_x + erase_w, erase_y + erase_h))
            patch = patch.filter(ImageFilter.GaussianBlur(30))
            bg.paste(patch, (erase_x, erase_y))

            # ===== END TIME (RIGHT SIDE ONLY) =====
            total_time = getattr(song, "duration", "3:25")

            time_y = 427
            text_width = draw.textlength(total_time, font=FONTS["small"])

            draw.text(
                (panel_x + panel_w - 100 - text_width, time_y),
                total_time,
                fill=(220, 220, 220),
                font=FONTS["small"],
            )

            bg.save(save_path, "PNG", quality=95)
            return save_path

        except Exception as e:
            logger.warning("Thumbnail generation failed: %s", e)
            return config.DEFAULT_THUMB
