# Runbook 02: Deploy e Configurazione di AdGuard Home

Questo documento descrive i passaggi per distribuire il server DNS AdGuard Home tramite Docker all'interno del container di rete.

## 1. Struttura delle Directory e Docker Compose
All'interno del container `core-network` (es. `192.168.1.50`), creare le directory per i dati persistenti:
```bash
mkdir -p /opt/core-network/adguard/work
mkdir -p /opt/core-network/adguard/conf
cd /opt/core-network
```

Il servizio AdGuard Home è definito all'interno del file `docker-compose.yml` (insieme a Headscale). Per consentire ad AdGuard di intercettare le richieste di Broadcast DHCP dalla rete fisica, è stato legato direttamente all'interfaccia host:
```yaml
  adguardhome:
    image: adguard/adguardhome:latest
    container_name: adguardhome
    network_mode: "host"
    volumes:
      - ./adguard/work:/opt/adguardhome/work
      - ./adguard/conf:/opt/adguardhome/conf
    restart: unless-stopped
```

Avviare lo stack con:
```bash
docker compose up -d
```

## 2. Inizializzazione (Primo Avvio)
1. Aprire il browser da un PC nella stessa LAN e navigare verso `http://192.168.1.50:3000`.
2. Seguire il wizard guidato:
   - **Interfaccia Web**: Impostare o confermare l'ascolto sulla porta `80`.
   - **Server DNS**: Impostare o confermare l'ascolto sulla porta `53`.
3. Creare un account Amministratore (Username e Password).
4. Completare il setup. Da questo momento, la porta 3000 si chiuderà e l'interfaccia sarà raggiungibile direttamente su `http://192.168.1.50`.

## 3. Configurazione Centralizzata del DHCP
Per avere il controllo totale sui dispositivi e risolvere i nomi locali, il DHCP del router TIM è stato disattivato in favore del server DHCP integrato in AdGuard Home.

**Sul Router TIM (ZTE Gateway - 192.168.1.1):**
- Server DHCP: Impostato su `[Off]` per evitare conflitti (Dual DHCP sulla stessa subnet).

**Su AdGuard Home (192.168.1.50):**
- Server DHCP: `Abilitato`
- Range IP Dinamici (Assegnati da AdGuard): `192.168.1.100` - `192.168.1.200`
- Pool Statico Libero (Riservato ai server): `192.168.1.2` - `192.168.1.99`
- Lease Time: `24 ore (86400 secondi)`

*In questo modo, ogni nuovo dispositivo che si connette al Wi-Fi richiede un IP ad AdGuard, che glielo fornisce assegnando se stesso come Server DNS primario autorevole.*
