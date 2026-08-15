"""
Build standalone .exe using PyInstaller.
Usage: python build_exe.py
Output: dist/ETS2_Chat_Translator.exe
"""
import os
import shutil
import subprocess
import sys

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
MAIN = os.path.join(PROJECT_DIR, "main.py")
# Read version from config.py
import re
_config_path = os.path.join(PROJECT_DIR, "config.py")
_version_match = re.search(r'VERSION\s*=\s*"(v[\d.]+)"', open(_config_path, encoding="utf-8").read())
VERSION = _version_match.group(1) if _version_match else "v0.0.0"
NAME = f"ETS2-TruckersMP翻译器-{VERSION}"
ICON = os.path.join(PROJECT_DIR, "icon.ico")
ICON_SRC = os.path.join(PROJECT_DIR, "75daa7c795d2fdc7dad84ec6b0636ddd.jpg")


def build():
    # Convert PNG icon to ICO if needed
    if os.path.exists(ICON_SRC):
        _convert_icon()
    elif not os.path.exists(ICON):
        _generate_icon()

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--noconsole",
        "--name", NAME,
        "--icon", ICON,
        "--add-data", f"{ICON};.",
        "--add-data", f"{os.path.join(PROJECT_DIR, 'xintubiao.png')};.",
        "--hidden-import", "httpx",
        "--hidden-import", "chat_dictionary",
        "--hidden-import", "message_types",
        "--hidden-import", "win32_constants",
        "--hidden-import", "message_display",
        "--hidden-import", "hotkey_manager",
        "--hidden-import", "compose_sender",
        "--hidden-import", "input_sender",
        "--hidden-import", "tray_icon",
        "--clean",
        MAIN,
    ]

    print(f"[*] Building {NAME}.exe ...")
    subprocess.check_call(cmd)
    print(f"[*] Done: {os.path.join(PROJECT_DIR, 'dist', NAME + '.exe')}")


def _convert_icon():
    """Convert xintubiao.png to icon.ico for PyInstaller (high quality)."""
    try:
        from PIL import Image
        img = Image.open(ICON_SRC)
        # Generate high-quality resampled sizes
        sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
        resampled = []
        for w, h in sizes:
            # Use LANCZOS for sharp downscaling, keep smaller sizes crisp
            r = img.resize((w, h), Image.Resampling.LANCZOS)
            resampled.append(r)
        # Save first image with all sizes appended
        resampled[0].save(ICON, format="ICO", sizes=sizes,
                          append_images=resampled[1:])
        print(f"[*] Converted {ICON_SRC} -> {ICON} ({len(sizes)} sizes)")
    except Exception as e:
        print(f"[!] Could not convert icon: {e}")
        # Fallback: try to use PNG directly
        shutil.copy(ICON_SRC, ICON)


def _generate_icon():
    """Generate a simple .ico file using Pillow (fallback)."""
    try:
        from PIL import Image, ImageDraw
        img = Image.new("RGBA", (64, 64), (30, 30, 30, 255))
        draw = ImageDraw.Draw(img)
        draw.rounded_rectangle([4, 4, 60, 60], radius=12, fill=(86, 156, 214, 255))
        draw.text((16, 14), "T", fill="white")
        img.save(ICON, format="ICO")
        print(f"[*] Generated icon: {ICON}")
    except Exception as e:
        print(f"[!] Could not generate icon: {e}")


if __name__ == "__main__":
    build()
