#!/usr/bin/env python3
import argparse
import ast
import json
import math
import re
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
FACTS = HERE / "facts.json"
TOP_FILES = ["README.md", "SKILL.md", "llms.txt", "llms-full.txt", "context7.json"]
FENCE = re.compile(r"^[ \t]*```([\w+-]*)[^\n]*\n(.*?)^[ \t]*```[ \t]*$", re.M | re.S)
JS_LANGS = ("javascript", "js", "jsx", "typescript", "ts", "tsx")
PY_LANGS = ("python", "py")
SH_LANGS = ("bash", "sh", "shell", "")
GO_LANGS = ("go", "golang")

PRODUCT_FILES = {
    "marketCategories.ts": "packages/backend/src/config/marketCategories.ts",
    "wsOrderbook.ts": "packages/backend/src/routes/wsOrderbook.ts",
    "OrderbookManager.ts": "packages/backend/src/collectors/OrderbookManager.ts",
    "publicStats.ts": "packages/backend/src/routes/publicStats.ts",
    "markets.ts": "packages/backend/src/routes/markets.ts",
    "tierService.ts": "packages/backend/src/services/tierService.ts",
    "index.ts": "packages/backend/src/index.ts",
    "validateQuery.ts": "packages/backend/src/middleware/validateQuery.ts",
}
ROUTE_PROBES = {
    "live": ["live_btc_5m.json", "live_hit_price.json"],
    "history_recent": ["history_recent.json"],
    "history": ["history.json"],
    "by_slug": ["by_slug.json"],
    "by_slug_orderbook": ["by_slug_orderbook.json"],
    "orderbook": ["orderbook.json"],
    "snapshots": ["snapshots.json"],
    "summary": ["summary.json"],
    "trades": ["trades.json"],
    "api_snapshot": ["api_snapshot.json"],
    "api_snapshot_latest": ["api_snapshot_latest.json"],
    "health": ["health.json"],
}
CODE_ONLY = {
    "by_slug": ["event_title", "neg_risk_id"],
    "snapshots": ["interval", "data[].best_bid_size", "data[].best_ask_size", "data[].bids", "data[].asks"],
    "api_snapshot_latest": ["[].crypto", "[].crypto_price"],
}
CODE_ONLY_SOURCE = {
    "by_slug": "markets.ts (closed market)",
    "snapshots": "markets.ts (touchsize, includebook, interval)",
    "api_snapshot_latest": "snapshots.ts (LIGHT_COLS)",
}
HEADING_ROUTES = [
    ("by_slug_orderbook", r"^###\s+GET\s+/v1/markets/by-slug/:slug/orderbook\b"),
    ("by_slug", r"^###\s+GET\s+/v1/markets/by-slug/:slug\s*$"),
    ("history_recent", r"^###\s+GET\s+/v1/markets/history/recent\b"),
    ("history", r"^###\s+GET\s+/v1/markets/history\s*$"),
    ("live", r"^###\s+GET\s+/v1/markets/live\b"),
    ("orderbook", r"^###\s+GET\s+/v1/markets/:id/orderbook\b"),
    ("snapshots", r"^###\s+GET\s+/v1/markets/:id/snapshots\b"),
    ("summary", r"^###\s+GET\s+/v1/markets/:id/summary\b"),
    ("trades", r"^###\s+GET\s+/v1/markets/:id/trades\b"),
    ("api_snapshot_latest", r"^###\s+GET\s+/api/snapshot/latest\b"),
    ("api_snapshot", r"^###\s+GET\s+/api/snapshot\s*$"),
    ("health", r"^###\s+GET\s+/health\b"),
]
ROUTE_PATTERNS = [
    ("by_slug", r"/by-slug/|\bgetMarketBySlug\b|\bget_market_by_slug\b"),
    ("by_slug_orderbook", r"/by-slug/\S*?/orderbook"),
    ("history_recent", r"/history/recent"),
    ("history", r"/v1/markets/history(?!/)"),
    ("live", r"/v1/markets/live|\blistMarkets\b|\blist_markets\b|\bListMarkets\b|\buseMarkets\b|\bgetMarkets\b"),
    ("api_snapshot_latest", r"/api/snapshot/latest"),
    ("api_snapshot", r"/api/snapshot(?![/\w-])"),
    ("ws", r"/ws/orderbook|\bStreamOrderbook\b|\bstreamOrderbook\b|\buseOrderbook\b"),
    ("orderbook", r"\bgetOrderbook\b|\bget_orderbook\b|\bGetOrderbook\b"),
    ("snapshots", r"/snapshots\b|\bgetSnapshots\b|\bget_snapshots\b"),
    ("summary", r"/summary\b|\bgetMarketSummary\b|\bget_market_summary\b|\bGetMarketSummary\b"),
    ("trades", r"/trades\b"),
    ("health", r"/health\b"),
    ("public_stats", r"/v1/public-stats|\bgetPublicStats\b|\bget_public_stats\b"),
    ("categories", r"/v1/categories"),
]
MODEL_WORDS = ("Orderbook", "Snapshot", "Level", "Trade", "Market")
DENY = {"tokens", "tokenSide", "totalBidDepth", "totalAskDepth", "cryptoPriceStalenessMs", "snapshotCount", "cryptoPrices"}
JS_COLLIDE = {"status", "ok", "size", "message", "headers", "length"}
WS_KEYS = {"type", "status", "data", "markets", "code", "message", "tier"}
MARKETS_MSG_BYTES = 4_600_000
TF_CHANGE_DATE = "2026-07-15"
OLD_TIMEFRAMES = {"meeting"}
NEW_SNAPSHOT_PARAMS = ("interval", "touchsize", "count")


def load_docs(root):
    names = TOP_FILES + sorted(f"docs/{p.name}" for p in (root / "docs").glob("*.md"))
    return {n: (root / n).read_text() for n in names if (root / n).exists()}


def each_line(docs):
    for name, text in docs.items():
        for no, line in enumerate(text.splitlines(), 1):
            yield name, no, line


def fenced(docs):
    out = []
    for name, text in docs.items():
        for m in FENCE.finditer(text):
            heading = ""
            for prev in reversed(text[: m.start()].splitlines()):
                if prev.startswith("#"):
                    heading = prev
                    break
            out.append({
                "file": name,
                "line": text.count("\n", 0, m.start()) + 1,
                "lang": m.group(1).lower(),
                "code": m.group(2),
                "heading": heading,
            })
    return out


def where(name, no, line):
    return f"{name}:{no}: {line.strip()[:110]}"


