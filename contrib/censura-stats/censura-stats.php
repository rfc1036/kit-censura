<?php
/**
 * Censura Stats – cache giornaliera, lock & status, warmup, 3 grafici
 * Endpoints:
 *   ?status=1        -> {"building":bool,"built_on":"YYYY-MM-DD","built_at":"..."}
 *   ?warmup=1        -> avvia subito rebuild (se necessario) e risponde con lo stato
 *                      accetta ?rebuild=1 per forzare il rebuild
 *   ?data=summaries  -> NDJSON {"ts":"YYYY-MM-DDTHH:MM:SS","cats":{...}} con &agg=run|hour|day &days=N
 *   ?data=totals     -> NDJSON {"ts":"YYYY-MM-DDTHH:MM:SS","total":123}
 *   ?data=ips        -> NDJSON {"ts":"YYYY-MM-DDTHH:MM:SS","ips":123}
 */

declare(strict_types=1);

// ---------------- Config ----------------
$LOG_DIR  = '/var/log';
$BASE     = 'kit-censura.log';
$MAX_ROT  = 30;
$TZ       = 'Europe/Rome';

// Cache
$CACHE_DIR_PREFERRED = '/var/cache/censura-stats';
$CACHE_DIR_FALLBACK  = rtrim(sys_get_temp_dir(), '/').'/censura-stats';
$SUM_CACHE = 'summaries.ndjson';
$TOT_CACHE = 'totals.ndjson';
$IPS_CACHE = 'ips.ndjson';
$STATE_JSON = 'state.json';
$LOCK_FILE  = '.rebuild.lock';

// Default finestra (aggiornato: 365 gg)
$DEFAULT_DAYS = 365;

date_default_timezone_set($TZ);

// ---------------- Parametri UI/API ----------------
$DAYS_LIMIT = isset($_GET['days']) ? max(0, (int)$_GET['days']) : $DEFAULT_DAYS; // 0 = nessun limite
$AGG = isset($_GET['agg']) ? strtolower($_GET['agg']) : 'day'; // run|hour|day
if (!in_array($AGG, ['run','hour','day'], true)) $AGG = 'day';
$FORCE_REBUILD = isset($_GET['rebuild']);

// ---------------- Cache dir ----------------
$CACHE_DIR = is_dir($CACHE_DIR_PREFERRED) || @mkdir($CACHE_DIR_PREFERRED, 0775, true)
    ? $CACHE_DIR_PREFERRED
    : ($CACHE_DIR_FALLBACK && (is_dir($CACHE_DIR_FALLBACK) || @mkdir($CACHE_DIR_FALLBACK, 0775, true)) ? $CACHE_DIR_FALLBACK : null);

if ($CACHE_DIR === null) { http_response_code(500); echo "Impossibile creare la directory di cache."; exit; }
if (!is_dir($CACHE_DIR) && !@mkdir($CACHE_DIR, 0775, true)) { http_response_code(500); echo "Impossibile creare la directory di cache: $CACHE_DIR"; exit; }
if (!is_writable($CACHE_DIR)) { http_response_code(500); echo "La directory di cache non è scrivibile: $CACHE_DIR"; exit; }

$SUM_PATH   = "$CACHE_DIR/$SUM_CACHE";
$TOT_PATH   = "$CACHE_DIR/$TOT_CACHE";
$IPS_PATH   = "$CACHE_DIR/$IPS_CACHE";
$STATE_PATH = "$CACHE_DIR/$STATE_JSON";
$LOCK_PATH  = "$CACHE_DIR/$LOCK_FILE";

// ---------------- Regex permissive ----------------
$reStamp    = '/^(\d{2}\/\d{2}\/\d{2})\s+(\d{2}:\d{2}:\d{2})\s+-\s+/';
$reSumStart = '/^(\d{2}\/\d{2}\/\d{2})\s+(\d{2}:\d{2}:\d{2})\s+-\s+Censorship Summary started\.\s*$/i';
$reSumCat   = '/^(\d{2}\/\d{2}\/\d{2})\s+(\d{2}:\d{2}:\d{2})\s+-\s+List\s+([A-Za-z0-9_\-]+)\s+-\s+No\.Records:\s+(\d+)\s*$/i';
$reSumEnd   = '/^(\d{2}\/\d{2}\/\d{2})\s+(\d{2}:\d{2}:\d{2})\s+-\s+Censorship Summary ended\.\s*$/i';
$reIPsTot   = '/^(\d{2}\/\d{2}\/\d{2})\s+(\d{2}:\d{2}:\d{2})\s+-\s+Total IPs:\s+(\d+)\b/i';
$reUrlsTot  = '/^(\d{2}\/\d{2}\/\d{2})\s+(\d{2}:\d{2}:\d{2})\s+-\s+Total unique urls:\s+(\d+)\.\s*$/i';

