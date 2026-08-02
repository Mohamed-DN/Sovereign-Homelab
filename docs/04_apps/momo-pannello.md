# Il pannello di Momo — le sette schede di casa dentro quello di hermes-agent

> **T8 del piano operativo.** Deciso dal proprietario il 2026-08-01, con le sue
> parole: *«fai una roba forte, prendi il loro e come un chirurgo lo apri e ci
> metti le nostre robe»*. E così è: nessuna riga del loro core è stata toccata
> per questo — il pannello ha un sistema di plugin a manifesto, ed è quello che
> si usa.

---

## 1. Purpose & architecture

Un pannello web per governare Momo: motori, modelli, fornitori, rotte,
memoria, rubrica e MASTER. Le stesse sette schede che l'Hermes vivo ha da
sempre, dentro il pannello di hermes-agent.

```
   browser
      │
      ▼
   momo-dashboard.service          LXC 102, 127.0.0.1:9119
   (hermes-agent, React + Vite)
      │
      ├── le loro pagine     config, sessioni, chiavi API, cron, MCP, skill
      │
      └── scheda "Sovrano"   plugin sovereign-console
             │                 ~/.hermes/plugins/sovereign-console/dashboard/
             │                    manifest.json · plugin_api.py · src/index.js
             ▼
          /api/plugins/sovereign-console/*     PONTE, non copia
             │
             ▼
          Hermes vivo  127.0.0.1:8093
```

**Il ponte non reimplementa niente.** Ogni scheda inoltra all'Hermes vivo, che
quegli endpoint li ha già e li serve da mesi. Una seconda implementazione
degli stessi dati divergerebbe dalla prima, e la divergenza sarebbe invisibile
finché una delle due non mostrasse un numero sbagliato — lo stesso
ragionamento del [Guardrail](momo-guardrail.md) e della
[memoria](hermes-memoria.md), un file solo letto da tutti.

Se Hermes non risponde, la scheda dice **«non raggiungibile»** e non si rompe:
`raggiungibile` è un campo della risposta, e vuol dire *«Hermes ha risposto»*,
non *«Hermes era d'accordo»*.

### 1.1 Le tre leve del loro sistema di plugin

Lette nel loro codice (`hermes_cli/web_server.py`), e nessuna tocca il core:

| Leva | Cosa fa | Usata qui |
|---|---|---|
| `tab.path` + `position` | aggiunge una scheda, posizionabile | ✅ `/sovrano`, dopo `config` |
| `tab.override` | **sostituisce** una loro pagina | no |
| `slots` | inietta pezzi in 31 punti della loro interfaccia | no |

## 2. Target & sizing

Un processo Python su **LXC 102**, in ascolto su `127.0.0.1:9119`. Il frontend
è statico, compilato una volta in `hermes_cli/web_dist/` (~2 MB); il ponte fa
una richiesta HTTP a `localhost:8093` per scheda aperta. Trascurabile.

**Node serve solo per compilare, non per far girare.** Il servizio parte con
`--skip-build`: dipendere da `npm` per avviare un pannello sarebbe fragile.

## 3. Install / deployment

```bash
# 1. Node 22 dal binario ufficiale (quello di Debian e' il 18, a fine vita e
#    troppo vecchio per Vite 8). In /opt, si toglie cancellando la cartella.
V=v22.14.0
curl -fsSL -o /tmp/node.tar.xz https://nodejs.org/dist/$V/node-$V-linux-x64.tar.xz
mkdir -p /opt/node && tar -xJf /tmp/node.tar.xz -C /opt/node --strip-components=1
ln -sf /opt/node/bin/node /usr/local/bin/node
ln -sf /opt/node/bin/npm  /usr/local/bin/npm

# 2. compilare il pannello (una volta sola)
export PATH=/opt/node/bin:$PATH
cd /opt/hermes-agent-study
npm install --workspace web --no-audit --no-fund
npm run build -w web            # scrive in hermes_cli/web_dist

# 3. il nostro plugin
mkdir -p /opt/momo/home/.hermes/plugins/sovereign-console
cp -r scripts/momo/dashboard /opt/momo/home/.hermes/plugins/sovereign-console/

# 4. abilitarlo in config.yaml -> plugins.enabled: - sovereign-console

# 5. il servizio
systemctl enable --now momo-dashboard
```

## 4. DNS / domain names / alias

`momo.internal` **risolve già** a 192.168.1.50 (NPM), per la riscrittura jolly
`*.internal` di AdGuard: non serve crearlo.

**Ma oggi non arriva a destinazione**, e il motivo è al §5.

## 5. Nginx Proxy Manager (NPM)

**Non ancora pubblicato, e c'è una ragione che non si aggira.**

Il pannello ascolta su `127.0.0.1`. Fuori dal loopback il loro codice
**pretende un provider di autenticazione e si rifiuta di partire**
(`should_require_auth()` in `web_server.py`: solo `127.0.0.1`, `localhost` e
`::1` sono esenti; RFC1918 è trattato come pubblico **di proposito**). Quindi
NPM su LXC 100 non può raggiungere LXC 102 finché non si sceglie come
autenticare.

Le due strade, e la prima è quella giusta per questa casa:

