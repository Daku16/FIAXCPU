# -*- mode: python ; coding: utf-8 -*-
# Windows genera un único .exe; Linux una carpeta que luego va dentro del .deb y el .rpm.
import os
import sys

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
ONEFILE = sys.platform == "win32"

a = Analysis(
    [os.path.join(ROOT, "fiax_launcher.py")],
    pathex=[ROOT],
    datas=[(os.path.join(ROOT, "templates"), "templates"), (os.path.join(ROOT, "static"), "static")],
    hiddenimports=["sqlalchemy.dialects.sqlite"],
    excludes=["tkinter", "unittest", "pytest"],
)
pyz = PYZ(a.pure)

common = dict(
    name="FIAX-CPU" if ONEFILE else "fiax-cpu",
    console=True,
    icon=os.path.join(SPECPATH, "icon.ico"),
    upx=False,
    strip=False,
)

if ONEFILE:
    exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], **common)
else:
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, **common)
    coll = COLLECT(exe, a.binaries, a.datas, name="fiax-cpu", upx=False, strip=False)