def literal_keys(src, marker):
    body = src[src.index(marker) + len(marker):]
    depth, keys, parents, last = 1, {}, [None], None
    for line in body.splitlines():
        s = line.strip()
        if s.startswith("//"):
            continue
        m = re.match(r"(\w+)\s*\??\s*[:,]", s)
        if m:
            keys.setdefault(parents[-1], []).append(m.group(1))
            last = m.group(1)
        for ch in s:
            if ch == "{":
                depth += 1
                parents.append(last)
            elif ch == "}":
                depth -= 1
                parents.pop()
                if depth == 0:
                    return keys
    return keys


def flat_paths(obj, prefix=""):
    out = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            q = f"{prefix}.{k}" if prefix else k
            out.add(q)
            out |= flat_paths(v, q)
    elif isinstance(obj, list):
        for v in obj:
            out |= flat_paths(v, prefix + "[]")
    return out


def last_name(path):
    return path.replace("[]", "").split(".")[-1]


def build_facts(read, probe_dir):
    res = subprocess.run(
        ["node", str(HERE / "helper.cjs"), "configs"],
        input=read("marketCategories.ts"), capture_output=True, text=True, check=True,
    )
    facts = json.loads(res.stdout)
    ws = read("wsOrderbook.ts")
    facts["intervalMs"] = int(re.search(r"const broadcastInterval = setInterval\(.*?\n  \}, (\d+)\);", ws, re.S).group(1))
    m = re.search(r"sendSafe\(client\.ws, \{ (\w+): '(\w+)', (\w+): payload \}\)", ws)
    facts["msgKeys"], facts["msgType"] = [m.group(1), m.group(3)], m.group(2)
    facts["marketKeys"] = literal_keys(ws, "payload.push({")[None]
    facts["wsErrorCodeNumeric"] = re.search(r"type: 'error', code: 4003", ws) is not None
    facts["wsCloseCodes"] = sorted({int(c) for c in re.findall(r"ws\.close\((\d+),", ws)})
    ob = read("OrderbookManager.ts")
    facts["snapshotKeys"] = literal_keys(ob, "export interface Snapshot {")[None]
    facts["levelKeys"] = literal_keys(ob, "export interface PriceLevel {")[None]
    stats = literal_keys(read("publicStats.ts"), "res.json({")
    facts["statsKeys"], facts["statsExchangeKeys"] = stats[None], stats["exchange"]
    mk = read("markets.ts")
    route = mk[mk.index("router.get('/v1/categories'"):]
    facts["routeKeys"] = literal_keys(route, ".map(c => ({")[None] + [re.search(r"\{ (group): c\.group \}", route).group(1)]
    facts["historyMaxMarkets"] = int(re.search(r"HISTORY_MAX_MARKETS \|\| ([\d_]+)", mk).group(1).replace("_", ""))
    facts["snapshotTimeSwapOnly"] = ".replace('T', ' ').replace('Z', '')" in mk
    tiers = read("tierService.ts")
    facts["wsMax"] = {t: int(n) for t, n in re.findall(r"^\s*(free|pro|scale|enterprise):\s*\{[^}]*?wsMax:\s*(\d+)", tiers, re.M)}
    cats = read("marketCategories.ts")
    tfs = set()
    for line in cats.splitlines():
        s = line.strip()
        if s.startswith("timeframe:"):
            tfs |= set(re.findall(r"'([\w-]+)'", re.sub(r"===\s*'[\w-]+'", "", s)))
    tfs |= set(re.search(r"-updown-\(([\w|]+)\)", cats).group(1).split("|"))
    facts["timeframes"] = sorted(tfs)
    cors = re.search(r"const corsMiddleware = cors\(\{\s*origin: \(origin, callback\) => \{(.*?)\n  \},", read("index.ts"), re.S)
    body = [x.strip() for x in cors.group(1).splitlines() if x.strip() and not x.strip().startswith("//")]
    facts["corsAnyOrigin"] = body[-1] == "return callback(null, true);"
    allowed = re.search(r"const ALLOWED_PARAMS = new Set\(\[(.*?)\]\)", read("validateQuery.ts"), re.S).group(1)
    facts["allowedParams"] = sorted(re.findall(r"'(\w+)'", allowed))
    paths = {}
    for r, files in ROUTE_PROBES.items():
        ps = set()
        for f in files:
            ps |= flat_paths(json.loads((probe_dir / f).read_text()))
        ps |= set(CODE_ONLY.get(r, []))
        for q in list(ps):
            if last_name(q) in ("bids", "asks"):
                ps |= {q + "[].price", q + "[].size"}
        paths[r] = ps
    names = {r: {last_name(q) for q in ps} for r, ps in paths.items()}
    names["ws"] = WS_KEYS | set(facts["marketKeys"]) | set(facts["snapshotKeys"]) | set(facts["levelKeys"]) | names["live"]
    names["public_stats"] = set(facts["statsKeys"]) | set(facts["statsExchangeKeys"])
    names["categories"] = set(facts["routeKeys"])
    facts["routePaths"] = {r: sorted(v) for r, v in paths.items()}
    facts["routeNames"] = {r: sorted(v) for r, v in names.items()}
    facts["vocab"] = sorted(set().union(*names.values()) | DENY)
    hit = json.loads((probe_dir / "live_hit_price.json").read_text())
    facts["hitCoins"] = sorted({m["crypto"] for m in hit})
    facts["hitCount"] = len(hit)
    hist = json.loads((probe_dir / "history.json").read_text())
    recent = json.loads((probe_dir / "history_recent.json").read_text())
    facts["historyRowKeys"] = sorted(set().union(*map(set, hist["markets"])))
    facts["historyRecentRowKeys"] = sorted(set().union(*map(set, recent["markets"])))
    return facts


def write_facts(args):
    repo, ref = Path(args.product), args.ref

    def read(short):
        return subprocess.run(
            ["git", "-C", str(repo), "show", f"{ref}:{PRODUCT_FILES[short]}"],
            capture_output=True, text=True, check=True,
        ).stdout

    commit = subprocess.run(["git", "-C", str(repo), "rev-parse", ref], capture_output=True, text=True, check=True).stdout.strip()
    facts = {"source": {"product": f"{ref} {commit}", "probes": args.probe_date}}
    facts.update(build_facts(read, Path(args.probe)))
    Path(args.facts).write_text(json.dumps(facts, indent=1, sort_keys=True) + "\n")
    print(f"wrote {args.facts}: product {commit[:7]}, probes {args.probe_date}")


def load_facts(path):
    facts = json.loads(Path(path).read_text())
    facts["timeframes"] = set(facts["timeframes"])
    facts["vocab"] = set(facts["vocab"])
    facts["routePaths"] = {r: set(v) for r, v in facts["routePaths"].items()}
    facts["routeNames"] = {r: set(v) for r, v in facts["routeNames"].items()}
    return facts


