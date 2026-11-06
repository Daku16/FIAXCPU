"""Genera el icono de la aplicación (chip con pulso) en PNG e ICO."""
from pathlib import Path
from PIL import Image, ImageDraw

S = 1024
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
d.rounded_rectangle((40, 40, S - 40, S - 40), 210, fill=(17, 28, 51, 255))
for i in range(4):
    p = 312 + i * 133
    for box in ((p - 22, 130, p + 22, 300), (p - 22, S - 300, p + 22, S - 130),
                (130, p - 22, 300, p + 22), (S - 300, p - 22, S - 130, p + 22)):
        d.rounded_rectangle(box, 16, fill=(56, 189, 248, 255))
d.rounded_rectangle((240, 240, S - 240, S - 240), 80, fill=(37, 99, 235, 255))
d.line([(320, 530), (430, 530), (480, 400), (560, 640), (610, 530), (705, 530)],
       fill=(248, 250, 252, 255), width=44, joint="curve")
out = Path(__file__).parent
img.resize((512, 512), Image.LANCZOS).save(out / "icon.png")
img.save(out / "icon.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
