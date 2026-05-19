# Consob — source mapping (phase 4 Step 0)

> **Status**: ⚠️ **BLOCKER discovered**. Consob is protected by **Radware Bot Manager** which the brief's "httpx desktop UA + it-IT" approach **cannot bypass**. See section 5 below for the empirical evidence and the decision needed from the user before any scraper code is written.
>
> Discovered: 2026-05-19 — by Claude during Step 0 spec validation.

---

## 1. Target URLs

| Resource | URL |
|---|---|
| Documenti OPA — listing | `https://www.consob.it/web/area-pubblica/documenti-opa` |
| Documenti OPA — page N | `https://www.consob.it/web/area-pubblica/documenti-opa?p_p_id=it_consob_OpaDocumentsPortlet&p_p_lifecycle=0&p_p_state=normal&p_p_mode=view&_it_consob_OpaDocumentsPortlet_delta=50&_it_consob_OpaDocumentsPortlet_resetCur=false&_it_consob_OpaDocumentsPortlet_cur={N}` |
| Document PDF | `https://www.consob.it/documents/11973/11173223/{slug}_{YYYYMMDD}.pdf/{uuid}?version=1.0&t={timestamp}&download=false` |

`{N}` is 1-indexed page number. `{slug}` follows `opa_{normalised-name}` pattern (e.g. `opa_bancasistema_20260511.pdf`, `opa_cir_20260427.pdf`, `opa_danzic_20260424.pdf`).

## 2. Liferay portlet pagination (confirmed via Chrome DevTools MCP)

| Parameter | Meaning | Example |
|---|---|---|
| `p_p_id` | Portlet id (fixed) | `it_consob_OpaDocumentsPortlet` |
| `p_p_lifecycle` | Render phase | `0` |
| `p_p_state` | Portlet state | `normal` |
| `p_p_mode` | Portlet mode | `view` |
| `_it_consob_OpaDocumentsPortlet_delta` | Page size | `50` (tested), also accepts other values |
| `_it_consob_OpaDocumentsPortlet_resetCur` | Reset cursor | `false` |
| `_it_consob_OpaDocumentsPortlet_cur` | Page number (1-indexed) | `1`, `2`, …, `12` |

**Total results on 2026-05-19**: 596 → 12 pages at `delta=50`.

## 3. HTML structure (confirmed on page 1, fixture captured)

The DOM is **NOT a `<table>`**. The list is a `<ul class="consobResult">` whose first `<li class="header">` carries column titles and a "{N} Risultati trovati - Visualizzati: 1-50" string, and the remaining `<li>` are data rows.

### Per-row structure

```html
<li>
  <div class="div20 center">
    11/05/2026
    <span class="mobile">-</span>
    12/06/2026
  </div>
  <div class="div80 j">
    <p>Offerta pubblica di acquisto e scambio obbligatoria totalitaria promossa da
       <strong>Banca CF+ Credito Fondiario Spa</strong> su azioni emesse da
       <strong>Banca Sistema Spa</strong>. Il corrispettivo offerto è pari a 1,89 euro …</p>
    <span class="pdf">
      <a class="linkList" href="https://www.consob.it/documents/11973/11173223/opa_bancasistema_20260511.pdf/6a2eb96e-…?version=1.0&t=…&download=false" target="_blank">Documento d'offerta</a><br>
      <!-- zero or more additional <a> links to Comunicati -->
    </span>
  </div>
</li>
```

### Field extraction selectors (BeautifulSoup-compatible)

| Field | Selector / regex |
|---|---|
| `period_start` | `li > div.div20.center` → first date (`\d{2}/\d{2}/\d{4}`) |
| `period_end` | `li > div.div20.center` → second date |
| `description_html` | `li > div.div80.j > p` (one or more `<p>`, may have nested `<strong>`, `<em>`) |
| `target_name` (best-effort) | regex on description text: `(?:emesse da|su azioni|su azioni ordinarie emesse da|avente ad oggetto.+azioni)\s+<strong>([^<]+)</strong>` |
| `offerente_name` (best-effort) | regex on description text: `promossa da\s+<strong>([^<]+)</strong>` |
| `offer_type_raw` (best-effort) | regex on description: `Offerta pubblica di (acquisto(?:\s+e scambio)?)\s+(obbligatoria\|volontaria)(?:\s+(totalitaria\|parziale\|preventiva\|residuale))?` |
| `documento_offerta_url` | `li span.pdf a` where text == `"Documento d'offerta"` |
| `additional_links` | other `li span.pdf a` (Comunicati: proroga, risultati definitivi, superamento 90%/95%, etc.) |