def check_one_coin(docs, facts):
    bad = []
    old_text = re.compile(r"one or more crypto|multi-crypto subscri|subscribe to (?:all|multiple|several) crypto", re.I)
    old_code = re.compile(r"[\"']unsubscribe[\"']|resubscribe|\bsubscriptions\s*[:=]|_subscriptions\b|getSubscriptions")
    loop = re.compile(r"^\s*for\b|\.forEach\(|\brange\b")
    connect = re.compile(r"new WebSocket\(|websockets\.connect\(|create_connection\(|WebSocketApp\(|Dial\(")
    for name, text in docs.items():
        lines = text.splitlines()
        for i, line in enumerate(lines):
            if old_text.search(line) or old_code.search(line):
                bad.append(where(name, i + 1, line))
            elif re.search(r"[\"']subscribe[\"']", line) and re.search(r"send|dumps|WriteJSON", line):
                for j in range(i - 1, max(i - 7, -1), -1):
                    if loop.search(lines[j]):
                        if not any(connect.search(x) for x in lines[j:i]):
                            bad.append(where(name, i + 1, line) + "  [subscribe in a loop on one connection]")
                        break
    rule = re.compile(r"one coin|one connection for each coin|one connection per coin", re.I)
    for name in ("README.md", "llms.txt", "llms-full.txt", "docs/websocket.md", "SKILL.md"):
        if not rule.search(docs.get(name, "")):
            bad.append(f"{name}: does not say one coin per connection")
    lim = re.compile(r"\b(Free|Pro|Scale|Enterprise)\b\s*\(?\s*(\d+)")
    table = re.compile(r"^\|\s*(Free|Pro|Scale|Enterprise)\s*\|\s*(\d+)")
    for name, no, line in each_line(docs):
        pairs = lim.findall(line) if re.search(r"connection", line, re.I) else []
        if name == "docs/websocket.md":
            pairs += table.findall(line)
        for tier, n in pairs:
            if int(n) != facts["wsMax"][tier.lower()]:
                bad.append(where(name, no, line) + f"  [code: {tier} {facts['wsMax'][tier.lower()]}]")
    info = ["code: wsMax " + ", ".join(f"{k} {v}" for k, v in facts["wsMax"].items())]
    return bad, info


def book_math(s, tag):
    out = []
    bids, asks = s.get("bids"), s.get("asks")
    if not (isinstance(bids, list) and isinstance(asks, list) and bids and asks):
        return out
    want = {
        "bestBid": max(l["price"] for l in bids),
        "bestAsk": min(l["price"] for l in asks),
        "bidDepth": sum(l["price"] * l["size"] for l in bids),
        "askDepth": sum(l["price"] * l["size"] for l in asks),
    }
    want["midPrice"] = (want["bestBid"] + want["bestAsk"]) / 2
    want["spread"] = want["bestAsk"] - want["bestBid"]
    for k, v in want.items():
        if k in s and not math.isclose(s[k], v, abs_tol=1e-9):
            out.append(f"{tag}: {k} {s[k]}; the code would give {v:g}")
    return out


def orderbook_problems(obj, tag, facts):
    out = []
    if sorted(obj) != sorted(facts["msgKeys"]):
        out.append(f"{tag}: message keys {sorted(obj)}; code {facts['msgKeys']}")
    markets = obj.get("markets")
    if not isinstance(markets, list) or not markets:
        return out + [f"{tag}: markets is not a list of markets"]
    for m in markets:
        if sorted(m) != sorted(facts["marketKeys"]):
            out.append(f"{tag}: market keys {sorted(m)}; code {facts['marketKeys']}")
        for side in ("up", "down"):
            s = m.get(side)
            if s is None:
                continue
            extra = sorted(set(s) - set(facts["snapshotKeys"]))
            if extra:
                out.append(f"{tag}: {side} has keys that Snapshot does not have: {extra}")
            for level in s.get("bids", []) + s.get("asks", []):
                if sorted(level) != sorted(facts["levelKeys"]):
                    out.append(f"{tag}: {side} level keys {sorted(level)}")
            out += book_math(s, f"{tag} {side}")
    return out


def check_orderbook(docs, blocks, facts):
    bad = []
    for name, no, line in each_line(docs):
        typed = re.search(r"type", line, re.I) and re.search(r"[\"']snapshot[\"']", line)
        if typed or re.search(r"(?:emit|\.on)\(\s*[\"']snapshot[\"']", line):
            bad.append(where(name, no, line))
    found = Counter()
    for b in blocks:
        try:
            obj = json.loads(b["code"])
        except ValueError:
            continue
        if isinstance(obj, dict) and obj.get("type") == facts["msgType"]:
            found[b["file"]] += 1
            bad += orderbook_problems(obj, f"{b['file']}:{b['line']}", facts)
    for name in ("docs/websocket.md", "llms-full.txt"):
        if not found[name]:
            bad.append(f"{name}: no JSON example of the '{facts['msgType']}' message")
    phrase = f"every {facts['intervalMs'] / 1000:g} seconds"
    for name in ("README.md", "llms.txt", "llms-full.txt", "docs/websocket.md"):
        if phrase not in docs.get(name, ""):
            bad.append(f"{name}: does not say '{phrase}'")
    info = [
        f"code: type '{facts['msgType']}', keys {facts['msgKeys']}, market keys {facts['marketKeys']}, interval {facts['intervalMs']} ms",
        f"JSON examples checked: {dict(found)}",
    ]
    return bad, info


def check_realtime(docs):
    allowed = ("Records trades in real-time from Polymarket",)
    bad, kept = [], []
    for name, no, line in each_line(docs):
        if re.search(r"real[- ]?time", line, re.I):
            (kept if any(a in line for a in allowed) else bad).append(where(name, no, line))
    return bad, [f"kept (capture side): {k}" for k in kept]


def check_public_stats(blocks, facts):
    bad, seen = [], set()
    for b in blocks:
        if "/v1/public-stats" not in b["heading"] or b["lang"] != "json":
            continue
        seen.add(b["file"])
        tag = f"{b['file']}:{b['line']}"
        try:
            obj = json.loads(b["code"])
        except ValueError as e:
            bad.append(f"{tag}: JSON does not parse: {e}")
            continue
        if sorted(obj) != sorted(facts["statsKeys"]):
            bad.append(f"{tag}: keys {list(obj)}; code {facts['statsKeys']}")
        ex = obj.get("exchange")
        if not isinstance(ex, dict) or sorted(ex) != sorted(facts["statsExchangeKeys"]):
            bad.append(f"{tag}: exchange {sorted(ex) if isinstance(ex, dict) else ex}; code {facts['statsExchangeKeys']}")
        if not isinstance(obj.get("snapshot_count"), str):
            bad.append(f"{tag}: snapshot_count is not a string")
    for name in ("docs/api-reference.md", "llms-full.txt"):
        if name not in seen:
            bad.append(f"{name}: no public-stats JSON example")
    return bad, [f"code keys {facts['statsKeys']}, exchange {facts['statsExchangeKeys']}"]