// ---------------- Helpers ----------------
function to_iso_datetime(string $dmy_hms): ?string {
    $dt = DateTime::createFromFormat('d/m/y H:i:s', $dmy_hms);
    return $dt ? $dt->format('Y-m-d\TH:i:s') : null;
}
function older_than(?string $iso, ?DateTime $minDt): bool {
    if ($minDt === null || $iso === null) return false;
    $d = DateTime::createFromFormat('Y-m-d\TH:i:s', $iso);
    return $d && $d < $minDt;
}
function list_log_files(string $dir, string $base, int $maxRot): array {
    $files = [];
    $cur = "$dir/$base";
    if (is_readable($cur)) $files[] = ['path'=>$cur,'type'=>'plain','order'=>0,'mtime'=>@filemtime($cur) ?: 0];
    for ($i=1; $i <= $maxRot; $i++) {
        $gz = sprintf('%s/%s.%d.gz', $dir, $base, $i);
        if (is_readable($gz)) $files[] = ['path'=>$gz,'type'=>'gz','order'=>$i,'mtime'=>@filemtime($gz) ?: 0];
    }
    usort($files, fn($a,$b) => $a['order'] <=> $b['order']);
    return $files;
}
function state_load(string $path): array {
    if (!is_readable($path)) return [];
    $s = @json_decode(@file_get_contents($path) ?: '{}', true);
    return is_array($s) ? $s : [];
}
function state_save(string $path, array $state): void {
    @file_put_contents($path, json_encode($state, JSON_UNESCAPED_SLASHES|JSON_PRETTY_PRINT));
}

// ---------------- STATUS endpoint ----------------
if (isset($_GET['status'])) {
    header('Content-Type: application/json; charset=utf-8');
    $st = state_load($STATE_PATH);
    $building = is_file($LOCK_PATH);
    echo json_encode([
        'building' => $building,
        'built_on' => $st['built_on'] ?? null,
        'built_at' => $st['built_at'] ?? null,
    ], JSON_UNESCAPED_SLASHES);
    exit;
}

