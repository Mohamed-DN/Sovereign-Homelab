# Idee per il Futuro (Smart Working Estremo & Zero Trust)

Questo documento raccoglie concetti avanzati di architettura di rete e sicurezza discussi durante lo sviluppo dell'infrastruttura. Sono idee preziose per chi viaggia o lavora da remoto in condizioni di forte sorveglianza (es. paesi esteri, reti pubbliche o dispositivi aziendali blindati).

## 1. Split Tunneling vs Full Tunneling (Subnet Router vs Exit Node)

Tailscale/Headscale permette di decidere in modo chirurgico come instradare il traffico quando si è fuori casa (es. Egitto, hotel, aeroporti):

- **Modalità Subnet Router (Split Tunnel)**: L'impostazione base. Il traffico "pesante" (YouTube, Netflix) viaggia direttamente sulla rete locale veloce in cui ti trovi. Soltanto le richieste DNS (per bloccare le pubblicità) e le chiamate agli IP locali di casa (`192.168.1.x`) passano per la VPN. Vantaggio: Massima velocità, blocco ads globale.
- **Modalità Exit Node (Full Tunnel)**: Tutto il traffico del dispositivo viene infilato nel tunnel crittografato e sputato fuori dal router di casa in Italia. Vantaggio: Protezione assoluta contro Wi-Fi pubblici hackerati e bypass completo dei blocchi geografici (es. la Rai penserà che tu sia fisicamente in Italia). Si attiva con un tap dall'app.

## 2. VPN Site-to-Site (Il Santo Graal)

Invece di installare l'app Tailscale su ogni singolo dispositivo in una seconda casa all'estero (operazione impossibile per Smart TV o console), si può usare la tecnica "Site-to-Site":

1. Si installa un **Router da Viaggio (es. GL.iNet)** o un mini-PC in Egitto.
2. Si collega questo router al server Headscale italiano impostandolo come Subnet Router per la rete egiziana (`192.168.2.0/24`).
3. Risultato: Le due case si fondono. Chiunque si colleghi al Wi-Fi egiziano navigherà su internet tramite la linea egiziana, ma raggiungerà istantaneamente il server italiano digitando `192.168.1.50`, sfruttando l'AdGuard per bloccare le pubblicità in modo invisibile senza avere app installate.

## 3. Battere i software "Zero Trust" Aziendali (Es. Zscaler)

Se si usa un computer aziendale con software di sorveglianza/Zero Trust (come Zscaler), la semplice app VPN non basta per nascondere la propria posizione geografica (es. far credere all'azienda di essere a Milano mentre si è a Il Cairo). Zscaler legge le reti Wi-Fi circostanti (BSSID), il GPS e il fuso orario, e va spesso in conflitto con le schede di rete virtuali della VPN.

**La Tecnica del "Router Matrioska" (Invisibilità Hardware):**
1. **Vietato** installare Tailscale sul PC aziendale.
2. Si utilizza un router da viaggio (GL.iNet) configurato con Tailscale (collegato all'Exit Node italiano).
3. Si disabilita (o si spegne totalmente) la scheda Wi-Fi del computer aziendale.
4. Si collega il PC aziendale al router GL.iNet esclusivamente tramite **Cavo Ethernet (LAN)**.

**Effetto**: Il software aziendale non potrà "annusare" le reti Wi-Fi egiziane circostanti essendo il Wi-Fi spento. Vedrà solo un generico collegamento cablato Ethernet e, facendo un test dell'IP, risulterà a tutti gli effetti il tuo IP residenziale italiano. Il PC aziendale crederà fisicamente di essere attaccato al muro del tuo salotto in Italia.