def check_categories(docs, blocks, facts):
    bad, seen = [], Counter()
    enabled = {c["id"]: c for c in facts["configs"] if c["enabled"]}
    for b in blocks:
        if "/v1/categories" not in b["heading"] or b["lang"] != "json":
            continue
        tag = f"{b['file']}:{b['line']}"
        try:
            arr = json.loads(b["code"])
        except ValueError as e:
            bad.append(f"{tag}: JSON does not parse: {e}")
            continue
        if not isinstance(arr, list) or not arr:
            bad.append(f"{tag}: not an array of configs: {b['code'].strip()[:80]}")
            continue
        for item in arr:
            cid = item.get("id") if isinstance(item, dict) else None
            cfg = enabled.get(cid)
            if cfg is None:
                bad.append(f"{tag}: id {cid!r} is not an enabled config")
                continue
            seen[b["file"]] += 1
            want = [k for k in facts["routeKeys"] if k != "group" or cfg["group"]]
            if sorted(item) != sorted(want):
                bad.append(f"{tag}: {cid} keys {sorted(item)}; route gives {sorted(want)}")
            for k in ("category", "group", "displayName", "captureIntervalMs", "refreshIntervalMs"):
                if k in item and item[k] != cfg[k]:
                    bad.append(f"{tag}: {cid} {k} {item[k]!r}; code {cfg[k]!r}")
            if not isinstance(item.get("activeMarkets"), int):
                bad.append(f"{tag}: {cid} activeMarkets is not a number")
    for name in ("docs/api-reference.md", "llms-full.txt"):
        if not seen[name]:
            bad.append(f"{name}: no categories JSON example with a config of the code")
    listed = {}
    for no, line in enumerate(docs.get("docs/overview.md", "").splitlines(), 1):
        m = re.match(r"^\|\s*\*\*(\w+)\*\*\s*\|([^|]*)\|", line)
        if not m:
            continue
        for cid in (x.strip(" `") for x in m.group(2).split(",")):
            if cid in ("", "--"):
                continue
            listed[cid] = m.group(1).lower()
            if cid not in enabled:
                bad.append(where("docs/overview.md", no, line) + f"  [{cid} is not an enabled config]")
            elif enabled[cid]["category"] != m.group(1).lower():
                bad.append(where("docs/overview.md", no, line) + f"  [{cid} is in {enabled[cid]['category']}]")
    missing = sorted(set(enabled) - set(listed))
    if missing:
        bad.append(f"docs/overview.md: table does not list {missing}")
    info = [f"code: {len(enabled)} enabled configs; example items checked: {dict(seen)}; overview ids: {len(listed)}"]
    return bad, info


def table_rows(lines, i):
    lo, hi = i, i
    while lo > 0 and lines[lo - 1].startswith("|"):
        lo -= 1
    while hi + 1 < len(lines) and lines[hi + 1].startswith("|"):
        hi += 1
    return [lines[k].split("|")[1] for k in range(lo, hi + 1) if k != i]


def check_counts(docs, facts):
    bad = []
    cats = sorted({c["category"] for c in facts["configs"] if c["enabled"]})
    for name, no, line in each_line(docs):
        for m in re.finditer(r"\b(\d+)\s+(?:market\s+)?categories\b", line, re.I):
            if int(m.group(1)) != len(cats):
                bad.append(where(name, no, line) + f"  [code: {len(cats)}]")
        named = {c for c in cats if re.search(rf"\b{c}\b", line, re.I)}
        missing = set(cats) - named
        if line.startswith("|") and missing:
            others = " ".join(table_rows(docs[name].splitlines(), no - 1))
            missing = {c for c in missing if not re.search(rf"\b{c}\b", others, re.I)}
        if len(named) >= 4 and missing:
            bad.append(where(name, no, line) + f"  [no {sorted(missing)}]")
        for m in re.finditer(r"\b(\d+)\s+(?:major\s+)?cities\b", line, re.I):
            if int(m.group(1)) != facts["cityCount"] or not re.search(r"up to\s+$", line[: m.start()], re.I):
                bad.append(where(name, no, line) + f"  [code: up to {facts['cityCount']}]")
    info = [f"code: {len(cats)} categories {cats}; {facts['cityCount']} cities in DAILY_TEMP_CITIES"]
    return bad, info


def parse_json_text(code):
    try:
        json.loads(code)
    except ValueError as e:
        rows = [r for r in code.splitlines() if r.strip()]
        if "Extra data" not in str(e):
            raise
        for r in rows:
            json.loads(r)


def check_syntax(blocks, scope):
    bad, done, skipped, js = [], Counter(), Counter(), []
    mine = [b for b in blocks if b["file"] in scope]
    gofmt = shutil.which("gofmt")
    for b in mine:
        tag = f"{b['file']}:{b['line']}"
        if b["lang"] == "json":
            try:
                parse_json_text(b["code"])
                done["json"] += 1
            except ValueError as e:
                bad.append(f"{tag}: JSON: {e}")
        elif b["lang"] in PY_LANGS:
            try:
                compile(b["code"], tag, "exec", flags=ast.PyCF_ONLY_AST | ast.PyCF_ALLOW_TOP_LEVEL_AWAIT)
                done["python"] += 1
            except SyntaxError as e:
                bad.append(f"{tag}: Python: {e}")
        elif b["lang"] in GO_LANGS:
            if gofmt is None:
                bad.append(f"{tag}: gofmt is not installed, so this Go block is not checked")
                continue
            res = subprocess.run([gofmt, "-e"], input=b["code"], capture_output=True, text=True)
            if res.returncode:
                bad.append(f"{tag}: Go: {(res.stderr.strip().splitlines() or ['gofmt failed'])[0]}")
            else:
                done["go"] += 1
        elif b["lang"] in JS_LANGS:
            js.append({"name": tag, "lang": b["lang"], "code": b["code"]})
            col0 = re.search(r"^\S[^\n]*\bawait\b", b["code"], re.M)
            loose = re.search(r"\bawait\b", b["code"]) and not re.search(r"\basync\b", b["code"])
            if "require(" in b["code"] and (col0 or loose):
                bad.append(f"{tag}: uses require() and top-level await: it fails as .js and as .mjs")
        else:
            skipped[b["lang"] or "plain"] += 1
    if js:
        res = subprocess.run(
            ["node", str(HERE / "helper.cjs"), "syntax"],
            input=json.dumps(js), capture_output=True, text=True, check=True,
        )
        for r in json.loads(res.stdout):
            if r["diags"]:
                bad.append(f"{r['name']}: {r['diags'][0]}")
            else:
                done["js/ts"] += 1
    return bad, [f"files: {len(scope)}", f"blocks: {len(mine)}; parse: {dict(done)}; not parsed: {dict(skipped)}"]


