#!/usr/bin/env bash
# Install (or --uninstall) the MK3 hotplug user service for a desktop or
# headless x86-64 host. Runs without sudo; prints the one privileged step
# (installing the udev rule) when it is still needed.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
UNIT="$UNIT_DIR/machinista.service"
RULE_SRC="$ROOT/deploy/desktop/71-machinista-mk3-desktop.rules"
RULE_DST="/etc/udev/rules.d/71-machinista-mk3-desktop.rules"

if [[ "${1:-}" == "--rule" ]]; then
  sudo cp "$RULE_SRC" "$RULE_DST"
  sudo udevadm control --reload
  echo "Installed $RULE_DST. Unplug and replug the MK3 to start the service."
  exit 0
fi

if [[ "${1:-}" == "--uninstall" ]]; then
  systemctl --user stop machinista.service 2>/dev/null || true
  rm -f "$UNIT"
  systemctl --user daemon-reload
  echo "Removed $UNIT"
  if [[ -e "$RULE_DST" ]]; then
    echo "To remove the udev rule run:"
    echo "  sudo rm $RULE_DST && sudo udevadm control --reload"
  fi
  echo "Linger was left as is; disable with: loginctl disable-linger $USER"
  exit 0
fi

if [[ ! -x "$ROOT/build/audio_engine" ]]; then
  echo "Native build missing: run tools/run_desktop.sh once (Ctrl-C after it starts) first." >&2
  exit 1
fi

mkdir -p "$UNIT_DIR"
sed "s#@ROOT@#$ROOT#g" "$ROOT/deploy/desktop/machinista.service" > "$UNIT"
systemctl --user daemon-reload
echo "Installed $UNIT"

# Keep the user manager running without a login so hotplug works after boot.
if [[ "$(loginctl show-user "$USER" -p Linger --value)" != yes ]]; then
  loginctl enable-linger "$USER"
fi
echo "Linger: $(loginctl show-user "$USER" -p Linger --value)"

if ! cmp -s "$RULE_SRC" "$RULE_DST"; then
  echo
  echo "One privileged step remains. Install the udev rule with:"
  echo "  $0 --rule"
  echo "Then unplug and replug the MK3 (or reboot) to start the service."
else
  echo "udev rule already installed."
fi
