# Runbook 04: Reverse Proxy e HTTPS (Nginx Proxy Manager)

Questo documento spiega come configurare Nginx Proxy Manager (NPM) per gestire il traffico in ingresso, esporre i servizi tramite nomi a dominio eleganti (es. `vpn.casa.net`) e soprattutto generare certificati di sicurezza HTTPS validi necessari per dispositivi rigidi come iOS.

## 1. Verificare la Porta 80
NPM ha bisogno assoluto della porta 80 e 443 per fare da "smistatore universale" per tutti i tuoi futuri servizi e reindirizzare automaticamente l'HTTP in HTTPS.
Fortunatamente, nella nostra configurazione AdGuard Home risponde sulla porta `3000` (e Headscale sulla `8080`), il che significa che la porta `80` è nativamente libera e pronta per essere assegnata a NPM senza causare alcun disservizio!

## 2. Aggiunta di NPM allo Stack Docker
Aggiungi queste directory:
```bash
mkdir -p /opt/core-network/npm/data
mkdir -p /opt/core-network/npm/letsencrypt
```

Aggiungi questo blocco al tuo `docker-compose.yml`:
```yaml
  npm:
    image: jc21/nginx-proxy-manager:latest
    container_name: npm
    ports:
      - "80:80"
      - "443:443"
      - "81:81"
    volumes:
      - ./npm/data:/data
      - ./npm/letsencrypt:/etc/letsencrypt
    restart: unless-stopped
```

Riavvia l'infrastruttura con `docker compose up -d`.
L'interfaccia web di NPM sarà disponibile su `http://192.168.1.50:81` (Default: `admin@example.com` / `changeme`).

## 3. Ottenere Certificati HTTPS (DuckDNS DNS-01 Challenge)
Invece di aprire le porte del router TIM verso internet, usiamo la sfida DNS.

1. In NPM, vai su **SSL Certificates** -> **Add SSL Certificate** -> **Let's Encrypt**.
2. **Domain Names**: Inserisci `*.tuonome.duckdns.org` (e premi Invio).
3. Email: la tua email.
4. Attiva **Use a DNS Challenge**.
5. **DNS Provider**: Scegli `DuckDNS`.
6. Nel campo `Credentials File Content` che appare sotto, sostituisci `your-duckdns-token` con il tuo token reale.
7. Attiva le spunte e premi **Save**.
In circa 60 secondi otterrai un certificato Wildcard HTTPS valido e riconosciuto in tutto il mondo!

## 4. Split-Brain DNS (Rewrites in AdGuard)
Per evitare che il traffico esca su internet per poi rientrare:
1. Apri AdGuard Home (`http://192.168.1.50:3000`).
2. Vai su **Filtri** -> **Riscriturre DNS** (DNS Rewrites).
3. Aggiungi: `*.tuonome.duckdns.org` -> `192.168.1.50`.
*(Tutte le richieste locali andranno dirette a NPM).*

## 5. Esporre i Servizi (Configurazione Specifica Headscale)
In NPM, vai su **Hosts** -> **Proxy Hosts** -> **Add Proxy Host**:
- **Domain Names**: `vpn.tuonome.duckdns.org`
- **Scheme**: `http`
- **Forward Hostname / IP**: `192.168.1.50`
- **Forward Port**: `8080` (Porta di Headscale)
- **ATTENZIONE**: Spunta obbligatoriamente l'opzione **Websockets Support**. Senza questa spunta, l'app mobile di Tailscale non riuscirà a connettersi.

Vai nel tab **SSL**, seleziona il certificato generato prima, e spunta `Force SSL`.

Vai nel tab **Advanced** e aggiungi questo codice nel riquadro *Custom Nginx Configuration* per spegnere il buffering (altrimenti l'app di Tailscale va in Timeout infinito):
```nginx
proxy_http_version 1.1;
proxy_set_header Upgrade $http_upgrade;
proxy_set_header Connection "upgrade";
proxy_buffering off;
proxy_read_timeout 86400s;
proxy_connect_timeout 86400s;
proxy_send_timeout 86400s;
```
- Salva.

Da questo momento, `https://vpn.tuonome.duckdns.org` è attivo, sicuro e pronto per configurare Headscale su iPhone!