def block_routes(code):
    rs = {name for name, pat in ROUTE_PATTERNS if re.search(pat, code)}
    for m in re.finditer(r"/orderbook\b", code):
        pre = code[max(0, m.start() - 200): m.start()]
        seg = re.split(r"[\s\"'`(]", pre)[-1]
        if pre.endswith("/ws") or "by-slug" in seg:
            continue
        rs.add("orderbook")
    return rs


def names_in(text):
    out = []
    for part in text.split(","):
        n = part.split(":")[0].strip().lstrip(".").strip()
        if re.fullmatch(r"[A-Za-z_]\w*", n):
            out.append(n)
    return out


def js_reads(code):
    code = re.sub(r"(^|[^:\"'`])//[^\n]*", r"\1", code)
    reads, local = [], set()
    bodies = re.findall(r"(?:interface\s+\w+[^{\n]*|type\s+\w+\s*=\s*)\{(.*?)\n\}", code, re.S)
    for body in bodies:
        reads += re.findall(r"^\s*(?:readonly\s+)?(\w+)\??\s*:", body, re.M)
    code = re.sub(r"(?:interface\s+\w+[^{\n]*|type\s+\w+\s*=\s*)\{.*?\n\}", "", code, flags=re.S)
    for inline in re.findall(r"<\{([^{}]*)\}", code):
        reads += re.findall(r"(\w+)\??\s*:", inline)
    code = re.sub(r"<\{[^{}]*\}", "<T", code)
    for pat, rhs in re.findall(r"(?:const|let|var)\s*\{([^{}=]*)\}\s*=([^;\n]*)", code):
        if ".json()" in rhs:
            reads += names_in(pat)
    code = re.sub(r"(?:const|let|var)\s*\{[^{}=]*\}\s*=", "const _ =", code)
    reads += re.findall(r"(?<=[\w\)\]])\??\.(?!\.)([A-Za-z_]\w*)", code)
    reads += re.findall(r"\[\s*[\"'](\w+)[\"']\s*\]", code)
    local |= set(re.findall(r"(?<![?\w.])(\w+)\??\s*:(?!:)", code))
    local |= set(re.findall(r"[{,]\s*(\w+)\s*(?=[,}])", code))
    return [r for r in reads if r not in JS_COLLIDE], local


def py_reads(code):
    reads = re.findall(r"\[\s*[\"'](\w+)[\"']\s*\]", code) + re.findall(r"\.get\(\s*[\"'](\w+)[\"']", code)
    local = set(re.findall(r"[\"'](\w+)[\"']\s*:", code)) | set(re.findall(r"\b(\w+)\s*=(?!=)", code))
    return reads, local


def jq_reads(code):
    reads, local = [], set()
    for flt in re.findall(r"\bjq\b[^'\n]*'([^']*)'", code):
        reads += re.findall(r"\.([A-Za-z_]\w*)", flt)
        for obj in re.findall(r"\{([^{}]*)\}", flt):
            for part in obj.split(","):
                part = part.strip()
                if re.fullmatch(r"[A-Za-z_]\w*", part):
                    reads.append(part)
        local |= set(re.findall(r"([A-Za-z_]\w*)\s*:", flt))
    return reads, local


def go_reads(code):
    return re.findall(r"json:\"(\w+)", code), set()


def scoped_blocks(blocks, scope):
    return [b for b in blocks if b["file"] in scope]


def check_live_array(blocks, scope):
    bad, info, seen = [], [], 0
    for b in blocks:
        if b["lang"] == "json" and re.search(r"GET\s+/v1/markets/live\b", b["heading"]):
            seen += 1
            try:
                obj = json.loads(b["code"])
            except ValueError as e:
                bad.append(f"{b['file']}:{b['line']}: JSON does not parse: {e}")
                continue
            if not isinstance(obj, list):
                bad.append(f"{b['file']}:{b['line']}: the example is a {type(obj).__name__}; the route returns an array")
    read = re.compile(r"\??\.markets\b|\[\s*[\"']markets[\"']\s*\]|<\{\s*markets\s*:|json:\"markets\"|\{\s*markets\s*\}\s*=")
    new_fn = re.compile(r"^\s*(?:def |func |(?:export\s+)?(?:async\s+)?function\b|(?:export\s+)?const\s+\w+\s*=\s*(?:async\s*)?\()")
    for b in blocks:
        lines = b["code"].splitlines()
        for i, line in enumerate(lines):
            if "/v1/markets/live" not in line:
                continue
            for j in range(i, min(i + 12, len(lines))):
                if j > i and new_fn.search(lines[j]):
                    break
                if read.search(lines[j]):
                    msg = f"{b['file']}:{b['line'] + j + 1}: {lines[j].strip()[:90]}  [reads markets from /v1/markets/live]"
                    (bad if b["file"] in scope else info).append(msg if b["file"] in scope else "not checked: " + msg)
    return bad, [f"live JSON examples: {seen}"] + info


def model_tables(name, text):
    if name == "docs/data-model.md":
        start, level = 0, "## "
    elif "## Data Model Reference" in text:
        start, level = text.index("## Data Model Reference"), "### "
    else:
        return
    sect = text[start:]
    if level == "### " and "\n## " in sect[5:]:
        sect = sect[: sect.index("\n## ", 5)]
    base_no = text.count("\n", 0, start) + 1
    heading, field_table = "", False
    for k, line in enumerate(sect.splitlines()):
        if line.startswith(level):
            heading, field_table = line[len(level):], False
            continue
        if not line.startswith("|"):
            field_table = False
            continue
        cells = line.split("|")
        if re.match(r"^\|\s*Field\s*\|", line):
            field_table = True
            continue
        names = re.findall(r"`(\w+)`", cells[1]) if len(cells) > 1 else []
        if names:
            yield base_no + k, heading, field_table, names