// ---------------- Cache: rebuild max 1 volta/giorno con lock ----------------
function rebuild_cache_once_per_day(
    string $logDir, string $base, int $maxRot,
    string $sumOut, string $totOut, string $ipsOut, string $statePath,
    int $daysLimit, bool $forceRebuild,
    string $lockPath
): void {
    global $reStamp, $reSumStart, $reSumCat, $reSumEnd, $reIPsTot, $reUrlsTot;

    $today = (new DateTimeImmutable('today'))->format('Y-m-d');
    $st = state_load($statePath);

    // già costruita oggi?
    if (!$forceRebuild && ($st['built_on'] ?? null) === $today
        && is_readable($sumOut) && is_readable($totOut) && is_readable($ipsOut)) {
        return;
    }

    // se lock presente, lascia che l'altro processo completi
    if (is_file($lockPath)) {
        return;
    }

    // prendi lock
    if (@file_put_contents($lockPath, (string)getmypid()) === false) {
        return;
    }

    try {
        $files = list_log_files($logDir, $base, $maxRot);

        $sumTmp = $sumOut.'.tmp';
        $totTmp = $totOut.'.tmp';
        $ipsTmp = $ipsOut.'.tmp';
        $sumH = @fopen($sumTmp, 'wb');
        $totH = @fopen($totTmp, 'wb');
        $ipsH = @fopen($ipsTmp, 'wb');
        if (!$sumH || !$totH || !$ipsH) {
            if ($sumH) fclose($sumH);
            if ($totH) fclose($totH);
            if ($ipsH) fclose($ipsH);
            throw new RuntimeException('Impossibile aprire i file di cache temporanei per scrittura.');
        }

        $minDt = null;
        if ($daysLimit > 0) $minDt = (new DateTime('now'))->modify("-{$daysLimit} days");

        $inSummary = false;
        $curCats   = [];

        foreach ($files as $meta) {
            $readLine = null;

            if ($meta['type'] === 'plain') {
                $f = new SplFileObject($meta['path'], 'r');
                $readLine = function() use ($f) {
                    if ($f->eof()) return false;
                    $line = $f->fgets();
                    return $line === false ? false : rtrim($line, "\r\n");
                };
            } else {
                if (extension_loaded('zlib')) {
                    $h = @gzopen($meta['path'], 'rb');
                    $readLine = function() use ($h) {
                        if (gzeof($h)) return false;
                        $line = gzgets($h);
                        return $line === false ? false : rtrim($line, "\r\n");
                    };
                } else {
                    $cmd = 'gzip -cd '.escapeshellarg($meta['path']);
                    $ph = @popen($cmd, 'r');
                    $readLine = function() use ($ph) {
                        if (feof($ph)) return false;
                        $line = fgets($ph);
                        return $line === false ? false : rtrim($line, "\r\n");
                    };
                }
            }

            if (!$readLine) continue;

            while (true) {
                $line = $readLine();
                if ($line === false) break;
                if (!preg_match($reStamp, $line)) continue;

                // Total unique urls
                if (preg_match($reUrlsTot, $line, $m)) {
                    $iso = to_iso_datetime("$m[1] $m[2]");
                    if (!older_than($iso, $minDt) && $iso !== null) {
                        fwrite($totH, json_encode(['ts'=>$iso,'total'=>(int)$m[3]], JSON_UNESCAPED_SLASHES)."\n");
                    }
                }

                // Total IPs
                if (preg_match($reIPsTot, $line, $m)) {
                    $iso = to_iso_datetime("$m[1] $m[2]");
                    if (!older_than($iso, $minDt) && $iso !== null) {
                        fwrite($ipsH, json_encode(['ts'=>$iso,'ips'=>(int)$m[3]], JSON_UNESCAPED_SLASHES)."\n");
                    }
                }

                // Summary categorie
                if (preg_match($reSumStart, $line)) { $inSummary = true; $curCats=[]; continue; }
                if ($inSummary && preg_match($reSumCat, $line, $m)) { $curCats[strtolower($m[3])] = (int)$m[4]; continue; }
                if ($inSummary && preg_match($reSumEnd, $line, $m)) {
                    $iso = to_iso_datetime("$m[1] $m[2]");
                    if (!older_than($iso, $minDt) && $iso !== null) {
                        fwrite($sumH, json_encode(['ts'=>$iso,'cats'=>$curCats], JSON_UNESCAPED_SLASHES)."\n");
                    }
                    $inSummary=false; $curCats=[]; continue;
                }
            }

            // chiusure handle
            if ($meta['type'] === 'plain') { $f = null; }
            else if (isset($h) && $h) { gzclose($h); unset($h); }
            else if (isset($ph) && $ph) { pclose($ph); unset($ph); }
        }

        fclose($sumH);
        fclose($totH);
        fclose($ipsH);
        @rename($sumTmp, $sumOut);
        @rename($totTmp, $totOut);
        @rename($ipsTmp, $ipsOut);

        state_save($statePath, [
            'built_on' => $today,
            'built_at' => date('c'),
        ]);
    } finally {
        @unlink($lockPath); // rilascia SEMPRE il lock
    }
}

// ---------------- WARMUP endpoint (avvia rebuild subito) ----------------
if (isset($_GET['warmup'])) {
    header('Content-Type: application/json; charset=utf-8');
    // Se serve davvero ricostruire (nuovo giorno o ?rebuild=1), questa chiamata attiva il lock e parte.
    rebuild_cache_once_per_day(
        $LOG_DIR, $BASE, $MAX_ROT,
        $SUM_PATH, $TOT_PATH, $IPS_PATH, $STATE_PATH,
        0, isset($_GET['rebuild']),
        $LOCK_PATH
    );
    $st = state_load($STATE_PATH);
    echo json_encode([
        'building' => is_file($LOCK_PATH), // se il rebuild è partito, qui è true
        'built_on' => $st['built_on'] ?? null,
        'built_at' => $st['built_at'] ?? null,
    ], JSON_UNESCAPED_SLASHES);
    exit;
}

