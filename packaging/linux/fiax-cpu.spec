%global __os_install_post %{nil}
%global debug_package %{nil}
%global _build_id_links none
AutoReqProv: no

Name:           fiax-cpu
Version:        %{app_version}
Release:        1
Summary:        Diagnostico y mantenimiento del equipo
License:        Proprietary
BuildArch:      x86_64
Requires:       xdg-utils

%description
FIAX CPU diagnostica el equipo, aplica rutinas de mantenimiento y compara
el estado inicial con el final. No requiere Python ni Git.

%install
cp -a %{payload}/. %{buildroot}/

%files
/opt/fiax-cpu
/usr/bin/fiax-cpu
/usr/share/applications/fiax-cpu.desktop
/usr/share/icons/hicolor/512x512/apps/fiax-cpu.png