def check_route_json(docs, blocks, facts, scope):
    bad, done = [], Counter()
    for b in scoped_blocks(blocks, scope):
        route = next((r for r, pat in HEADING_ROUTES if re.search(pat, b["heading"])), None)
        if route is None or b["lang"] != "json":
            continue
        tag = f"{b['file']}:{b['line']}"
        try:
            obj = json.loads(b["code"])
        except ValueError as e:
            bad.append(f"{tag}: {route}: JSON does not parse: {e}")
            continue
        extra = sorted(flat_paths(obj) - facts["routePaths"][route])
        if extra:
            bad.append(f"{tag}: {route}: keys the route does not return: {extra[:8]}")
        if route in ("orderbook", "by_slug_orderbook"):
            for side in ("up", "down"):
                if isinstance(obj.get(side), dict):
                    bad += book_math(obj[side], f"{tag} {side}")
        done[route] += 1
    paths = facts["routePaths"]
    model = {
        "Orderbook": {last_name(q) for q in paths["orderbook"] if q.startswith("up.") and q.count(".") == 1},
        "Snapshot": {last_name(q) for q in paths["snapshots"] if q.startswith("data[].") and q.count(".") == 1}
        | {last_name(q) for q in paths["api_snapshot"] if q.startswith("up.")},
        "Level": set(facts["levelKeys"]),
        "Trade": {last_name(q) for q in paths["trades"] if q.startswith("data[].")},
        "Market": {last_name(q) for q in paths["live"]},
    }
    for name in sorted(scope):
        for no, heading, field_table, names in model_tables(name, docs.get(name, "")):
            key = next((w for w in MODEL_WORDS if w in heading), None)
            allowed = model.get(key, set()) if field_table else facts["vocab"] - DENY
            done[f"{name}:{key or 'unmapped'}" if field_table else f"{name}:other"] += 1
            for n in names:
                if n not in allowed:
                    what = f"{key or 'no'} API object" if field_table else "any API object"
                    bad.append(f"{name}:{no}: {heading[:40]}: field `{n}` is not in {what}")
    src = [f"code-only keys: {r}: {CODE_ONLY[r]} ({CODE_ONLY_SOURCE[r]})" for r in CODE_ONLY]
    return bad, [f"route examples and model table rows checked: {dict(done)}"] + src


def check_field_reads(blocks, facts, scope):
    bad, done = [], Counter()
    names, vocab = facts["routeNames"], facts["vocab"]
    for b in scoped_blocks(blocks, scope):
        code, lang = b["code"], b["lang"]
        routes = block_routes(code)
        if not routes:
            continue
        if lang in JS_LANGS:
            reads, local = js_reads(code)
        elif lang in PY_LANGS:
            reads, local = py_reads(code)
        elif lang in GO_LANGS:
            reads, local = go_reads(code)
        elif lang in SH_LANGS:
            reads, local = jq_reads(code)
        else:
            continue
        allowed = set().union(*(names[r] for r in routes)) | local
        wrong = sorted({r for r in reads if (r in vocab and r not in allowed) or (r in DENY and r not in local)})
        tag = f"{b['file']}:{b['line']} ({lang or 'sh'}; {', '.join(sorted(routes))})"
        if wrong:
            bad.append(f"{tag}: reads {wrong}")
        if "orderbook" in routes and re.search(r"\.(UP|DOWN)\.\w|\[\s*[\"'](UP|DOWN)[\"']\s*\]\s*[\[.]", code):
            bad.append(f"{tag}: reads UP/DOWN keys; the orderbook route returns up and down")
        done[lang or "sh"] += 1
    return bad, [f"blocks with an API call checked: {dict(done)}; vocabulary: {len(vocab)} keys of {len(names)} routes"]


def check_websocat(blocks, facts):
    bad, seen = [], 0
    for b in blocks:
        code = b["code"]
        if "websocat" not in code or b["lang"] not in SH_LANGS:
            continue
        seen += 1
        tag = f"{b['file']}:{b['line']}"
        if re.search(r"(?<![\w-])-n1\b|(?<![\w-])-1\b|--one-message", code):
            bad.append(f"{tag}: -1 / --one-message stops after one message")
        if not re.search(r"(?<![\w-])-n\b|--no-close", code):
            bad.append(f"{tag}: no -n: the connection closes when the input ends")
        m = re.search(r"(?:-B|--buffer-size)[ =](\d+)", code)
        if not m or int(m.group(1)) < MARKETS_MSG_BYTES:
            bad.append(f"{tag}: no -B of {MARKETS_MSG_BYTES} bytes or more: the first markets message is split")
        auth = code.find('"type":"auth"')
        subs = [x.start() for x in re.finditer(r'"type"\s*:\s*"subscribe"', code)]
        wait = code.find("sleep", auth if auth >= 0 else 0)
        if len(subs) != 1:
            bad.append(f"{tag}: {len(subs)} subscribe messages; one connection follows one coin")
        elif not (0 <= auth < wait < subs[0]):
            bad.append(f"{tag}: subscribe is not sent after auth and a wait on the same connection")
    if not seen:
        bad.append("no websocat example")
    return bad, [f"websocat examples: {seen}; first markets message about {MARKETS_MSG_BYTES:,} bytes"]


def check_followups(docs, facts, scope):
    bad, info = [], []
    gl = docs.get("docs/glossary.md", "")
    line = next((x for x in gl.splitlines() if x.startswith("| **timeframe**")), "")
    named = {t for t in re.findall(r"[\w-]+", line) if t in facts["timeframes"] or t in OLD_TIMEFRAMES}
    missing = sorted(facts["timeframes"] - named)
    if missing:
        bad.append(f"docs/glossary.md: timeframe line does not name {missing}")
    if named & OLD_TIMEFRAMES and f"before {TF_CHANGE_DATE}" not in line:
        bad.append(f"docs/glossary.md: timeframe line names {sorted(named & OLD_TIMEFRAMES)} as current")
    info.append(f"code timeframes: {sorted(facts['timeframes'])}")
    for name, no, text in each_line(docs):
        if re.search(r"\bdeltas?\b", text, re.I) and re.search(r"Hyperliquid|L2 book", text):
            bad.append(where(name, no, text) + "  [Hyperliquid l2Book sends full books]")
        if "Binance" in text and re.search(r"price|trades", text, re.I) and not re.search(r"HYPE|Hyperliquid", text):
            bad.append(where(name, no, text) + "  [HYPE price comes from Hyperliquid allMids]")
        if re.search(r"real-time trades from Binance", text):
            bad.append(where(name, no, text) + "  [Binance bookTicker: best bid and ask, not trades]")
        if "cryptoPriceStalenessMs" in text:
            msg = where(name, no, text) + "  [no such field]"
            checked = name in scope | {"docs/glossary.md", "docs/troubleshooting.md"}
            (bad if checked else info).append(msg if checked else "not checked: " + msg)
    for name in ("llms-full.txt", "llms.txt", "docs/overview.md", "docs/glossary.md"):
        if "hit-price" not in docs.get(name, ""):
            bad.append(f"{name}: does not describe the hit-price markets")
    coins = set(facts["hitCoins"])
    for name, no, text in each_line(docs):
        if "hit-price" in text and "2026-11-11" in text:
            said = set(re.findall(r"\b(BTC|ETH|SOL|XRP|DOGE|HYPE|BNB)\b", text[text.index("hit-price"):]))
            if said != coins:
                bad.append(where(name, no, text) + f"  [live on 2026-11-11: {sorted(coins)}]")
            for n in re.findall(r"\b(\d+) markets\b", text):
                if int(n) != facts["hitCount"]:
                    bad.append(where(name, no, text) + f"  [live on 2026-11-11: {facts['hitCount']} markets]")
    info.append(f"live hit-price markets 2026-11-11: {facts['hitCount']} on {sorted(coins)}")
    return bad, info


