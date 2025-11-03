# 🧩 Censura Stats – Dashboard da log (PHP)

Una singola pagina **PHP** che legge i log di **kit-censura** e visualizza 3 grafici interattivi:

1. 📊 **URL per categoria** (stacked area chart)  
2. 🌐 **Totale URL unici**  
3. 🔢 **Totale IP bloccati**

Il tutto con **cache giornaliera automatica**, **warmup iniziale**, **pulsante di rigenerazione manuale**, **streaming NDJSON** e **decimazione LTTB** per prestazioni elevate.

---

## ✨ Caratteristiche principali

- ✅ **Parsing automatico dei log**
  - Legge `/var/log/kit-censura.log` e le versioni compresse `.gz`
  - Riconosce:
    - `List <categoria> - No.Records: N`
    - `Total unique urls: N.`
    - `Total IPs: N`

- ⚡ **Cache giornaliera**
  - 1 rebuild massimo al giorno
  - File NDJSON:
    - `summaries.ndjson` – categorie
    - `totals.ndjson` – totale URL
    - `ips.ndjson` – IP
  - Gestione **lock file** `.rebuild.lock` per evitare rebuild paralleli

- 🧠 **Endpoint API**
  - `?data=summaries` → NDJSON con categorie
  - `?data=totals` → NDJSON con totali URL
  - `?data=ips` → NDJSON con totali IP
  - `?status=1` → stato cache (`building`, `built_on`, `built_at`)
  - `?warmup=1` → avvia rebuild se necessario
  - `?warmup=1&rebuild=1` → forza rebuild immediato

- 🕒 **Front-end interattivo** (Chart.js + Luxon)
  - Grafici reattivi, con asse temporale
  - Decimazione LTTB (`samples: 800`) per dataset grandi
  - Nessuna animazione → caricamento istantaneo
  - Aggregazione per **run**, **ora**, o **giorno**
  - Periodo predefinito: **365 giorni**

- 🧰 **Interfaccia utente**
  - Form per selezionare *periodo* e *aggregazione*
  - Pulsante **“Rigenera cache ora”**
  - Banner con **spinner** e messaggio “Sto aggiornando la cache…” durante il rebuild
  - Aggiornamento automatico quando la cache è pronta

---

## ⚙️ Requisiti

- PHP **7.4+** (consigliato PHP 8.x)
- Estensione **zlib** attiva (opzionale, altrimenti usa `gzip -cd`)
- Accesso in lettura ai log di sistema (`/var/log/kit-censura.log`)
- Web server con PHP abilitato (Apache / Nginx)

---

## 🧩 Installazione

```bash
sudo cp censura-stats.php /var/www/html/
sudo mkdir -p /var/cache/censura-stats
sudo chown www-data:www-data /var/cache/censura-stats
sudo chmod 775 /var/cache/censura-stats
```

Assicurati che l’utente del web server (`www-data` o `nginx`) possa leggere i log:

```bash
sudo usermod -a -G adm www-data
```

---

## 🔧 Configurazione (in testa al file PHP)

```php
$LOG_DIR  = '/var/log';
$BASE     = 'kit-censura.log';
$MAX_ROT  = 30; // numero massimo di log .gz da analizzare
$TZ       = 'Europe/Rome';

$CACHE_DIR_PREFERRED = '/var/cache/censura-stats';
$CACHE_DIR_FALLBACK  = sys_get_temp_dir().'/censura-stats';

$DEFAULT_DAYS = 365; // periodo predefinito
```

---

## 🔍 Endpoint API

### Dati

| Endpoint | Descrizione | Output |
|-----------|-------------|--------|
| `?data=summaries` | Categorie per run | `{"ts":"YYYY-MM-DDTHH:MM:SS","cats":{"aams":123,...}}` |
| `?data=totals` | Totale URL unici | `{"ts":"YYYY-MM-DDTHH:MM:SS","total":39160}` |
| `?data=ips` | Totale IP | `{"ts":"YYYY-MM-DDTHH:MM:SS","ips":11931}` |

Parametri opzionali:
- `days=N` → Limita la finestra temporale (0 = nessun limite)
- `agg=run|hour|day` → Aggregazione temporale (default: `day`)

### Stato e cache

| Endpoint | Descrizione |
|-----------|-------------|
| `?status=1` | Stato della cache (`building`, `built_on`, `built_at`) |
| `?warmup=1` | Avvia rebuild se necessario |
| `?warmup=1&rebuild=1` | Forza rebuild immediato |

---

## 🧭 Utilizzo

Apri nel browser:

```
http://<host>/censura-stats.php
```

Vedrai:
- Un form con **Periodo** e **Aggregazione**
- Un bottone **Rigenera cache ora**
- Tre grafici:
  1. Categorie (stacked)
  2. Totale URL unici
  3. Totale IP

---

## 🕒 Automatizzare il warmup (cron)

```bash
5 6 * * * curl -sS "http://localhost/censura-stats.php?warmup=1" >/dev/null
# oppure per forzare sempre il rebuild
5 6 * * * curl -sS "http://localhost/censura-stats.php?warmup=1&rebuild=1" >/dev/null
```

---

## 🧱 Struttura del codice

- Parsing dei log (anche compressi `.gz`)
- Regex per:
  - `List <categoria> - No.Records`
  - `Total unique urls`
  - `Total IPs`
- Output NDJSON (una riga per record)
- Aggregazione lato server (`run`, `hour`, `day`)
- Cache giornaliera con lock (`.rebuild.lock`)
- Stato cache in `state.json`
- Front-end Chart.js + Luxon

---

## 🔒 Sicurezza

- Di default **non** richiede autenticazione → proteggi l’endpoint se pubblico.
- Usa `.htpasswd`, filtri IP o VPN.
- Il pulsante “Rigenera cache ora” forza solo il rebuild applicativo (nessun rischio di comandi di sistema).


## 🧑‍💻 Autore

**Antonio Bartolini**  
📦 Repository: [`rfc1036/kit-censura/`](https://github.com/rfc1036/kit-censura/)  
📜 File: `censura-stats.php`