### Page-1 fixture saved

`tests/fixtures/consob/documenti-opa-page1.html` (85 KB, 50 rows, full pagination block).

### Observed offer type narratives (from the 50 rows of page 1)

The Italian descriptions use a finite vocabulary. Examples seen:
- "Offerta pubblica di acquisto **obbligatoria totalitaria** promossa da X su azioni Y. Il corrispettivo è pari ad N,NN euro …"
- "Offerta pubblica di acquisto **volontaria parziale** promossa da X su un massimo di NNN azioni…"
- "Offerta pubblica di acquisto **e scambio** obbligatoria totalitaria…"
- "Offerta pubblica di acquisto **volontaria totalitaria**…"
- "Offerta pubblica di **scambio** volontaria totalitaria…"

Proposed mapping to our canonical `deal_type_enum`:

| Italian raw | Canonical enum |
|---|---|
| acquisto obbligatoria totalitaria | `opa_obbligatoria` |
| acquisto volontaria totalitaria | `opa_volontaria` |
| acquisto volontaria parziale | `opa_volontaria_parziale` |
| acquisto volontaria preventiva totalitaria | `opa_volontaria_preventiva` |
| acquisto residuale | `opa_residuale` |
| acquisto e scambio (any sub-type) | `opas` |
| scambio volontaria totalitaria | `ops` (or fold into `opas`) |

⚠️ **Action required from user**: the canonical enum already has `opa_volontaria_totalitaria`, `opa_volontaria_parziale`, `opa_obbligatoria`, `opa_consolidamento` (added in phase 1 migration `0004`). Mapping above keeps those + may need 1–2 new values (`opa_volontaria_preventiva`, `ops` if treated separately). Migration `0006` would be needed if so.

## 4. Document URL stability

PDF URLs are direct `https://www.consob.it/documents/...` links. They include a UUID and a `?t={millis-timestamp}` cache-buster but the path itself is stable. Download should work via direct HTTP **once the Radware challenge for the listing page has been bypassed** — see section 5.

