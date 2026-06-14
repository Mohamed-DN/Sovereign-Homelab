# Guida Completa e Definitiva a Headscale (VPN Mesh)

Headscale è il "direttore d'orchestra" della tua rete privata. Non sposta i dati, ma gestisce le "chiavi" di sicurezza. I dispositivi usano l'app **Tailscale** per collegarsi, ma noi li forziamo a parlare con il tuo **Headscale personale** invece che con i server commerciali di Tailscale.

## Fase A: Configurazione e Setup (Da fare solo la prima volta)

Prima di tutto, assicurati che il file `/opt/core-network/headscale/config/config.yaml` abbia l'URL corretto. **Attenzione**: il `server_url` deve essere fin da subito il nome a dominio HTTPS pubblico (e non l'IP locale), altrimenti l'app mobile darà errori di connessione e andrà in timeout.
- `server_url: https://vpn.tuonome.duckdns.org` (Usa rigorosamente `https://` senza specificare la porta 8080).
- `listen_addr: 0.0.0.0:8080` (Per permettere a Nginx di passargli il traffico)
- `metrics_listen_addr: 0.0.0.0:9090` (Aperto verso la LAN)
*(Se modifichi questo file, ricordati di riavviare con `docker restart headscale`).*

Sul terminale di **Proxmox** (LXC 100), crea il tuo "utente" o "spazio di lavoro":
```bash
docker exec headscale headscale users create casa
*(Puoi vedere la lista degli utenti e il loro ID numerico con `docker exec headscale headscale users list`)*
```
*(Da questo momento, l'utente `casa` è pronto ad accogliere i dispositivi).*

---

## Fase A.2: Configurazione MagicDNS (Integrazione con AdGuard)
Per far sì che i dispositivi connessi in 4G sfruttino il blocco pubblicità di AdGuard, devi forzare il server DNS tramite Headscale.

Apri il file `/opt/core-network/headscale/config/config.yaml` e cerca la sezione `dns:`.
Impostala in questo modo, cancellando i vecchi IP pubblici sotto `global` e inserendo quello di AdGuard:
```yaml
dns:
  magic_dns: true
  base_domain: casa.net
  nameservers:
    global:
      - 192.168.1.50
  override_local_dns: true
```
Salva il file e riavvia il server: `docker restart headscale`.
*(Ora tutti i dispositivi Tailscale riceveranno AdGuard come DNS)*.

---

## Fase B: Aggiungere PC e Mac

### Su Windows (Metodo Infallibile con Pre-Auth Key)
L'app di Windows spesso va in conflitto con l'interfaccia web per i server custom. Il metodo migliore è generare una chiave sul server e forzare la connessione.
1. Scarica e installa l'app ufficiale di Tailscale per Windows.
   *(Nota: nelle nuove versioni di Headscale devi usare il NUMERO dell'utente, di solito `1`. Controlla il numero con `docker exec headscale headscale users list` prima di lanciare il comando)*:
   ```bash
   docker exec headscale headscale preauthkeys create -u 1 --reusable --expiration 24h
   ```
3. Su Windows, apri **PowerShell come amministratore** ed esegui:
   ```powershell
   tailscale up --login-server http://192.168.1.50:8080 --authkey INCOLLA_QUI_LA_CHIAVE --force-reauth
   ```
*(In alternativa, puoi cambiare server tenendo premuto SHIFT e cliccando col tasto destro sull'icona di Tailscale, poi `Preferences` -> `Custom Login Server`. Dopodiché, completi il login da browser e usi la nodekey come descritto per Mac/Linux).*

### Su Linux / Mac (via terminale)
1. Installa Tailscale (su Mac scaricalo dall'App Store, su Linux usa lo script `curl -fsSL https://tailscale.com/install.sh | sh`).
2. Apri il terminale ed esegui:
   ```bash
   sudo tailscale up --login-server http://192.168.1.50:8080
   ```
3. Come su Windows, copia la `nodekey` generata.

### Approvare i PC sul Server
Torna nel terminale di **Proxmox** (LXC 100) ed esegui questo comando per accettare il dispositivo:
```bash
docker exec headscale headscale nodes register -u 1 --key INCOLLA_QUI_LA_NODEKEY
```
*Il tuo PC è ora nella rete!*

---

## Fase C: Aggiungere Dispositivi Mobile (iOS e Android)
Le app mobile di Tailscale non hanno il terminale, quindi bisogna usare un "trucco" per far apparire il menu segreto in cui cambiare il server. Assicurati che il telefono sia connesso al Wi-Fi di casa la prima volta.

### Su Android
1. Scarica **Tailscale** dal Play Store e aprila.
2. Tocca i **tre puntini** in alto a destra.
3. Seleziona **Change Server** (Cambia server).
4. Inserisci `http://192.168.1.50:8080` e salva.
5. Tocca **Sign in**. Il browser del telefono si aprirà e ti mostrerà il comando esatto con la tua `nodekey` da incollare su Proxmox.

### Su iPhone / iPad (iOS) - Metodo NovaAccess (Consigliato)
L'app ufficiale di Tailscale ha spesso bug noti con l'aggiunta di server custom via reverse proxy. L'approccio migliore e più stabile è usare un'app indipendente.
1. Scarica **NovaAccess** dall'App Store (supporta nativamente server custom come Headscale).
2. Genera una chiave direttamente dal server Proxmox: `docker exec headscale headscale preauthkeys create -u 1 --reusable --expiration 24h`
3. Apri NovaAccess, inserisci l'URL pubblico di Nginx (es. `https://vpn.tuonome.duckdns.org`) come *Control URL*.
4. Incolla la chiave generata nel campo *Auth Key*.
5. Clicca su **Login to Tailnet**. Sarai connesso all'istante, bypassando del tutto i menu buggati dell'app ufficiale e l'uso del browser!

### Su iPhone / iPad (iOS) - Metodo Ufficiale Tailscale
1. Scarica **Tailscale** dall'App Store e aprila.
2. Tocca l'icona dell'utente in alto a destra, poi i 3 puntini, e seleziona **Use Custom Coordination Server**.
3. Inserisci il dominio completo: `https://vpn.tuonome.duckdns.org`.
4. Effettua il login normale: se Nginx è configurato correttamente con i WebSockets e il buffering spento (vedi Runbook 04), si aprirà Safari fornendoti la `nodekey` da incollare su Proxmox.

### Approvare gli Smartphone sul Server
Torna nel terminale di **Proxmox** (LXC 100) e accetta il telefono:
```bash
docker exec headscale headscale nodes register -u 1 --key INCOLLA_QUI_LA_NODEKEY_DEL_TELEFONO
```

---

## Fase D: Comandi Utili per il Server

Per vedere tutti i dispositivi connessi e i loro indirizzi IP "privati":
```bash
docker exec headscale headscale nodes list
```

Per cancellare un dispositivo (es. un vecchio telefono):
```bash
docker exec headscale headscale nodes delete -i [ID_DEL_DISPOSITIVO]
```