1. **OIDC verso Authentik** — hanno un provider che lo nomina esplicitamente
   (`plugins/dashboard_auth/self_hosted/`, cita Authentik e Keycloak). Un
   login solo: se la sessione Authentik c'è già, il passaggio è trasparente.
   Serve creare un'applicazione OIDC in Authentik e mettere
   `dashboard.oauth.self_hosted.{issuer, client_id}` in `config.yaml`.
2. **Password propria** (`dashboard.basic_auth`) — più veloce da mettere in
   piedi, ma è un secondo login e una seconda password da ricordare, in una
   casa che ha un SSO proprio apposta per non averne.

**Quello che NON si fa**: legare il pannello a `0.0.0.0` senza autenticazione
e affidarsi solo al forward-auth di NPM. Chiunque su LXC 102 lo raggiungerebbe
in chiaro, e il pannello comanda MASTER.

## 6. Homepage & Uptime Kuma

- **Homepage**: tessera da aggiungere **dopo** la pubblicazione (§5): una
  tessera che punta a un indirizzo che non risponde è peggio di nessuna.
- **Uptime Kuma**: monitor HTTP su `momo.internal`, sempre dopo il §5. Oggi
  il controllo utile è `systemctl is-active momo-dashboard`.

## 7. Backup & restore

**Nessuno stato proprio.** Il pannello legge e scrive attraverso l'Hermes vivo
e la configurazione di Momo, che hanno già il loro backup. Il `web_dist` è un
prodotto di compilazione: si rifà con `npm run build -w web`.

Il **codice** — manifesto, ponte, frontend — sta in `scripts/momo/dashboard/`
nel repository.

## 8. Rollback

```bash
systemctl disable --now momo-dashboard          # spegne solo il pannello
# togliere 'sovereign-console' da plugins.enabled  -> restano le loro pagine
rm -rf /opt/momo/home/.hermes/plugins/sovereign-console   # via del tutto
```
Momo continua a rispondere su Telegram in tutti e tre i casi: il pannello non
è sulla strada delle risposte.

## 9. Edge Cases — cosa succede se un passo va a metà

| Caso | Cosa succede |
|---|---|
| Hermes vivo spento | ogni scheda dice «non raggiungibile» con il motivo; il pannello resta in piedi |
| `web_dist` assente | il servizio parte ma serve un 404 JSON con scritto come compilare; le API funzionano lo stesso |
| Il plugin non è in `plugins.enabled` | né il manifesto, né gli asset, né le rotte vengono serviti: silenzio totale, ed è voluto |
| Node tolto dopo la compilazione | **il pannello continua a funzionare**: `--skip-build` non lo usa |
| Aggiornamento di hermes-agent | il `web_dist` va ricompilato; il nostro plugin no, vive fuori dal loro albero |
| Due processi sulla 9119 | il secondo non parte; `systemctl status momo-dashboard` lo dice |

## 10. Troubleshooting

| Problema | Causa probabile | Rimedio |
|---|---|---|
| `401` su ogni rotta chiamata con `curl` | **non è un difetto.** In loopback il pannello usa un token di sessione **iniettato nella pagina HTML** (`window.__HERMES_SESSION_TOKEN__`): il browser ce l'ha, `curl` no | leggere il token dalla pagina e passarlo come `Authorization: Bearer <token>` |
| `404` su una rotta del ponte | le rotte sono in **inglese** come quelle di Hermes (`backends`, `memory/status`, `master/status`), non in italiano | `grep '@router' plugin_api.py` |
| Il pannello muore dopo il logout | era avviato a mano invece che dal servizio | `systemctl enable --now momo-dashboard` |
| La scheda «Sovrano» non compare | plugin non abilitato, o bundle non servito | `curl -s localhost:9119/api/dashboard/plugins` |
| Il build fallisce | Node troppo vecchio (Vite 8 vuole 20+) | `/opt/node/bin/node --version` |

## 11. Verifica di funzionamento

```bash
systemctl is-active momo-dashboard
curl -s localhost:9119/api/health          # {"ok":true,...}

# le sette schede, con il token preso dalla pagina
T=$(curl -s localhost:9119/ | grep -o '__HERMES_SESSION_TOKEN__[^;]*' \
      | head -1 | sed 's/.*=//; s/["'"'"' ]//g')
B=http://127.0.0.1:9119/api/plugins/sovereign-console
for r in health backends models/catalog providers/presets \
         routes memory/status contacts master/status; do
  printf '%-20s ' "$r"
  curl -s -o /dev/null -w 'HTTP %{http_code}\n' -H "Authorization: Bearer $T" "$B/$r"
done
# atteso: 200 su tutte e otto (verificato il 2026-08-02)
```

## 12. Official Sources

- Codice loro letto: `hermes_cli/web_server.py` (discovery dei plugin, mount delle rotte, `should_require_auth`, iniezione del token nella SPA), `web/src/plugins/` (registry e SDK), `plugins/dashboard_auth/self_hosted/` (OIDC verso Authentik)
- Esempi da cui è copiata la forma: `plugins/kanban/dashboard/`, `plugins/hermes-achievements/dashboard/`
- [PIANO_AGENT_MOMO](../00_overview/PIANO_AGENT_MOMO.md) §3 — la regola sul fork minimo e sul registro delle divergenze
- [momo-telegram.md](momo-telegram.md) — l'altro canale di Momo
- [hermes.md](hermes.md) §7-octies — le sette schede originali, di cui questo è il ponte
