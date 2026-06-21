# Create a Proxmox VM for Appliance or Critical Services

Use VMs for PBS, Immich, Nextcloud AIO, Home Assistant OS, Jellyfin, and Wazuh.

## Standard VM Sizes

| VM ID | Name | CPU | RAM | OS disk | Notes |
|---:|---|---:|---:|---:|---|
| 110 | `immich` | 6 | 16 GB | 120 GB | separate photo data mount |
| 120 | `nextcloud-aio` | 4 | 8-12 GB | 120 GB | separate data mount if used seriously |
| 130 | `home-assistant-os` | 2 | 4 GB | 64 GB | appliance VM |
| 140 | `pbs` | 4 | 8 GB | 64 GB | dedicated datastore |
| 150 | `jellyfin` | 4 | 8 GB | 80 GB | media mount; GPU optional |
| 160 | `wazuh` | 6-8 | 16 GB | 200 GB | optional later |

## Web UI Creation

1. Upload the ISO or appliance image to Proxmox.
2. Click **Create VM**.
3. Use the VM ID and name from the table.
4. Choose OVMF/UEFI only when the appliance requires it.
5. Use VirtIO SCSI and VirtIO network.
6. Set CPU type to `host` for heavy workloads such as Immich or Jellyfin.
7. Allocate disk on mirrored storage.
8. Install the OS.
9. Install QEMU guest agent when supported.

## CLI Pattern

Example Linux VM:

```bash
qm create 110 --name immich --memory 16384 --cores 6 --cpu host --net0 virtio,bridge=vmbr0
qm set 110 --scsihw virtio-scsi-pci --scsi0 local-lvm:120
qm set 110 --ide2 local:iso/debian-12.iso,media=cdrom
qm set 110 --boot order=scsi0
qm set 110 --agent enabled=1
```

Adjust storage names to match the Proxmox node.

## Data Disk Pattern

For critical data, keep OS and data separate:

```bash
qm set 110 --scsi1 local-lvm:900
```

Inside the VM:

```bash
lsblk
mkfs.ext4 /dev/sdb
mkdir -p /srv/immich
echo '/dev/sdb /srv/immich ext4 defaults,nofail 0 2' >> /etc/fstab
mount -a
```

Use stable UUIDs instead of `/dev/sdb` once the design is final.

## Backup Registration

Add each VM to a PBS backup job before production use. For data-heavy VMs, document whether PBS backs up the data disk, restic backs it up, or both.

---

**Previous:** [Create LXC Runbook](CREATE_LXC_RUNBOOK.md)
**Next:** [Storage Layout and Backup Boundaries](STORAGE_LAYOUT_AND_BACKUP_BOUNDARIES.md)