// ---------------- Servizio dati con aggregazione ----------------
if (isset($_GET['data'])) {
    try {
        rebuild_cache_once_per_day(
            $LOG_DIR, $BASE, $MAX_ROT,
            $SUM_PATH, $TOT_PATH, $IPS_PATH, $STATE_PATH,
            0, $FORCE_REBUILD,
            $LOCK_PATH
        );
    } catch (Throwable $e) {
        http_response_code(500);
        header('Content-Type: text/plain; charset=utf-8');
        echo "Errore ricostruzione cache: ".$e->getMessage();
        exit;
    }

    $type = $_GET['data'];
    $minDt = null;
    if ($DAYS_LIMIT > 0) $minDt = (new DateTime('now'))->modify("-{$DAYS_LIMIT} days");

    header('Content-Type: application/x-ndjson; charset=utf-8');

    $emitAggregated = function($path, $valueKey) use ($AGG, $minDt) {
        $h = @fopen($path, 'rb');
        if (!$h) return;
        if ($AGG === 'run') {
            while (!feof($h)) {
                $line = fgets($h);
                if ($line === false) break;
                $line = trim($line);
                if ($line === '') continue;
                $row = json_decode($line, true);
                if (!isset($row['ts'], $row[$valueKey])) continue;
                $dt = DateTime::createFromFormat('Y-m-d\TH:i:s', $row['ts']);
                if (!$dt) continue;
                if ($minDt && $dt < $minDt) continue;
                echo $line."\n";
            }
        } else {
            $bucketMap = [];
            while (!feof($h)) {
                $line = fgets($h);
                if ($line === false) break;
                $line = trim($line);
                if ($line === '') continue;
                $row = json_decode($line, true);
                if (!isset($row['ts'], $row[$valueKey])) continue;

                $dt = DateTime::createFromFormat('Y-m-d\TH:i:s', $row['ts']);
                if (!$dt) continue;
                if ($minDt && $dt < $minDt) continue;

                if ($AGG === 'hour') {
                    $key = $dt->format('Y-m-d H');
                    $bucketTs = $dt->format('Y-m-d\TH:59:59');
                } else { // day
                    $key = $dt->format('Y-m-d');
                    $bucketTs = $dt->format('Y-m-d\T23:59:59');
                }
                $bucketMap[$key] = ['ts'=>$bucketTs, $valueKey=>$row[$valueKey]];
            }
            ksort($bucketMap);
            foreach ($bucketMap as $b) echo json_encode($b, JSON_UNESCAPED_SLASHES)."\n";
        }
        fclose($h);
    };

    if ($type === 'summaries') { $emitAggregated($SUM_PATH, 'cats'); exit; }
    if ($type === 'totals')    { $emitAggregated($TOT_PATH, 'total'); exit; }
    if ($type === 'ips')       { $emitAggregated($IPS_PATH, 'ips'); exit; }

    http_response_code(400);
    echo "Parametro data non valido.";
    exit;
}