def doc_section(text, pattern):
    m = re.search(pattern, text, re.M)
    if not m:
        return ""
    nxt = re.search(r"^#{2,3} ", text[m.end():], re.M)
    return text[m.start(): m.end() + (nxt.start() if nxt else len(text))]


def check_review1(docs, blocks, facts, scope):
    bad, info = [], []
    col0 = re.compile(r"^\S[^\n]*\bawait\b", re.M)
    for b in scoped_blocks(blocks, scope):
        tag = f"{b['file']}:{b['line']}"
        if b["lang"] in ("typescript", "ts") and col0.search(b["code"]) and not re.search(r"^\s*(import|export)\b", b["code"], re.M):
            bad.append(f"{tag}: TypeScript top-level await in a file with no import or export (tsc TS1375)")
        if b["lang"] in ("javascript", "js") and col0.search(b["code"]) and ".mjs" not in docs[b["file"]]:
            bad.append(f"{tag}: top-level await, but {b['file']} does not say to save the code as .mjs")
    calls_seen = 0
    for b in blocks:
        if b["file"] != "docs/cookbook.md":
            continue
        tag = f"{b['file']}:{b['line']}"
        if b["lang"] in ("javascript", "js"):
            calls = len(re.findall(r"\bawait fetch\(", b["code"]))
            checks = len(re.findall(r"\.ok\b", b["code"]))
        elif b["lang"] in PY_LANGS:
            calls = len(re.findall(r"\brequests\.get\(", b["code"]))
            checks = len(re.findall(r"raise_for_status\(\)|\.ok\b|\.status_code\b", b["code"]))
        else:
            continue
        calls_seen += calls
        if calls > checks:
            bad.append(f"{tag}: {calls} requests, {checks} status checks: a 401, 410 or 429 reply crashes or prints nothing")
    for name, no, text in each_line(docs):
        if name == "docs/cookbook.md" and re.search(r"\b(FROM|TO)\s*=\s*\"?20\d\d-\d\d-\d\d", text):
            bad.append(where(name, no, text) + "  [fixed date: a market from /v1/markets/live has no rows then]")
    full = docs.get("llms-full.txt", "")
    hist_keys, recent_keys = set(facts["historyRowKeys"]), set(facts["historyRecentRowKeys"])
    sec = doc_section(full, r"^###\s+GET\s+/v1/markets/history\s*$")
    intro = sec.split("**Query Parameters:**")[0]
    if "same keys as in `GET /v1/markets/history/recent`" in intro:
        claimed = recent_keys
    else:
        m = re.search(r"Each row has (.*?)\.", intro)
        claimed = set(re.findall(r"`(\w+)`", m.group(1))) if m else set()
    if claimed != hist_keys:
        bad.append(f"llms-full.txt GET /v1/markets/history rows: says {sorted(claimed - hist_keys)} that the rows lack, "
                   f"misses {sorted(hist_keys - claimed)}")
    cap = facts["historyMaxMarkets"]
    lim = re.search(r"^\| `limit` \|[^\n]*", sec, re.M)
    if not lim or "no limit" in lim.group(0) or f"{cap:,}" not in lim.group(0) or "result_too_large" not in lim.group(0):
        bad.append(f"llms-full.txt GET /v1/markets/history `limit`: without limit the route returns up to {cap:,} markets, "
                   "then 422 result_too_large (markets.ts HISTORY_MAX_MARKETS)")
    info.append(f"history rows: {len(hist_keys)} keys; history/recent rows: {len(recent_keys)} keys; HISTORY_MAX_MARKETS {cap:,}")
    if facts["snapshotTimeSwapOnly"]:
        snap = doc_section(full, r"^###\s+GET\s+/v1/markets/:id/snapshots\b")
        row = re.search(r"^\| `from` \|[^\n]*", snap, re.M)
        if not row or "ISO 8601" in row.group(0) or "+00:00" not in row.group(0):
            bad.append("llms-full.txt snapshots `from`: the route only swaps T and drops Z, so say the UTC Z form and that "
                       "an offset such as +00:00 fails")
    go = [b for b in blocks if b["file"] == "docs/sdks.md" and b["lang"] in GO_LANGS]
    for b in go:
        if facts["wsErrorCodeNumeric"] and re.search(r"authResp\s+map\[string\]string", b["code"]):
            bad.append(f"docs/sdks.md:{b['line']}: the auth reply is decoded as map[string]string, but the error reply "
                       "has a numeric code (wsOrderbook.ts)")
    if go:
        rest = go[0]
        defined = set(re.findall(r"^type (\w+) ", rest["code"], re.M))
        used = set(re.findall(r"(?:\*|\[\])([A-Z]\w*)\b", rest["code"]))
        if used - defined:
            bad.append(f"docs/sdks.md:{rest['line']}: the Go REST client block uses {sorted(used - defined)} but does not define it")
    info.append(f"cookbook requests checked: {calls_seen}; Go blocks: {len(go)}")
    return bad, info


def check_ws_stop(blocks, facts):
    bad, seen = [], 0
    opens = re.compile(r"new WebSocket\(|websockets\.connect\(|\.Dial\(")
    again = re.compile(r"reconnect|setTimeout\(\s*connect\b", re.I)
    for b in blocks:
        code = b["code"]
        if not (opens.search(code) and again.search(code)):
            continue
        seen += 1
        if "4003" not in code:
            bad.append(f"{b['file']}:{b['line']}: the client reconnects, but does not stop on close code 4003 "
                       "(invalid key, a plan without WebSocket access, or the connection limit)")
    info = [f"code: the server closes with {facts['wsCloseCodes']}; reconnecting clients checked: {seen}"]
    return bad, info


