#!/usr/bin/env bash
# Genera dist/fiax-cpu_<versión>_amd64.deb y dist/fiax-cpu-<versión>-1.x86_64.rpm
set -euo pipefail
cd "$(dirname "$0")/.."

PYTHON="${PYTHON:-python3}"
VERSION="$("$PYTHON" -c 'from config import Config; print(Config.APP_VERSION)')"
"$PYTHON" -m PyInstaller --noconfirm --clean --distpath dist --workpath build packaging/fiax.spec

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
PAYLOAD="$STAGE/payload"
install -d "$PAYLOAD/opt" "$PAYLOAD/usr/bin" "$PAYLOAD/usr/share/applications" "$PAYLOAD/usr/share/icons/hicolor/512x512/apps"
cp -a dist/fiax-cpu "$PAYLOAD/opt/fiax-cpu"
ln -s /opt/fiax-cpu/fiax-cpu "$PAYLOAD/usr/bin/fiax-cpu"
install -m 644 packaging/linux/fiax-cpu.desktop "$PAYLOAD/usr/share/applications/"
install -m 644 packaging/icon.png "$PAYLOAD/usr/share/icons/hicolor/512x512/apps/fiax-cpu.png"

# .deb
DEB="$STAGE/deb"
cp -a "$PAYLOAD" "$DEB"
install -d "$DEB/DEBIAN"
cat > "$DEB/DEBIAN/control" <<EOF
Package: fiax-cpu
Version: $VERSION
Section: utils
Priority: optional
Architecture: amd64
Depends: xdg-utils
Installed-Size: $(du -sk "$PAYLOAD" | cut -f1)
Maintainer: Equipo FIAX CPU <soporte@fiax.invalid>
Description: Diagnostico y mantenimiento del equipo
 Diagnostica el equipo, aplica rutinas de mantenimiento y compara el estado
 inicial con el final. No requiere Python ni Git.
EOF
dpkg-deb --root-owner-group --build "$DEB" "dist/fiax-cpu_${VERSION}_amd64.deb"

# .rpm
RPM_TOP="$STAGE/rpm"
rpmbuild -bb packaging/linux/fiax-cpu.spec \
  --define "_topdir $RPM_TOP" \
  --define "app_version $VERSION" \
  --define "payload $PAYLOAD" \
  --define "_rpmdir $RPM_TOP/out"
cp "$RPM_TOP"/out/x86_64/*.rpm dist/

ls -lh dist/*.deb dist/*.rpm
