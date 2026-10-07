#!/bin/sh
# TrackFlow host hardening example.
# This script does not run unless an operator sets
# TRACKFLOW_CONFIRM_SERVER_HARDENING=yes on the target machine.
# It is not evidence that a production server was changed.

set -eu

if [ "${TRACKFLOW_CONFIRM_SERVER_HARDENING:-}" != "yes" ]; then
  echo "Refusing to run. Set TRACKFLOW_CONFIRM_SERVER_HARDENING=yes on the target server." >&2
  exit 1
fi

echo "Review docs/security/server-hardening.md and apply sshd, permissions, and firewall there."
echo "This script does not change sshd or the firewall by itself."