def check_alert_bot(docs, blocks):
    bad, seen = [], 0
    text = docs.get("docs/cookbook.md", "")
    lines = text.splitlines()
    start = next((i for i, x in enumerate(lines) if re.match(r"^## \d+\. Build a Spread Alert Bot", x)), None)
    if start is None:
        return ["docs/cookbook.md: no spread alert bot recipe"], []
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    intro = "\n".join(lines[start:end]).split("```")[0]
    if not ("429" in intro and "Retry-After" in intro and "410" in intro):
        bad.append(f"docs/cookbook.md:{start + 1}: the recipe does not state its retry rule (429 with Retry-After, 5xx, stop on 410)")
    for b in blocks:
        if b["file"] != "docs/cookbook.md" or not (start < b["line"] <= end):
            continue
        code, tag = b["code"], f"docs/cookbook.md:{b['line']} ({b['lang'] or 'sh'})"
        seen += 1
        if "429" not in code or not re.search(r"retry-after", code, re.I):
            bad.append(f"{tag}: does not wait the Retry-After seconds on HTTP 429")
        if not ("500" in code and "503" in code):
            bad.append(f"{tag}: does not retry HTTP 500 to 504")
        if re.search(r"\bthrow\b|raise_for_status\(\)", code):
            bad.append(f"{tag}: an error reply ends the bot with an exception")
        if not re.search(r"\bbreak\b|\breturn null\b", code):
            bad.append(f"{tag}: never stops on an error that a retry cannot fix (such as 401 or 410)")
    if seen < 3:
        bad.append(f"docs/cookbook.md:{start + 1}: {seen} code blocks; want JavaScript, Python and cURL")
    return bad, [f"spread alert bot blocks checked: {seen}"]


def check_cors_params(docs, facts):
    bad = []
    if facts["corsAnyOrigin"]:
        for name, no, line in each_line(docs):
            if re.search(r"does not set (?:permissive )?CORS|server-to-server communication", line, re.I):
                bad.append(where(name, no, line) + "  [index.ts: the API allows any origin]")
    want = [p for p in NEW_SNAPSHOT_PARAMS if p in facts["allowedParams"]]
    for name in ("llms-full.txt", "docs/api-reference.md"):
        sec = doc_section(docs.get(name, ""), r"^###\s+GET\s+/v1/markets/:id/snapshots\b")
        rows = set(re.findall(r"^\| `(\w+)` \|", sec, re.M))
        missing = [p for p in want if p not in rows]
        if missing:
            bad.append(f"{name}: the snapshots params table does not list {missing}")
    info = [f"code: CORS allows any origin: {facts['corsAnyOrigin']}; snapshots params checked: {want}"]
    return bad, info


def main():
    ap = argparse.ArgumentParser(description="Check the examples and facts of the Resolved Markets docs.")
    ap.add_argument("--docs", default=str(ROOT), help="docs repo root (default: this repo)")
    ap.add_argument("--facts", default=str(FACTS), help="facts file (default: facts.json next to this script)")
    ap.add_argument("--files", help="comma-separated files for the per-file checks (default: all doc files)")
    ap.add_argument("--write-facts", action="store_true", help="rebuild the facts file from the product repo and probes")
    ap.add_argument("--product", help="with --write-facts: path of a clone of the product repo")
    ap.add_argument("--ref", default="origin/main", help="with --write-facts: product git ref (default: origin/main)")
    ap.add_argument("--probe", help="with --write-facts: folder of live API replies (see ROUTE_PROBES)")
    ap.add_argument("--probe-date", help="with --write-facts: date of the live API replies")
    args = ap.parse_args()
    if args.write_facts:
        if not (args.product and args.probe and args.probe_date):
            ap.error("--write-facts needs --product, --probe and --probe-date")
        write_facts(args)
        return
    docs = load_docs(Path(args.docs))
    blocks = fenced(docs)
    scope = set(args.files.split(",")) if args.files else set(docs)
    facts = load_facts(args.facts)
    print(f"facts: product {facts['source']['product']}, probes {facts['source']['probes']}")
    checks = [
        ("one coin per connection: no multi-coin subscribe, the rule is stated, connection limits match code",
         lambda: check_one_coin(docs, facts)),
        ("WebSocket examples use the message of the code; the stated interval is the interval of the code",
         lambda: check_orderbook(docs, blocks, facts)),
        ("no real-time claim, except 1 capture-side line", lambda: check_realtime(docs)),
        ("public-stats examples have the keys and types of the route", lambda: check_public_stats(blocks, facts)),
        ("categories examples and the overview config ids match marketCategories.ts",
         lambda: check_categories(docs, blocks, facts)),
        ("category count, category lists and city count match the code", lambda: check_counts(docs, facts)),
        ("every JSON, JS/TS/TSX, Python and Go block parses; no require() with top-level await",
         lambda: check_syntax(blocks, scope)),
        ("GET /v1/markets/live is an array: the examples are arrays, and no code reads a markets key from it",
         lambda: check_live_array(blocks, scope)),
        ("REST JSON examples and data model tables use only keys that the route returns",
         lambda: check_route_json(docs, blocks, facts, scope)),
        ("code examples read only keys that their routes return",
         lambda: check_field_reads(blocks, facts, scope)),
        ("websocat example: one coin, auth then wait then subscribe, stays open, takes the first markets message",
         lambda: check_websocat(blocks, facts)),
        ("timeframes, Hyperliquid full books, HYPE price source, hit-price markets",
         lambda: check_followups(docs, facts, scope)),
        ("module rules, status checks, recipe dates, history rows and limit, snapshot times, Go types",
         lambda: check_review1(docs, blocks, facts, scope)),
        ("every reconnecting WebSocket client stops on close code 4003",
         lambda: check_ws_stop(blocks, facts)),
        ("the spread alert bot retries only 429, 5xx and network errors, and stops on the rest",
         lambda: check_alert_bot(docs, blocks)),
        ("the CORS text matches the code; the snapshots tables list interval, touchsize and count",
         lambda: check_cors_params(docs, facts)),
    ]
    passed = 0
    for i, (title, fn) in enumerate(checks, 1):
        bad, info = fn()
        print(f"{'PASS' if not bad else 'FAIL'}  {i}. {title}")
        for line in info + bad[:60]:
            print(f"      {line}")
        if len(bad) > 60:
            print(f"      ... {len(bad) - 60} more")
        passed += not bad
    print(f"{passed} of {len(checks)} checks pass")
    sys.exit(0 if passed == len(checks) else 1)


if __name__ == "__main__":
    main()