// ---------------- UI ----------------
?>
<!doctype html>
<html lang="it">
<head>
  <meta charset="utf-8">
  <title>Censura – Statistiche (stacked, totale URL, IP)</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
  <script src="https://cdn.jsdelivr.net/npm/luxon@3/build/global/luxon.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-luxon@1"></script>
  <style>
    :root { color-scheme: light dark; }
    body { font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin: 16px; }
    .wrap { max-width: 1200px; margin: 0 auto; }
    header { margin-bottom: 12px; }
    .grid { display: grid; grid-template-columns: 1fr; gap: 16px; }
    .card { border: 1px solid color-mix(in srgb, CanvasText 20%, transparent); border-radius: 12px; padding: 12px; }
    .muted { opacity: .75; font-size: .9rem; }
    canvas { width: 100%; height: 420px; }
    .badges { display:flex; gap:8px; align-items:center; margin-bottom:8px; }
    .badge { padding:2px 8px; border-radius:999px; border:1px solid color-mix(in srgb, CanvasText 20%, transparent); }
    .row { display:flex; gap:10px; align-items:center; flex-wrap:wrap; }
    input[type="number"]{ width: 7ch; }
    select { padding: 2px 6px; }
    .spinner{ display:inline-block; width:1em; height:1em; border:.2em solid currentColor; border-right-color:transparent; border-radius:50%; animation:spin .8s linear infinite; vertical-align:-.2em;}
    @keyframes spin{to{transform:rotate(360deg)}}
    button.small { padding:6px 10px; border-radius:8px; border:1px solid color-mix(in srgb, CanvasText 30%, transparent); background:transparent; cursor:pointer;}
  </style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>Statistiche Censura</h1>
    <div class="row muted" style="gap:12px;">
      <div>Fonte: <?=htmlspecialchars($LOG_DIR . '/' . $BASE)?> (+ archivi .gz) — Cache: 1x/giorno</div>
      <form id="controls" class="row" method="get" style="margin-left:auto; gap:8px;">
        <label>Periodo:
          <input type="number" name="days" min="0" step="1" value="<?= (int)$DAYS_LIMIT ?>"> giorni
        </label>
        <label>Aggregazione:
          <select name="agg">
            <option value="day"  <?= $AGG==='day'?'selected':'' ?>>giorno</option>
            <option value="hour" <?= $AGG==='hour'?'selected':'' ?>>ora</option>
            <option value="run"  <?= $AGG==='run'?'selected':'' ?>>ogni run</option>
          </select>
        </label>
        <button>Applica</button>
        <button type="button" id="btnRebuild" class="small" title="Forza ricostruzione cache">Rigenera cache ora</button>
      </form>
    </div>
  </header>

  <div id="notice" class="card" style="display:none; margin-bottom:12px;"></div>

  <div class="grid">
    <!-- Grafico 1: categorie stacked -->
    <div class="card">
      <div class="badges">
        <span class="badge">Stacked area</span>
        <span class="muted">Categorie (No.Records) — <?=htmlspecialchars(strtoupper($AGG))?>, ultimi <?= (int)$DAYS_LIMIT ?> giorni</span>
      </div>
      <canvas id="chartCategories"></canvas>
    </div>

    <!-- Grafico 2: totale URL unici -->
    <div class="card">
      <div class="badges">
        <span class="badge">Linea</span>
        <span class="muted">Totale URL unici — <?=htmlspecialchars(strtoupper($AGG))?></span>
      </div>
      <canvas id="chartTotals"></canvas>
    </div>

    <!-- Grafico 3: IP totali -->
    <div class="card">
      <div class="badges">
        <span class="badge">Linea</span>
        <span class="muted">IP totali (Total IPs) — <?=htmlspecialchars(strtoupper($AGG))?></span>
      </div>
      <canvas id="chartIPs"></canvas>
    </div>
  </div>
</div>

<script>
// ---- Status helpers ----
async function checkStatus() {
  const res = await fetch(location.pathname + '?status=1', { cache: 'no-store' });
  if (!res.ok) throw new Error('status HTTP '+res.status);
  return res.json(); // {building, built_on, built_at}
}
async function warmup(force=false) {
  const url = location.pathname + (force ? '?warmup=1&rebuild=1' : '?warmup=1');
  const res = await fetch(url, { cache: 'no-store' });
  if (!res.ok) throw new Error('warmup HTTP '+res.status);
  return res.json(); // {building, built_on, built_at}
}
async function waitUntilReady(show) {
  let first = true;
  while (true) {
    const st = await checkStatus();
    if (!st.building) {
      if (!first) show(false, 'Cache pronta. Carico i grafici…');
      return;
    }
    show(first, 'Sto aggiornando la cache… potrebbe richiedere qualche minuto.');
    first = false;
    await new Promise(r => setTimeout(r, 3000));
  }
}

// ---- NDJSON fetch (robusto, ignora righe vuote) ----
async function fetchNDJSON(url, onItem) {
  const res = await fetch(url);
  if (!res.ok) throw new Error('HTTP '+res.status+' on '+url);
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = '';
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, {stream:true});
    const lines = buf.split('\n');
    buf = lines.pop();
    for (const line of lines) {
      const s = line.trim();
      if (!s) continue;
      try { onItem(JSON.parse(s)); } catch(e){ console.warn('NDJSON skip:', s.slice(0,120)); }
    }
  }
  const s = buf.trim();
  if (s) { try { onItem(JSON.parse(s)); } catch(e){ console.warn('NDJSON tail skip:', s.slice(0,120)); } }
}

const notice = document.getElementById('notice');
function showNotice(msg, loading=false) {
  notice.innerHTML = (loading ? '<span class="spinner"></span> ' : '') + msg;
  notice.style.display = 'block';
}
document.getElementById('btnRebuild').addEventListener('click', async () => {
  try {
    showNotice('Avvio ricostruzione cache…', true);
    const st = await warmup(true); // forza rebuild
    if (!st.building) {
      showNotice('Cache già aggiornata. Carico i grafici…', true);
    } else {
      await waitUntilReady((first, msg) => showNotice(msg, true));
    }
    // refresh grafici:
    location.reload();
  } catch (e) {
    console.error(e);
    showNotice('Errore nel rebuild: ' + e.message);
  }
});

