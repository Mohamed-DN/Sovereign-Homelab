#!/usr/bin/env bash
set -euo pipefail

root_ca="${1:-/var/lib/docker/volumes/internal-ca_step_ca_data/_data/certs/root_ca.crt}"
base_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
output_dir="$base_dir/site/downloads"

if [[ ! -s "$root_ca" ]]; then
  echo "root CA certificate not found: $root_ca" >&2
  exit 1
fi

mkdir -p "$output_dir"
rm -f \
  "$output_dir/sovereign-root-ca.crt" \
  "$output_dir/sovereign-root-ca.cer" \
  "$output_dir/fingerprint.txt" \
  "$output_dir/install-windows.ps1" \
  "$output_dir/sovereign-homelab-ca.mobileconfig"

install -m 0644 "$root_ca" "$output_dir/sovereign-root-ca.crt"
openssl x509 -in "$root_ca" -outform DER -out "$output_dir/sovereign-root-ca.cer"

thumbprint="$(openssl x509 -in "$root_ca" -noout -fingerprint -sha256 | cut -d= -f2 | tr -d ':')"
subject="$(openssl x509 -in "$root_ca" -noout -subject -nameopt RFC2253 | sed 's/^subject=//')"
printf 'SHA-256: %s\nSubject: %s\n' "$thumbprint" "$subject" > "$output_dir/fingerprint.txt"

sed "s/__ROOT_THUMBPRINT__/$thumbprint/g" \
  "$base_dir/install-windows.ps1.template" > "$output_dir/install-windows.ps1"

profile_uuid="$(cat /proc/sys/kernel/random/uuid | tr '[:lower:]' '[:upper:]')"
payload_uuid="$(cat /proc/sys/kernel/random/uuid | tr '[:lower:]' '[:upper:]')"
certificate_data="$(base64 -w 0 "$output_dir/sovereign-root-ca.cer")"

cat > "$output_dir/sovereign-homelab-ca.mobileconfig" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>PayloadContent</key>
  <array>
    <dict>
      <key>PayloadCertificateFileName</key><string>sovereign-root-ca.cer</string>
      <key>PayloadContent</key><data>${certificate_data}</data>
      <key>PayloadDescription</key><string>Installs the Sovereign Homelab private root CA.</string>
      <key>PayloadDisplayName</key><string>Sovereign Homelab Root CA</string>
      <key>PayloadIdentifier</key><string>org.sovereign.homelab.ca.root</string>
      <key>PayloadType</key><string>com.apple.security.root</string>
      <key>PayloadUUID</key><string>${payload_uuid}</string>
      <key>PayloadVersion</key><integer>1</integer>
    </dict>
  </array>
  <key>PayloadDescription</key><string>Private HTTPS trust for .internal services. Install only from LAN or the homelab VPN.</string>
  <key>PayloadDisplayName</key><string>Sovereign Homelab HTTPS Trust</string>
  <key>PayloadIdentifier</key><string>org.sovereign.homelab.ca</string>
  <key>PayloadOrganization</key><string>Sovereign Homelab</string>
  <key>PayloadRemovalDisallowed</key><false/>
  <key>PayloadType</key><string>Configuration</string>
  <key>PayloadUUID</key><string>${profile_uuid}</string>
  <key>PayloadVersion</key><integer>1</integer>
</dict>
</plist>
EOF

chmod 0644 "$output_dir"/*

if find "$output_dir" -maxdepth 1 -type f \( -iname '*key*' -o -iname '*password*' -o -iname '*secret*' \) | grep -q .; then
  echo "unsafe filename detected in trust portal output" >&2
  exit 1
fi

echo "trust portal artifacts rendered"
