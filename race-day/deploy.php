<?php
/* =============================================================
   Instant deploy.

   Hitting this URL with the write token pulls the current files
   straight from GitHub and writes them next to itself. No git on
   the server, no shell access, no FTP credentials anywhere —
   just an HTTPS fetch.

       https://singa.studio/utct2026/deploy.php?key=YOUR-TOKEN

   secret.php and data/ are never touched.
   ============================================================= */

const RAW  = 'https://raw.githubusercontent.com/joshkrige/utct-hub/main/race-day/';
const FILES = ['index.html', 'api.php', 'sw.js', 'manifest.webmanifest'];

header('Content-Type: text/plain; charset=utf-8');
header('Cache-Control: no-store');

$token = '';
if (is_file(__DIR__ . '/secret.php')) {
    $t = include __DIR__ . '/secret.php';
    if (is_string($t) && $t !== '') $token = $t;
}
if ($token === '' || !isset($_GET['key']) || !hash_equals($token, (string) $_GET['key'])) {
    http_response_code(403);
    echo "forbidden\n";
    exit;
}

function fetch_url(string $url): ?string {
    if (function_exists('curl_init')) {
        $ch = curl_init($url);
        curl_setopt_array($ch, [
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_FOLLOWLOCATION => true,
            CURLOPT_TIMEOUT        => 30,
            CURLOPT_USERAGENT      => 'utct-deploy',
        ]);
        $body = curl_exec($ch);
        $code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        curl_close($ch);
        if ($body !== false && $code === 200) return $body;
        return null;
    }
    if (ini_get('allow_url_fopen')) {
        $ctx = stream_context_create(['http' => ['timeout' => 30, 'user_agent' => 'utct-deploy']]);
        $body = @file_get_contents($url, false, $ctx);
        return $body === false ? null : $body;
    }
    return null;
}

$results = [];
$failed  = 0;

/* Fetch everything first. A half-written deploy is worse than none, so
   nothing is written unless every file came down intact. */
$bodies = [];
foreach (FILES as $f) {
    $body = fetch_url(RAW . $f . '?t=' . time());
    if ($body === null || strlen($body) < 200) {
        $results[] = sprintf('%-24s FETCH FAILED', $f);
        $failed++;
        continue;
    }
    $bodies[$f] = $body;
}

if ($failed > 0) {
    http_response_code(502);
    echo "nothing written — some files could not be fetched\n\n";
    echo implode("\n", $results), "\n";
    exit;
}

foreach ($bodies as $f => $body) {
    $dest = __DIR__ . '/' . $f;
    $old  = is_file($dest) ? (string) file_get_contents($dest) : '';
    if ($old === $body) {
        $results[] = sprintf('%-24s unchanged  (%d bytes)', $f, strlen($body));
        continue;
    }
    $tmp = $dest . '.' . getmypid() . '.tmp';
    if (@file_put_contents($tmp, $body, LOCK_EX) === false || !@rename($tmp, $dest)) {
        @unlink($tmp);
        $results[] = sprintf('%-24s WRITE FAILED', $f);
        $failed++;
        continue;
    }
    $results[] = sprintf('%-24s updated    (%d bytes)', $f, strlen($body));
}

http_response_code($failed ? 500 : 200);
echo ($failed ? "deploy finished with errors" : "deploy ok"), "  ",
     gmdate('Y-m-d H:i:s'), " UTC\n\n";
echo implode("\n", $results), "\n";