(async function main(){
  // 1) Avvia warmup SUBITO per coprire la "prima visita"
  try {
    const st = await warmup(false);
    if (st.building) {
      // se il rebuild è partito ora, mostra banner e attendi
      await waitUntilReady((first, msg) => showNotice(msg, true));
    }
  } catch (e) {
    // Se warmup fallisce, ripieghiamo sul controllo status
    console.warn('warmup fallito:', e);
  }

  try {
    const baseUrl = location.pathname + (location.search || '');
    const qsSep = location.search ? '&' : '?';

    // 2) Categorie
    const byTs = new Map(); const allCats = new Set();
    await fetchNDJSON(baseUrl + qsSep + 'data=summaries', row => {
      byTs.set(row.ts, row.cats || {});
      for (const k in (row.cats || {})) allCats.add(k);
    });
    const tsList = Array.from(byTs.keys()).sort();
    const catList = Array.from(allCats).sort();
    const catDatasets = catList.map(cat => ({
      label: cat,
      data: tsList.map(ts => ({ x: ts, y: (byTs.get(ts)[cat] ?? 0) })),
      parsing: { xAxisKey:'x', yAxisKey:'y' },
      pointRadius: 0, borderWidth: 1.2, tension: 0.2, fill: 'origin', stack: 'urls'
    }));

    // 3) Totali URL
    const totSeries = [];
    await fetchNDJSON(baseUrl + qsSep + 'data=totals', row => { if ('total' in row) totSeries.push({ x: row.ts, y: row.total }); });
    totSeries.sort((a,b) => a.x.localeCompare(b.x));

    // 4) IP
    const ipSeries = [];
    await fetchNDJSON(baseUrl + qsSep + 'data=ips', row => { if ('ips' in row) ipSeries.push({ x: row.ts, y: row.ips }); });
    ipSeries.sort((a,b) => a.x.localeCompare(b.x));

    // 5) Grafici (decimazione + no animazioni)
    const commonOpts = {
      responsive: true, animation: false,
      interaction: { mode: 'nearest', intersect: false },
      plugins: { legend: { position: 'top' }, tooltip: { intersect: false }, decimation: { enabled: true, algorithm: 'lttb', samples: 800 } }
    };

    new Chart(document.getElementById('chartCategories'), {
      type: 'line',
      data: { datasets: catDatasets },
      options: {
        ...commonOpts, elements: { line: { fill: true } },
        scales: {
          x: { type: 'time', time: { tooltipFormat: 'dd/MM/yyyy' }, stacked: true, title: { display:true, text:'Tempo' } },
          y: { beginAtZero: true, stacked: true, title: { display:true, text:'No.Records per categoria' } }
        },
        plugins: { ...commonOpts.plugins, title: { display: true, text: 'URL per categoria (stacked)' } }
      }
    });

    new Chart(document.getElementById('chartTotals'), {
      type: 'line',
      data: { datasets: [{ label: 'Totale URL unici', data: totSeries, parsing: { xAxisKey: 'x', yAxisKey: 'y' }, pointRadius: 0, borderWidth: 1.6, tension: 0.2 }] },
      options: {
        ...commonOpts,
        scales: {
          x: { type: 'time', time: { tooltipFormat: 'dd/MM/yyyy' }, title: { display:true, text:'Tempo' } },
          y: { beginAtZero: true, title: { display:true, text:'Totale URL unici' } }
        },
        plugins: { ...commonOpts.plugins, title: { display: true, text: 'Totale URL unici nel tempo' } }
      }
    });

    new Chart(document.getElementById('chartIPs'), {
      type: 'line',
      data: { datasets: [{ label: 'IP bloccati (Total IPs)', data: ipSeries, parsing: { xAxisKey: 'x', yAxisKey: 'y' }, pointRadius: 0, borderWidth: 1.5, tension: 0.2 }] },
      options: {
        ...commonOpts,
        scales: {
          x: { type: 'time', time: { tooltipFormat: 'dd/MM/yyyy' }, title: { display:true, text:'Tempo' } },
          y: { beginAtZero: true, title: { display:true, text:'Conteggio IP' } }
        },
        plugins: { ...commonOpts.plugins, title: { display: true, text: 'IP totali nel tempo' } }
      }
    });

    // nascondi banner dopo il rendering
    notice.style.display = 'none';
  } catch (e) {
    console.error(e);
    showNotice('Errore nel caricamento dati: ' + e.message);
  }
})();
</script>
</body>
</html>