Each row carries **multiple PDFs** (1 "Documento d'offerta" + N "Comunicati" follow-ups: proroga, risultati definitivi, sovra-soglia 90/95%, supplemento, modifica condizione, etc.). Phase 4 brief covers only the main `Documento d'offerta`. Comunicati are explicitly out-of-scope (bundled into phase 6-7 expansion per phase-3 tech debt #2).

## 5. ⚠️ Bot detection: Radware Bot Manager

This is the central finding of Step 0, and it invalidates the brief's "httpx + headers" implementation plan.

### Evidence

1. **`curl` with Chrome desktop UA + `Accept-Language: it-IT,it;q=0.9,en;q=0.7` → 302 redirect to `validate.perfdrive.com`**. The challenge page is 15 KB and does not contain the OPA data; it expects a JS-resolvable challenge token before un-blocking the IP.

   ```
   $ curl -sIL "https://www.consob.it/web/area-pubblica/documenti-opa" \
          -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 … Chrome/147 …" \
          -H "Accept-Language: it-IT,it;q=0.9,en;q=0.7"
   …
   Location: https://validate.perfdrive.com/?ssa=…&ssk=botmanager_support@radware.com&…
   FINAL_URL=https://validate.perfdrive.com/?ssa=…
   STATUS=200 SIZE=15060 CT=text/html
   ```

   Same outcome with `httpx`.

2. **Headless Chrome (via chrome-devtools MCP) succeeded ONCE.** First navigation to `…/documenti-opa` was redirected to the challenge page; the in-page JS solved it transparently after a few seconds, and the actual portlet rendered (596 results, 50 visible rows).

3. **Second navigation (page 2) failed.** Almost immediately the next request landed on a hard CAPTCHA page:

   > "We apologize for the inconvenience... but your activity and behavior on this site made us think that you are a bot."
   >
   > "Incident ID: 1e09ac1d-ch6v-42cc-996c-98b53cfdb424"
   >
   > "Please solve this CAPTCHA to request unblock to the website"

   `title` of the page: **"Radware Captcha Page"**. The same IP can no longer reach the site even from a real-browser flow without solving the visible CAPTCHA.

4. **Rate-limit empirical test (10 seq req with 1 s delay) — NOT POSSIBLE**. The brief assumed direct HTTP. The blocker fires on the first request. Once a session is flagged as bot, even subsequent navigations from the same Chrome instance are blocked. So we cannot characterise Consob's intrinsic rate limit because the bot detection layer fires first.

### Consequences for phase 4

The brief's Step 1 (`ConsobDiscoveryClient` using httpx + rate_limiter) **cannot work**. Production options ranked:

| Option | Cost | Robustness | Engineering work | Recommendation |
|---|---|---|---|---|
| **A. Managed scraping API** (ScrapingBee, ZenRows, Bright Data Web Unlocker) | ~$30-300/mo depending on volume | High — vendor maintains the cat-and-mouse | 1-2h to wire the HTTP client | ✅ **Most pragmatic for phase 1 paper-trading scope** |
| B. Playwright + stealth (`patchright`, `playwright-extra` with stealth plugin) + residential proxy | ~$50-200/mo for residential proxies; free Playwright | Medium — Radware updates break it periodically | 1-2 days to wire + 1 day every few months to maintain | Possible but fragile |
| C. Self-hosted undetected-chromedriver / playwright on the Oracle VM, no proxy | €0 cash | Low — single IP, will get blocked | 4-8h to wire | Will work for ~hours-to-days then break for weeks |
| D. Negotiate API access from Consob | €0 cash | High if granted | 1 day to write the request + N weeks/months of waiting | Worth filing in parallel; cannot block phase 4 on it |
| E. Manual periodic data export (operator clicks "Recherche", saves HTML, uploads) | €0 cash | High | Trivial code, but requires human-in-the-loop | Acceptable as fallback if all else blocked |

### Cross-jurisdiction implication

**Phase 5 (BaFin) is a coin flip too** — German regulators often use Cloudflare Bot Management or Akamai. If BaFin is also protected, the architectural decision taken here (A vs B vs C vs E) should cover all three.

## 6. Rate-limit observations

**Inconclusive** due to Radware block. The single successful page-1 load returned 85 KB of useful HTML in ~3 s wall-clock (including Radware JS solver time). No `Retry-After`, no `X-RateLimit-*` headers were ever returned by Consob itself (because we never reached Consob's actual rate-limit layer).

## 7. Italian offer type classifications observed

See "Observed offer type narratives" in section 3.

Comunicato types observed (out of phase-4 scope; logged for phase 6-7 reference):
- Comunicato sulla proroga del periodo di adesione
- Comunicato sui risultati definitivi dell'offerta
- Comunicato sul superamento della soglia del 90% / 95%
- Comunicato sulla proroga condizionata del periodo di adesione
- Comunicato del Consiglio di Amministrazione (CdA emittente)
- Comunicato di incremento del corrispettivo
- Comunicato di ritiro dell'offerta
- Supplemento al documento d'offerta
- Comunicato sulla scadenza dell'offerta
- Comunicato sui risultati provvisori
- Comunicato di rinuncia alla condizione sulla soglia
- … (≥56 distinct labels seen on page 1 alone)

## 8. Decision needed from user before coding

**Per brief: "STOP after Step 0. Wait for user validation of the source mapping before coding the scraper. This prevents Phase 2 mistake (wrong source assumption)."**

The mistake the brief was guarding against has been caught here. **Direct HTTP scraping of Consob is not viable.** Before any code is written, please pick one of:

- **(A) Approve a managed scraping vendor**, give me an account + API key → I implement the brief unchanged, just routing requests through the vendor's proxy.
- **(B) Approve Playwright + residential proxies** → I rewrite Step 1 of the brief to use `playwright` + `playwright-extra` with stealth and document the proxy plumbing in `scripts/oracle_bootstrap.sh` for phase 13.
- **(C) Accept best-effort self-hosted scraping** (will degrade) → I rewrite Step 1 with `patchright` + the assumption we'll hit blocks and need fallback periods.
- **(D) Pause phase 4** while a formal request is sent to Consob → no code in this branch; the docs-only PR records the finding and we re-open phase 4 after the response.
- **(E) Operator manual export** → I provide a Python script that ingests a Consob `documenti-opa.html` dropped into `data/manual-imports/it/` by the operator. Latency = whenever the operator runs it (acceptable for a paper-trading cap of 8-10h/week).

My recommendation: **A first** (lowest engineering risk, $30-100/mo on ScrapingBee's standard tier should cover phase-1 paper-trading volumes; explicit egress vs. fragile self-hosting). If the budget guard from CLAUDE.md §3 ("Coût mensuel cash : €0") is strict, then **E** (manual + script) is the only €0 path; we accept the latency cost.

## 9. Artifacts captured during Step 0

- `tests/fixtures/consob/documenti-opa-page1.html` — full page 1 HTML (50 rows + 12-page pagination block).
- `artifacts/phase-04/_raw-page1.json` — original chrome-devtools MCP response (for traceability; .gitignored as scratch).
