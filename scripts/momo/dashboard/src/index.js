/*
 * Sovereign console - dashboard plugin frontend for hermes-agent.
 *
 * WHY THIS FILE IS PLAIN JS AND NOT JSX
 * -------------------------------------
 * LXC 102 has no node and no npm, and the dashboard's own web_dist has never
 * been built there. A plugin whose only shipping form is "run a bundler
 * first" is a plugin that cannot be installed on the machine it was written
 * for. So this is hand-authored ES2017 using React.createElement - exactly
 * the shape a bundler would have emitted anyway (compare the achievements
 * plugin's dist/index.js, which is hand-maintained in the same form) - and
 * manifest.json points `entry` straight at it. There is no build step, and
 * `node --check` is the whole verification story. See README.md if you ever
 * want to move to JSX + esbuild.
 *
 * WHAT IT TALKS TO
 * ----------------
 * Nothing directly. Every call goes to /api/plugins/sovereign-console, the
 * bridge in plugin_api.py, which forwards to the live household assistant.
 * React, the design-system components and the authenticated fetch helpers all
 * arrive on `window` from the host - this bundle imports nothing.
 *
 * Comments are English by house rule; everything the reader sees is Italian.
 */

(function () {
  "use strict";

  var SDK = window.__HERMES_PLUGIN_SDK__;
  if (!SDK || !window.__HERMES_PLUGINS__) return;

  var React = SDK.React;
  var h = React.createElement;
  var F = React.Fragment;

  var hooks = SDK.hooks;
  var useState = hooks.useState;
  var useEffect = hooks.useEffect;
  var useCallback = hooks.useCallback;
  var useMemo = hooks.useMemo;

  var fetchJSON = SDK.fetchJSON;
  var authedFetch = SDK.authedFetch;

  var BASE = "/api/plugins/sovereign-console";

  // -------------------------------------------------------------------------
  // Design system, defensively
  // -------------------------------------------------------------------------
  // The host exposes a component map, but which entries exist depends on its
  // version. Resolve each one with a plain-element fallback so an older host
  // renders a slightly plainer page instead of a blank one: a missing Badge
  // must not cost the household its MASTER switch.

  var C = SDK.components || {};
  function ds(name, fallback) {
    return C[name] || fallback;
  }
  var Card = ds("Card", "div");
  var CardContent = ds("CardContent", "div");
  var Badge = ds("Badge", "span");
  var Button = ds("Button", "button");
  var Input = ds("Input", "input");

  function cx() {
    return Array.prototype.slice.call(arguments).filter(Boolean).join(" ");
  }

  // -------------------------------------------------------------------------
  // Transport
  // -------------------------------------------------------------------------

  /** Turn a thrown fetchJSON error into something worth reading. */
  function motivo(err) {
    var msg = (err && err.message) || String(err);
    if (msg.indexOf("404") === 0) {
      return "Il ponte del plugin non risponde (404). Controlla che " +
        "sovereign-console sia in plugins.enabled e che il pannello sia " +
        "stato riavviato dopo l'installazione.";
    }
    if (msg.indexOf("401") === 0 || msg.indexOf("403") === 0) {
      return "Il pannello ha rifiutato la richiesta (" + msg.split(":")[0] +
        "): sessione scaduta?";
    }
    return "Errore verso il ponte: " + msg;
  }

  function leggi(path) {
    return fetchJSON(BASE + path);
  }

  function scrivi(path, corpo) {
    return fetchJSON(BASE + path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(corpo || {})
    });
  }

  /**
   * Collapse the bridge envelope into {ok, testo}.
   *
   * The bridge answers 200 even when the assistant is down, so "unreachable"
   * and "refused" are two different sentences here instead of one generic
   * failure.
   */
  function esito(r) {
    if (!r) return { ok: false, testo: "risposta vuota" };
    if (!r.raggiungibile) return { ok: false, testo: r.errore || "Hermes non raggiungibile" };
    var d = r.dati || {};
    var testo = d.message || d.error || (r.ok ? "fatto" : "rifiutato");
    return { ok: !!r.ok, testo: testo };
  }

  /**
   * Load one bridge endpoint into {caricamento, dati, errore} plus a reload.
   *
   * Each panel owns its own request and its own failure. One dead endpoint
   * greys out one card; the other six keep working.
   */
  function useDato(path) {
    var s0 = { caricamento: true, dati: null, errore: "" };
    var st = useState(s0);
    var stato = st[0];
    var setStato = st[1];

    var carica = useCallback(function () {
      setStato(function (p) {
        return { caricamento: true, dati: p.dati, errore: "" };
      });
      return leggi(path).then(function (r) {
        if (r && r.raggiungibile) {
          setStato({ caricamento: false, dati: r.dati, errore: "" });
        } else {
          setStato({
            caricamento: false, dati: null,
            errore: (r && r.errore) || "Hermes non raggiungibile"
          });
        }
      }).catch(function (e) {
        setStato({ caricamento: false, dati: null, errore: motivo(e) });
      });
    }, [path]);

    useEffect(function () { carica(); }, [carica]);
    return [stato, carica];
  }

  // -------------------------------------------------------------------------
  // Small shared pieces
  // -------------------------------------------------------------------------

  function Pillola(props) {
    return h(Badge, {
      className: cx("sv-pill", props.acceso ? "sv-pill-on" : "sv-pill-off")
    }, props.children);
  }

  function Riquadro(props) {
    return h(Card, { className: cx("sv-card", props.className) },
      h(CardContent, { className: "sv-card-body" },
        props.titolo ? h("div", { className: "sv-card-title" }, props.titolo) : null,
        props.nota ? h("p", { className: "sv-hint" }, props.nota) : null,
        props.children));
  }

  /** Uniform "loading / unreachable / here it is" body for every panel. */
  function Corpo(props) {
    if (props.stato.errore) {
      return h("div", { className: "sv-errore" },
        h("strong", null, "Non raggiungibile. "),
        h("span", null, props.stato.errore),
        h("div", { className: "sv-riga sv-riga-fine" },
          h(Button, { className: "sv-btn sv-btn-ghost", type: "button", onClick: props.ricarica },
            "riprova")));
    }
    if (props.stato.caricamento && !props.stato.dati) {
      return h("p", { className: "sv-hint" }, "caricamento…");
    }
    if (!props.stato.dati) {
      return h("p", { className: "sv-hint" }, "nessun dato");
    }
    return props.children;
  }

  function Messaggio(props) {
    if (!props.testo) return null;
    return h("span", {
      className: cx("sv-msg", props.ok ? "sv-msg-ok" : "sv-msg-ko")
    }, (props.ok ? "✓ " : "✗ ") + props.testo);
  }

  function gigabyte(bytes) {
    if (!bytes) return "";
    return (bytes / 1e9).toFixed(1).replace(".", ",") + " GB";
  }

  // -------------------------------------------------------------------------
  // 1. Motori
  // -------------------------------------------------------------------------

  function Motori() {
    var d = useDato("/backends");
    var stato = d[0];
    var ricarica = d[1];

    var mst = useState([]);
    var righe = mst[0];
    var setRighe = mst[1];
    var msgSt = useState(null);
    var msg = msgSt[0];
    var setMsg = msgSt[1];

    // Work on a copy: the whole list is posted back on save, and the fields
    // this page does not edit (comment, options, parallel, extra) must survive
    // the round trip untouched.
    useEffect(function () {
      var b = (stato.dati && stato.dati.backends) || [];
      setRighe(JSON.parse(JSON.stringify(b)));
    }, [stato.dati]);

    function cambia(i, chiave, valore) {
      setRighe(function (p) {
        var n = p.slice();
        n[i] = Object.assign({}, n[i]);
        n[i][chiave] = valore;
        return n;
      });
    }

    function sposta(i, delta) {
      setRighe(function (p) {
        var j = i + delta;
        if (j < 0 || j >= p.length) return p;
        var n = p.slice();
        var t = n[i]; n[i] = n[j]; n[j] = t;
        return n;
      });
    }

    function salva() {
      setMsg({ ok: true, testo: "salvataggio…" });
      scrivi("/backends", { backends: righe }).then(function (r) {
        setMsg(esito(r));
        if (r && r.ok) window.setTimeout(ricarica, 600);
      }).catch(function (e) {
        setMsg({ ok: false, testo: motivo(e) });
      });
    }

    return h(F, null,
      h(Riquadro, {
        titolo: "Motori",
        nota: "L'ordine conta: Hermes usa il primo motore che risponde. " +
          "Le chiavi API non si vedono e non si scrivono da qui: stanno in file " +
          "leggibili solo da root."
      },
        h(Corpo, { stato: stato, ricarica: ricarica },
          h("div", { className: "sv-elenco" }, righe.map(function (b, i) {
            var modelli = b.available_models || [];
            return h("div", { className: "sv-voce", key: b.name || i },
              h("div", { className: "sv-riga" },
                h("strong", null, b.label || b.name),
                h("code", { className: "sv-code" }, b.name),
                h(Pillola, { acceso: b.is_private }, b.is_private ? "privato" : "non privato"),
                h(Pillola, { acceso: b.healthy }, b.healthy ? "sano" : "giù"),
                b.has_key ? h(Pillola, { acceso: true }, "chiave presente") : null,
                h("span", { className: "sv-spazio" }),
                h(Button, {
                  className: "sv-btn sv-btn-ghost", type: "button",
                  onClick: function () { sposta(i, -1); }
                }, "↑"),
                h(Button, {
                  className: "sv-btn sv-btn-ghost", type: "button",
                  onClick: function () { sposta(i, 1); }
                }, "↓")),
              h("div", { className: "sv-riga sv-riga-campi" },
                h("label", { className: "sv-campo sv-campo-flag" },
                  h("input", {
                    type: "checkbox", checked: !!b.enabled,
                    onChange: function (e) { cambia(i, "enabled", e.target.checked); }
                  }),
                  h("span", null, "acceso")),
                h("label", { className: "sv-campo" },
                  h("span", { className: "sv-etichetta" }, "modello"),
                  modelli.length
                    ? h("select", {
                      className: "sv-select", value: b.model || "",
                      onChange: function (e) { cambia(i, "model", e.target.value); }
                    },
                      [h("option", { key: "_", value: b.model || "" }, b.model || "(nessuno)")]
                        .concat(modelli.filter(function (m) { return m !== b.model; })
                          .map(function (m) {
                            return h("option", { key: m, value: m }, m);
                          })))
                    : h(Input, {
                      className: "sv-input", value: b.model || "",
                      onChange: function (e) { cambia(i, "model", e.target.value); }
                    })),
                h("label", { className: "sv-campo" },
                  h("span", { className: "sv-etichetta" }, "indirizzo"),
                  h("code", { className: "sv-code sv-code-larga" }, b.url))),
              h("div", { className: "sv-riga sv-hint" },
                h("span", null, "tipo: " + (b.type || "?")),
                h("span", null, "latenza: " +
                  (b.latency_ms != null ? b.latency_ms + " ms" : "mai misurata")),
                h("span", null, "chiamate in volo: " + (b.inflight != null ? b.inflight : 0)),
                b.comment ? h("span", { className: "sv-commento" }, b.comment) : null));
          })),
          h("div", { className: "sv-riga sv-barra" },
            h(Button, { className: "sv-btn sv-btn-primario", type: "button", onClick: salva },
              "Salva motori"),
            h(Button, { className: "sv-btn sv-btn-ghost", type: "button", onClick: ricarica },
              "Ricarica"),
            msg ? h(Messaggio, { ok: msg.ok, testo: msg.testo }) : null))));
  }

  // -------------------------------------------------------------------------
  // 2. Modelli
  // -------------------------------------------------------------------------

  var RUOLI = ["chat", "reasoning", "coding", "vision", "tools", "embedding",
    "small", "multilingual"];

  function Modelli() {
    var d = useDato("/models/catalog");
    var stato = d[0];
    var ricarica = d[1];

    var mSt = useState("");
    var motore = mSt[0];
    var setMotore = mSt[1];
    var rSt = useState("");
    var ruolo = rSt[0];
    var setRuolo = rSt[1];
    var sSt = useState({});
    var stati = sSt[0];
    var setStati = sSt[1];

    var installati = (stato.dati && stato.dati.installed) || {};
    var motori = useMemo(function () {
      return Object.keys(installati);
    }, [stato.dati]);

    useEffect(function () {
      if (!motore && motori.length) setMotore(motori[0]);
    }, [motori, motore]);

    function segna(nome, testo) {
      setStati(function (p) {
        var n = Object.assign({}, p);
        n[nome] = testo;
        return n;
      });
    }

    /**
     * Read the bridge's Server-Sent Events as they arrive.
     *
     * authedFetch is used instead of fetchJSON because the answer is a stream,
     * not a JSON document - fetchJSON would wait for the last byte and the
     * download would look frozen for its whole duration.
     */
    function scarica(nome) {
      if (!motore) { segna(nome, "nessun motore Ollama selezionato"); return; }
      segna(nome, "avvio…");
      authedFetch(BASE + "/models/pull", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ backend: motore, model: nome })
      }).then(function (resp) {
        if (!resp.ok) { segna(nome, "✗ il ponte ha risposto " + resp.status); return; }
        if (!resp.body || !resp.body.getReader) {
          segna(nome, "✗ questo browser non sa leggere lo stream");
          return;
        }
        var reader = resp.body.getReader();
        var dec = new TextDecoder();
        var buf = "";
        function pompa() {
          return reader.read().then(function (r) {
            if (r.done) { segna(nome, "fatto"); ricarica(); return; }
            buf += dec.decode(r.value, { stream: true });
            var pezzi = buf.split("\n\n");
            buf = pezzi.pop();
            pezzi.forEach(function (p) {
              var riga = p.split("\n").filter(function (l) {
                return l.indexOf("data: ") === 0;
              })[0];
              if (!riga) return;
              try {
                var j = JSON.parse(riga.slice(6));
                if (j.error) segna(nome, "✗ " + j.error);
                else if (j.total && j.completed) {
                  segna(nome, Math.round((100 * j.completed) / j.total) + "%");
                } else if (j.status) segna(nome, j.status);
              } catch (e) {
                // A frame split across two chunks: the next read completes it.
              }
            });
            return pompa();
          });
        }
        return pompa();
      }).catch(function (e) {
        segna(nome, "✗ " + motivo(e));
      });
    }

    function elimina(nome) {
      if (!motore) { segna(nome, "nessun motore Ollama selezionato"); return; }
      if (!window.confirm("Eliminare " + nome + " da " + motore + "?")) return;
      segna(nome, "elimino…");
      scrivi("/models/delete", { backend: motore, model: nome }).then(function (r) {
        var e = esito(r);
        segna(nome, (e.ok ? "eliminato" : "✗ " + e.testo));
        if (e.ok) ricarica();
      }).catch(function (err) {
        segna(nome, "✗ " + motivo(err));
      });
    }

    var catalogo = (stato.dati && stato.dati.catalog) || [];
    var visibili = catalogo.filter(function (m) {
      return !ruolo || (m.role || []).indexOf(ruolo) >= 0;
    });
    var presenti = installati[motore] || {};

    return h(Riquadro, {
      titolo: "Modelli",
      nota: "Il catalogo è quello di Hermes. Scaricare passa dal motore Ollama " +
        "scelto qui sotto e mostra l'avanzamento reale, non una barra finta."
    },
      h(Corpo, { stato: stato, ricarica: ricarica },
        h("div", { className: "sv-riga sv-riga-campi" },
          h("label", { className: "sv-campo" },
            h("span", { className: "sv-etichetta" }, "motore"),
            h("select", {
              className: "sv-select", value: motore,
              onChange: function (e) { setMotore(e.target.value); }
            }, motori.length
              ? motori.map(function (m) { return h("option", { key: m, value: m }, m); })
              : [h("option", { key: "_", value: "" }, "nessun motore Ollama")])),
          h("label", { className: "sv-campo" },
            h("span", { className: "sv-etichetta" }, "ruolo"),
            h("select", {
              className: "sv-select", value: ruolo,
              onChange: function (e) { setRuolo(e.target.value); }
            }, [h("option", { key: "_", value: "" }, "tutti")].concat(
              RUOLI.map(function (r) { return h("option", { key: r, value: r }, r); })))),
          h("span", { className: "sv-spazio" }),
          h(Button, { className: "sv-btn sv-btn-ghost", type: "button", onClick: ricarica },
            "Ricarica")),
        h("div", { className: "sv-elenco" }, visibili.map(function (m) {
          var dim = presenti[m.name];
          var installato = dim !== undefined;
          return h("div", { className: "sv-voce", key: m.name },
            h("div", { className: "sv-riga" },
              h("strong", null, m.label || m.name),
              h("code", { className: "sv-code" }, m.name),
              installato
                ? h(Pillola, { acceso: true }, "installato" + (dim ? " · " + gigabyte(dim) : ""))
                : h(Pillola, { acceso: false }, "non installato"),
              h("span", { className: "sv-spazio" }),
              installato
                ? h(Button, {
                  className: "sv-btn sv-btn-pericolo", type: "button",
                  onClick: function () { elimina(m.name); }
                }, "elimina")
                : h(Button, {
                  className: "sv-btn", type: "button",
                  onClick: function () { scarica(m.name); }
                }, "scarica"),
              h("span", { className: "sv-hint sv-stato" }, stati[m.name] || "")),
            h("div", { className: "sv-hint" },
              (m.note || "") +
              ((m.role || []).length ? "  ·  ruoli: " + m.role.join(", ") : "")));
        })),
        visibili.length ? null : h("p", { className: "sv-hint" }, "nessun modello con questo ruolo")));
  }

  // -------------------------------------------------------------------------
  // 3. Fornitori
  // -------------------------------------------------------------------------

  function Fornitori() {
    var d = useDato("/providers/presets");
    var stato = d[0];
    var ricarica = d[1];
    var presets = (stato.dati && stato.dati.presets) || [];

    return h(Riquadro, {
      titolo: "Fornitori",
      nota: "Sola lettura: questi sono i preset che Hermes conosce. Per usarne " +
        "uno si aggiunge il motore nella scheda Motori e la chiave si scrive a " +
        "mano nel file di root - non passa da questa pagina, mai."
    },
      h(Corpo, { stato: stato, ricarica: ricarica },
        h("div", { className: "sv-elenco" }, presets.map(function (p) {
          return h("div", { className: "sv-voce", key: p.name },
            h("div", { className: "sv-riga" },
              h("strong", null, p.label || p.name),
              h("code", { className: "sv-code" }, p.name),
              h(Pillola, { acceso: p.configured }, p.configured ? "già configurato" : "non configurato"),
              h(Pillola, { acceso: p.verified }, p.verified ? "verificato dal vivo" : "mai provato")),
            h("div", { className: "sv-hint" },
              h("div", null, "indirizzo: " + (p.url || "?") + "  ·  modello: " + (p.model || "?")),
              p.limits ? h("div", null, "limiti: " + p.limits) : null,
              p.key_url ? h("div", null, "chiave da: " + p.key_url) : null,
              p.note ? h("div", { className: "sv-commento" }, p.note) : null));
        })),
        presets.length ? null : h("p", { className: "sv-hint" }, "nessun preset")));
  }

  // -------------------------------------------------------------------------
  // 4. Rotte
  // -------------------------------------------------------------------------

  var STRATEGIE = [
    { v: "ordine", t: "ordine (di default)" },
    { v: "piu_veloce", t: "più veloce (latenza dell'ultima chiamata)" },
    { v: "meno_carico", t: "meno carico (chiamate in volo)" }
  ];

  function Rotte() {
    var d = useDato("/routes");
    var stato = d[0];
    var ricarica = d[1];

    var rSt = useState([]);
    var rotte = rSt[0];
    var setRotte = rSt[1];
    var sSt = useState("ordine");
    var strategia = sSt[0];
    var setStrategia = sSt[1];
    var mSt = useState(null);
    var msg = mSt[0];
    var setMsg = mSt[1];

    useEffect(function () {
      var r = (stato.dati && stato.dati.routes) || [];
      setRotte(JSON.parse(JSON.stringify(r)));
      if (stato.dati && stato.dati.strategy) setStrategia(stato.dati.strategy);
    }, [stato.dati]);

    function cambia(i, chiave, valore) {
      setRotte(function (p) {
        var n = p.slice();
        n[i] = Object.assign({}, n[i]);
        n[i][chiave] = valore;
        return n;
      });
    }

    function sposta(i, delta) {
      setRotte(function (p) {
        var j = i + delta;
        if (j < 0 || j >= p.length) return p;
        var n = p.slice();
        var t = n[i]; n[i] = n[j]; n[j] = t;
        return n;
      });
    }

    function salva() {
      setMsg({ ok: true, testo: "salvataggio…" });
      scrivi("/routes", { routes: rotte, strategy: strategia }).then(function (r) {
        setMsg(esito(r));
        if (r && r.ok) window.setTimeout(ricarica, 600);
      }).catch(function (e) {
        setMsg({ ok: false, testo: motivo(e) });
      });
    }

    return h(Riquadro, {
      titolo: "Rotte per intenti",
      nota: "«privato» non può mai cadere su un motore non privato, nemmeno " +
        "forzandolo. Il nome della rotta è fisso; primario e ripiego sono nomi " +
        "di motori, il ripiego separato da virgole."
    },
      h(Corpo, { stato: stato, ricarica: ricarica },
        h("div", { className: "sv-riga sv-riga-campi" },
          h("label", { className: "sv-campo" },
            h("span", { className: "sv-etichetta" }, "strategia di scelta"),
            h("select", {
              className: "sv-select", value: strategia,
              onChange: function (e) { setStrategia(e.target.value); }
            }, STRATEGIE.map(function (s) {
              return h("option", { key: s.v, value: s.v }, s.t);
            })))),
        h("div", { className: "sv-elenco" }, rotte.map(function (r, i) {
          return h("div", { className: "sv-voce", key: r.name || i },
            h("div", { className: "sv-riga" },
              h("strong", null, r.name),
              r.solo_privati ? h(Pillola, { acceso: true }, "solo motori privati") : null,
              h("span", { className: "sv-spazio" }),
              h(Button, {
                className: "sv-btn sv-btn-ghost", type: "button",
                onClick: function () { sposta(i, -1); }
              }, "↑"),
              h(Button, {
                className: "sv-btn sv-btn-ghost", type: "button",
                onClick: function () { sposta(i, 1); }
              }, "↓")),
            h("div", { className: "sv-riga sv-riga-campi" },
              h("label", { className: "sv-campo sv-campo-largo" },
                h("span", { className: "sv-etichetta" }, "descrizione"),
                h(Input, {
                  className: "sv-input", value: r.descrizione || "",
                  onChange: function (e) { cambia(i, "descrizione", e.target.value); }
                }))),
            h("div", { className: "sv-riga sv-riga-campi" },
              h("label", { className: "sv-campo" },
                h("span", { className: "sv-etichetta" }, "motore primario"),
                h(Input, {
                  className: "sv-input", value: r.primary || "",
                  onChange: function (e) { cambia(i, "primary", e.target.value); }
                })),
              h("label", { className: "sv-campo sv-campo-largo" },
                h("span", { className: "sv-etichetta" }, "ripiego (nomi separati da virgola)"),
                h(Input, {
                  className: "sv-input", value: (r.fallback || []).join(", "),
                  onChange: function (e) {
                    cambia(i, "fallback", e.target.value.split(",").map(function (s) {
                      return s.trim();
                    }).filter(Boolean));
                  }
                }))));
        })),
        h("div", { className: "sv-riga sv-barra" },
          h(Button, { className: "sv-btn sv-btn-primario", type: "button", onClick: salva },
            "Salva rotte"),
          h(Button, { className: "sv-btn sv-btn-ghost", type: "button", onClick: ricarica },
            "Ricarica"),
          msg ? h(Messaggio, { ok: msg.ok, testo: msg.testo }) : null)));
  }

  // -------------------------------------------------------------------------
  // 5. Memoria
  // -------------------------------------------------------------------------

  function Memoria() {
    var d = useDato("/memory/status");
    var stato = d[0];
    var ricarica = d[1];
    var mSt = useState(null);
    var msg = mSt[0];
    var setMsg = mSt[1];

    function reindicizza() {
      setMsg({ ok: true, testo: "reindicizzo… può metterci un paio di minuti" });
      scrivi("/memory/reindex", {}).then(function (r) {
        setMsg(esito(r));
        ricarica();
      }).catch(function (e) {
        setMsg({ ok: false, testo: motivo(e) });
      });
    }

    var m = stato.dati || {};
    var corpo;
    if (m.configurata === false) {
      corpo = h("p", { className: "sv-hint" },
        "Memoria non configurata" + (m.errore ? ": " + m.errore : ": manca il DSN di Postgres."));
    } else {
      corpo = h("div", { className: "sv-griglia" },
        h("div", { className: "sv-riga" },
          h("span", null, "Postgres"), h(Pillola, { acceso: m.postgres }, m.postgres ? "su" : "giù")),
        h("div", { className: "sv-riga" },
          h("span", null, "Qdrant"), h(Pillola, { acceso: m.qdrant }, m.qdrant ? "su" : "giù"),
          m.qdrant_punti != null ? h("span", { className: "sv-hint" }, m.qdrant_punti + " punti") : null),
        h("div", { className: "sv-riga" },
          h("span", null, "Valkey"), h(Pillola, { acceso: m.valkey }, m.valkey ? "su" : "giù")),
        h("div", { className: "sv-riga" },
          h("span", null, "Embedding"),
          h(Pillola, { acceso: m.embedding },
            m.embedding ? (m.embedding_ms + " ms") : "non disponibile")),
        h("div", { className: "sv-riga sv-hint" },
          h("span", null, "fatti: " + (m.fatti != null ? m.fatti : "?")),
          h("span", null, "impegni: " + (m.impegni != null ? m.impegni : "?")),
          h("span", null, "procedure: " + (m.procedure != null ? m.procedure : "?")),
          h("span", null, "vettori: " + (m.vettori != null ? m.vettori : "?"))));
    }

    return h(Riquadro, {
      titolo: "Memoria",
      nota: "Lo stato è letto dal vivo dai tre magazzini. Reindicizzare usa le " +
        "stesse funzioni del timer notturno: un solo percorso di codice per " +
        "«lo fa da solo» e «lo voglio adesso»."
    },
      h(Corpo, { stato: stato, ricarica: ricarica },
        corpo,
        h("div", { className: "sv-riga sv-barra" },
          h(Button, { className: "sv-btn", type: "button", onClick: reindicizza },
            "Reindicizza vault e runbook"),
          h(Button, { className: "sv-btn sv-btn-ghost", type: "button", onClick: ricarica },
            "Ricarica"),
          msg ? h(Messaggio, { ok: msg.ok, testo: msg.testo }) : null)));
  }

  // -------------------------------------------------------------------------
  // 6. Rubrica
  // -------------------------------------------------------------------------

  function Rubrica() {
    var d = useDato("/contacts");
    var stato = d[0];
    var ricarica = d[1];

    var nSt = useState(""); var nome = nSt[0]; var setNome = nSt[1];
    var eSt = useState(""); var email = eSt[0]; var setEmail = eSt[1];
    var tSt = useState(""); var nota = tSt[0]; var setNota = tSt[1];
    var mSt = useState(null); var msg = mSt[0]; var setMsg = mSt[1];

    function aggiungi() {
      if (!nome.trim() || !email.trim()) {
        setMsg({ ok: false, testo: "servono nome ed email" });
        return;
      }
      setMsg({ ok: true, testo: "aggiungo…" });
      scrivi("/contacts", {
        nome: nome.trim(), email: email.trim(), nota: nota.trim()
      }).then(function (r) {
        var e = esito(r);
        setMsg(e);
        if (e.ok) { setNome(""); setEmail(""); setNota(""); ricarica(); }
      }).catch(function (err) {
        setMsg({ ok: false, testo: motivo(err) });
      });
    }

    function invio(e) {
      if (e.key === "Enter") { e.preventDefault(); aggiungi(); }
    }

    var contatti = (stato.dati && stato.dati.contacts) || [];

    return h(F, null,
      h(Riquadro, {
        titolo: "Aggiungi un contatto",
        nota: "Hermes scrive solo a chi è in rubrica: un indirizzo mai visto " +
          "viene rifiutato, non inventato."
      },
        h("div", { className: "sv-riga sv-riga-campi" },
          h("label", { className: "sv-campo" },
            h("span", { className: "sv-etichetta" }, "nome"),
            h(Input, {
              className: "sv-input", value: nome, onKeyDown: invio,
              onChange: function (e) { setNome(e.target.value); }
            })),
          h("label", { className: "sv-campo" },
            h("span", { className: "sv-etichetta" }, "email"),
            h(Input, {
              className: "sv-input", value: email, onKeyDown: invio,
              onChange: function (e) { setEmail(e.target.value); }
            })),
          h("label", { className: "sv-campo" },
            h("span", { className: "sv-etichetta" }, "nota"),
            h(Input, {
              className: "sv-input", value: nota, onKeyDown: invio,
              onChange: function (e) { setNota(e.target.value); }
            }))),
        h("div", { className: "sv-riga sv-barra" },
          h(Button, { className: "sv-btn sv-btn-primario", type: "button", onClick: aggiungi },
            "Aggiungi"),
          msg ? h(Messaggio, { ok: msg.ok, testo: msg.testo }) : null)),
      h(Riquadro, { titolo: "Rubrica" },
        h(Corpo, { stato: stato, ricarica: ricarica },
          contatti.length
            ? h("div", { className: "sv-elenco" }, contatti.map(function (c, i) {
              return h("div", { className: "sv-voce", key: c.email || i },
                h("div", { className: "sv-riga" },
                  h("strong", null, c.nome),
                  h("span", { className: "sv-hint" }, c.email),
                  h(Pillola, { acceso: c.attivo }, c.attivo ? "attivo" : "disattivato"),
                  h("span", { className: "sv-spazio" }),
                  h("span", { className: "sv-hint" },
                    "usato " + (c.usato_volte != null ? c.usato_volte : 0) + " volte")),
                c.nota ? h("div", { className: "sv-hint sv-commento" }, c.nota) : null);
            }))
            : h("p", { className: "sv-hint" },
              "Rubrica vuota: aggiungi il primo contatto qui sopra."))));
  }

  // -------------------------------------------------------------------------
  // 7. Master
  // -------------------------------------------------------------------------

  function Master() {
    var d = useDato("/master/status");
    var stato = d[0];
    var ricarica = d[1];
    var l = useDato("/master/log");
    var registro = l[0];
    var ricaricaRegistro = l[1];

    var mSt = useState(null); var msg = mSt[0]; var setMsg = mSt[1];
    var pSt = useState(""); var motivoPausa = pSt[0]; var setMotivoPausa = pSt[1];

    var s = stato.dati || {};
    var azioni = s.actions || [];
    var sw = s.switch || {};

    function chiama(azione, corpo, etichetta) {
      setMsg({ ok: true, testo: etichetta + "…" });
      scrivi("/master/" + azione, corpo || {}).then(function (r) {
        var e = esito(r);
        setMsg({ ok: e.ok, testo: e.ok ? etichetta : e.testo });
        ricarica();
        ricaricaRegistro();
      }).catch(function (err) {
        setMsg({ ok: false, testo: motivo(err) });
      });
    }

    // Arming is a deliberate act. The confirmation is asked here AND required
    // upstream: the bridge never supplies `conferma` on its own.
    function arma() {
      var testo = "Armare la modalità MASTER?\n\n" + azioni.length +
        " azioni diventano eseguibili per 30 minuti, poi si disarma da sola.\n\n" +
        "Il divieto assoluto (Immich, distruzione dati, guardie) resta attivo comunque.";
      if (!window.confirm(testo)) return;
      chiama("arm", { conferma: true }, "armato");
    }

    var minuti = Math.floor((s.seconds_left || 0) / 60);
    var secondi = (s.seconds_left || 0) % 60;

    var righeRegistro = (registro.dati && registro.dati.log) || [];

    return h(F, null,
      h(Riquadro, {
        titolo: "Modalità MASTER",
        nota: "Un elenco fisso di azioni, mai una shell libera. Il divieto " +
          "assoluto resta anche da armato: non è un'opzione di questa pagina. " +
          "Armare dura 30 minuti e poi scade da solo."
      },
        h(Corpo, { stato: stato, ricarica: ricarica },
          h("div", { className: "sv-riga" },
            h(Pillola, { acceso: s.armed },
              s.armed ? ("ARMATO · scade fra " + minuti + "m " + secondi + "s") : "non armato"),
            h(Pillola, { acceso: s.running }, s.running ? "RUNNING" : "PAUSED"),
            h("span", { className: "sv-hint" }, azioni.length + " azioni nel catalogo"),
            s.ssh_configured ? null
              : h(Pillola, { acceso: false }, "chiave SSH master assente")),
          s.running ? null : h("div", { className: "sv-hint" },
            (sw.paused_by ? "in pausa da " + sw.paused_by : "in pausa") +
            (sw.paused_reason ? " «" + sw.paused_reason + "»" : "") +
            ((sw.stopped_tools || []).length
              ? " · fermi: " + sw.stopped_tools.join(", ") +
              " — chat, lettura e memoria continuano"
              : "")),
          s.ssh_configured ? null : h("p", { className: "sv-hint" },
            "Le azioni su Proxmox (pct/qm) non possono partire finché la chiave " +
            "SSH non viene creata."),
          h("div", { className: "sv-riga sv-barra" },
            h(Button, { className: "sv-btn sv-btn-pericolo", type: "button", onClick: arma },
              "Arma (30 minuti)"),
            h(Button, {
              className: "sv-btn sv-btn-ghost", type: "button",
              onClick: function () { chiama("disarm", {}, "disarmato"); }
            }, "Disarma subito"),
            h(Button, {
              className: "sv-btn sv-btn-ghost", type: "button",
              onClick: function () { chiama("pause", { motivo: motivoPausa }, "in pausa"); }
            }, "Metti in pausa"),
            h(Button, {
              className: "sv-btn sv-btn-ghost", type: "button",
              onClick: function () { chiama("resume", {}, "ripreso"); }
            }, "Riprendi"),
            msg ? h(Messaggio, { ok: msg.ok, testo: msg.testo }) : null),
          h("div", { className: "sv-riga sv-riga-campi" },
            h("label", { className: "sv-campo sv-campo-largo" },
              h("span", { className: "sv-etichetta" },
                "motivo della pausa (finisce nel registro)"),
              h(Input, {
                className: "sv-input", value: motivoPausa,
                onChange: function (e) { setMotivoPausa(e.target.value); }
              }))))),

      h(Riquadro, { titolo: "Azioni disponibili" },
        h(Corpo, { stato: stato, ricarica: ricarica },
          h("div", { className: "sv-elenco" }, azioni.map(function (a) {
            return h("div", { className: "sv-voce", key: a.name },
              h("div", { className: "sv-riga" },
                h("strong", null, a.name),
                a.conferma ? h(Pillola, { acceso: false }, "chiede conferma") : null,
                a.reversibile ? null : h(Pillola, { acceso: false }, "irreversibile")),
              h("div", { className: "sv-hint" }, a.descrizione),
              h("div", { className: "sv-hint" },
                "parametri: " + (Object.keys(a.parametri || {}).join(", ") || "nessuno")));
          })))),

      h(Riquadro, {
        titolo: "Registro",
        nota: "Sola lettura: il servizio può scrivere una riga, non riscriverla."
      },
        h(Corpo, { stato: registro, ricarica: ricaricaRegistro },
          righeRegistro.length
            ? h("div", { className: "sv-elenco" }, righeRegistro.map(function (r) {
              return h("div", { className: "sv-voce", key: r.id },
                h("div", { className: "sv-riga" },
                  h("span", { className: "sv-hint" }, r.quando),
                  h("strong", null, r.azione),
                  h(Pillola, { acceso: r.esito === "riuscita" }, r.esito),
                  h("span", { className: "sv-hint" }, r.chi)),
                r.comando ? h("code", { className: "sv-code sv-code-larga" }, r.comando) : null);
            }))
            : h("p", { className: "sv-hint" }, "nessuna azione registrata"))));
  }

  // -------------------------------------------------------------------------
  // The page
  // -------------------------------------------------------------------------

  // One plugin, one tab, seven sections. The manifest contract gives a plugin
  // exactly one `tab`, so seven top-level tabs would mean seven plugin
  // directories, seven entries in plugins.enabled and seven Python modules all
  // bridging to the same assistant. See README.md for the full reasoning.
  var SEZIONI = [
    { id: "motori", label: "Motori", Comp: Motori },
    { id: "modelli", label: "Modelli", Comp: Modelli },
    { id: "fornitori", label: "Fornitori", Comp: Fornitori },
    { id: "rotte", label: "Rotte", Comp: Rotte },
    { id: "memoria", label: "Memoria", Comp: Memoria },
    { id: "rubrica", label: "Rubrica", Comp: Rubrica },
    { id: "master", label: "Master", Comp: Master }
  ];

  var CHIAVE_SCHEDA = "sovrano-scheda";

  function SovranoPage() {
    var aSt = useState(function () {
      try {
        var salvata = window.localStorage.getItem(CHIAVE_SCHEDA);
        return salvata && SEZIONI.some(function (s) { return s.id === salvata; })
          ? salvata : "motori";
      } catch (e) {
        return "motori";
      }
    });
    var attiva = aSt[0];
    var setAttiva = aSt[1];

    var hSt = useState(null);
    var salute = hSt[0];
    var setSalute = hSt[1];

    useEffect(function () {
      var vivo = true;
      leggi("/health").then(function (r) {
        if (vivo) setSalute(r);
      }).catch(function (e) {
        if (vivo) setSalute({ raggiungibile: false, errore: motivo(e) });
      });
      return function () { vivo = false; };
    }, []);

    function scegli(id) {
      setAttiva(id);
      try { window.localStorage.setItem(CHIAVE_SCHEDA, id); } catch (e) { /* private mode */ }
    }

    // Only the visible section is mounted: listing engines probes every
    // backend live, so mounting all seven at once would fire seven slow
    // requests for six pages nobody is looking at.
    var sezione = SEZIONI.filter(function (s) { return s.id === attiva; })[0] || SEZIONI[0];

    return h("div", { className: "sv-root" },
      h("header", { className: "sv-testata" },
        h("h1", { className: "sv-titolo" }, "Sovrano"),
        h("p", { className: "sv-hint" },
          "Le sette schede dell'assistente di casa. Questa pagina non decide " +
          "niente da sola: legge e scrive sull'Hermes vivo."),
        salute
          ? h(Pillola, { acceso: salute.raggiungibile },
            salute.raggiungibile
              ? ("Hermes raggiungibile su " + (salute.url || ""))
              : ("Hermes non raggiungibile: " + (salute.errore || "")))
          : h("span", { className: "sv-hint" }, "verifico il collegamento…")),
      h("nav", { className: "sv-schede" }, SEZIONI.map(function (s) {
        return h("button", {
          key: s.id, type: "button",
          className: cx("sv-scheda", s.id === attiva && "sv-scheda-attiva"),
          onClick: function () { scegli(s.id); }
        }, s.label);
      })),
      h("main", { className: "sv-contenuto" }, h(sezione.Comp, { key: sezione.id })));
  }

  window.__HERMES_PLUGINS__.register("sovereign-console", SovranoPage);
})();
