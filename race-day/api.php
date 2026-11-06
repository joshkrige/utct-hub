<?php
/* =============================================================
   UTCT 100 tracker — tiny JSON backend.
   Drop this next to index.html on any PHP host. Nothing else needed:
   it creates its own data/ folder on first run.

   GET  api.php            -> { events: [...], config: {...} }
   POST api.php  (JSON)    -> { token, kind:"event"|"config", payload }
                              writes require the token below.

   CHANGE THE TOKEN before you share any link.
   ============================================================= */

/* The token lives in secret.php, which is NOT in git — so this file can sit in a
   public repo without handing anyone write access. secret.php is one line:
       <?php return 'your-token-here';
   Create it once on the server; it is never overwritten by a deploy. */
$RUNNER_TOKEN = 'no-token-configured';
if (is_file(__DIR__ . '/secret.php')) {
    $t = include __DIR__ . '/secret.php';
    if (is_string($t) && $t !== '') $RUNNER_TOKEN = $t;
}
const MAX_EVENTS = 500;

$dir  = __DIR__ . '/data';
$file = $dir . '/state.json';

header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store, no-cache, must-revalidate');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Headers: Content-Type');
header('Access-Control-Allow-Methods: GET, POST, OPTIONS');

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') { http_response_code(204); exit; }

/* ---- storage ---- */
if (!is_dir($dir)) {
    @mkdir($dir, 0775, true);
    @file_put_contents($dir . '/.htaccess', "Require all denied\nDeny from all\n");
}

function load_state(string $file): array {
    $blank = ['events' => [], 'config' => new stdClass()];
    if (!is_file($file)) return $blank;
    $raw = @file_get_contents($file);
    if ($raw === false || $raw === '') return $blank;
    $j = json_decode($raw, true);
    if (!is_array($j)) return $blank;
    return [
        'events' => isset($j['events']) && is_array($j['events']) ? $j['events'] : [],
        'config' => isset($j['config']) && is_array($j['config']) ? $j['config'] : [],
    ];
}

function save_state(string $file, array $state): bool {
    $tmp = $file . '.' . getmypid() . '.tmp';
    $json = json_encode($state, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE);
    if ($json === false) return false;
    if (@file_put_contents($tmp, $json, LOCK_EX) === false) return false;
    return @rename($tmp, $file);          // atomic swap: a reader never sees a half file
}

function out(array $state, int $code = 200): void {
    http_response_code($code);
    $cfg = $state['config'];
    echo json_encode([
        'events' => array_values($state['events']),
        'config' => (is_array($cfg) && count($cfg)) ? $cfg : new stdClass(),
        'now'    => round(microtime(true) * 1000),
    ], JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE);
}

/* ---- read ---- */
if ($_SERVER['REQUEST_METHOD'] === 'GET') { out(load_state($file)); exit; }

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    echo json_encode(['error' => 'method not allowed']);
    exit;
}

/* ---- write ---- */
$body = json_decode(file_get_contents('php://input'), true);
if (!is_array($body)) {
    http_response_code(400);
    echo json_encode(['error' => 'bad json']);
    exit;
}
if (!isset($body['token']) || !hash_equals($RUNNER_TOKEN, (string) $body['token'])) {
    http_response_code(403);
    echo json_encode(['error' => 'bad token']);
    exit;
}

$lock = @fopen($dir . '/.lock', 'c');
if ($lock) { flock($lock, LOCK_EX); }

$state  = load_state($file);
$kind   = $body['kind'] ?? '';
$p      = $body['payload'] ?? null;

if ($kind === 'event' && is_array($p) && isset($p['id'])) {
    $id = (string) $p['id'];
    $byId = [];
    foreach ($state['events'] as $e) { if (isset($e['id'])) $byId[(string) $e['id']] = $e; }

    if (!empty($p['deleted'])) {
        unset($byId[$id]);
    } else {
        $cp   = isset($p['cp']) ? (int) $p['cp'] : -1;
        $type = ($p['type'] ?? '') === 'out' ? 'out' : 'in';
        $t    = isset($p['t']) ? (float) $p['t'] : round(microtime(true) * 1000);
        if ($cp < 0 || $cp > 40) {
            http_response_code(400);
            echo json_encode(['error' => 'bad cp']);
            if ($lock) { flock($lock, LOCK_UN); fclose($lock); }
            exit;
        }
        /* one IN and one OUT per checkpoint — a re-tap corrects, never duplicates */
        foreach ($byId as $k => $e) {
            if ((int) ($e['cp'] ?? -1) === $cp && ($e['type'] ?? '') === $type && $k !== $id) unset($byId[$k]);
        }
        $byId[$id] = [
            'id' => $id, 'cp' => $cp, 'type' => $type, 't' => $t,
            'src' => preg_replace('/[^a-z]/', '', (string) ($p['src'] ?? 'runner')),
        ];
    }
    $events = array_values($byId);
    usort($events, fn($a, $b) => ($a['t'] <=> $b['t']));
    if (count($events) > MAX_EVENTS) $events = array_slice($events, -MAX_EVENTS);
    $state['events'] = $events;

} elseif ($kind === 'tick' && is_array($p) && isset($p['key'])) {
    /* One job tick. Merged key by key so two crew ticking different jobs at the
       same stop never overwrite each other. */
    $cfg = is_array($state['config']) ? $state['config'] : [];
    $ticks = isset($cfg['ticks']) && is_array($cfg['ticks']) ? $cfg['ticks'] : [];
    $key = preg_replace('/[^0-9:]/', '', (string) $p['key']);
    if ($key === '' || strlen($key) > 12) {
        http_response_code(400);
        echo json_encode(['error' => 'bad tick key']);
        if ($lock) { flock($lock, LOCK_UN); fclose($lock); }
        exit;
    }
    if (!empty($p['on'])) { if (count($ticks) < 400) $ticks[$key] = true; }
    else unset($ticks[$key]);
    $cfg['ticks'] = $ticks;
    $state['config'] = $cfg;

} elseif ($kind === 'config' && is_array($p)) {
    $cfg = is_array($state['config']) ? $state['config'] : [];

    if (isset($p['ticks']) && is_array($p['ticks'])) {
        $t = [];
        foreach ($p['ticks'] as $k => $v) {
            $k = preg_replace('/[^0-9:]/', '', (string) $k);
            if ($k !== '' && $v && count($t) < 400) $t[$k] = true;
        }
        $cfg['ticks'] = $t;
    }
    if (isset($p['targetSec'])) $cfg['targetSec'] = max(28800, min(93600, (int) $p['targetSec']));
    if (isset($p['startMs']))   $cfg['startMs']   = (float) $p['startMs'];
    if (isset($p['needs']) && is_array($p['needs'])) {
        $items = [];
        foreach ((array) ($p['needs']['items'] ?? []) as $it) {
            $it = trim(mb_substr((string) $it, 0, 24));
            if ($it !== '' && count($items) < 20) $items[] = $it;
        }
        $cfg['needs'] = ['items' => $items, 't' => (float) ($p['needs']['t'] ?? round(microtime(true) * 1000))];
    }
    $state['config'] = $cfg;

} else {
    http_response_code(400);
    echo json_encode(['error' => 'bad payload']);
    if ($lock) { flock($lock, LOCK_UN); fclose($lock); }
    exit;
}

$ok = save_state($file, $state);
if ($lock) { flock($lock, LOCK_UN); fclose($lock); }

out($state, $ok ? 200 : 500);
