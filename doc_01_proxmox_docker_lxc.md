# Runbook 01: Creazione Base LXC e Installazione Docker su Proxmox

Questo documento serve come guida di riferimento (runbook) per ricreare da zero l'ambiente di base del tuo server su Proxmox.

## 1. Creazione del Container LXC
Dall'interfaccia grafica di Proxmox:
1. Scaricare il template `debian-12-standard` da `CT Templates`.
2. Cliccare su **Create CT** in alto a destra.
3. **General**: 
   - Scegliere un ID (es. 100) e un Hostname (es. `core-network`).
   - ⚠️ **Fondamentale**: Spuntare la casella `Unprivileged container`.
4. **Template**: Selezionare Debian 12.
5. **Disks**: Assegnare 15 GiB.
6. **CPU / Memory**: 2 Core, 1024 MiB RAM, 512 MiB Swap.
7. **Network**: 
   - Disabilitare il Firewall.
   - IPv4: Statico (es. `192.168.1.50/24`).
   - Gateway: IP del Router (es. `192.168.1.1`).
   - IPv6: Statico, ma lasciare i campi vuoti.

## 2. Abilitazione Funzionalità di Sistema
Prima di avviare il container, configurare i permessi speciali necessari per Docker e per la VPN.

### 2a. Nesting (Per Docker)
Dall'interfaccia web di Proxmox:
- Selezionare il container appena creato.
- Andare su **Options** -> **Features**.
- Spuntare la casella **Nesting** e salvare.

### 2b. TUN Device (Per Headscale/Tailscale)
Aprire la **Shell dell'host Proxmox** (non del container) e modificare il file di configurazione dell'LXC (sostituire `100` con l'ID corretto):
```bash
nano /etc/pve/lxc/100.conf
```
Aggiungere in fondo queste due righe:
```text
lxc.cgroup2.devices.allow: c 10:200 rwm
lxc.mount.entry: /dev/net/tun dev/net/tun none bind,create=file
```
Salvare (Ctrl+O) ed uscire (Ctrl+X).

## 3. Installazione di Docker
Avviare il container, entrare nella sua **Console** (con utente `root` e la password scelta) ed eseguire:

```bash
# Aggiornamento sistema e dipendenze
apt update && apt upgrade -y
apt install -y curl git nano

# Installazione automatizzata di Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
```

A questo punto il container è pronto ad ospitare qualsiasi servizio.
