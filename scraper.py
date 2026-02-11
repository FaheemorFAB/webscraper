import sys, asyncio, re, requests, logging
import pandas as pd
from urllib.parse import urljoin, urlparse
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from bs4 import BeautifulSoup
from typing import Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

# ── CONFIG ────────────────────────────────────────────────────────────────────
API_KEY        = "9a89b06d71262c1f7f0a3f710ba4fd2a4032df5acdf73332a97284bb26edce12"
TARGET         = 50
MAX_CONCURRENT = 8
HEADERS        = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0"}
CONTACT_PATHS  = ["/contact", "/contact-us", "/about", "/about-us", "/en/contact", "/ar/contact"]
SEARCH_QUERIES = ["hospital Qatar","clinic Qatar","medical center Qatar","pharmacy Qatar",
                  "polyclinic Qatar","specialist clinic Doha","dental clinic Qatar"]

# ── REGEX ─────────────────────────────────────────────────────────────────────
EMAIL_RE  = re.compile(r"(?<![\/\w])([a-zA-Z0-9._%+\-]{2,64}@[a-zA-Z0-9.\-]{2,255}\.[a-zA-Z]{2,12})(?![\/\w])", re.I)
MAILTO_RE = re.compile(r'mailto:([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,12})', re.I)
CF_RE     = re.compile(r'data-cfemail="([0-9a-f]+)"', re.I)
SCHEMA_RE = re.compile(r'"email"\s*:\s*"([^"]+)"', re.I)
OBF_RE    = re.compile(r'([a-zA-Z0-9._%+\-]{2,64})\s*[\[\(]?\s*(?:AT|at)\s*[\]\)]?\s*([a-zA-Z0-9.\-]{2,255})\s*[\[\(]?\s*(?:DOT|dot)\s*[\]\)]?\s*([a-zA-Z]{2,12})')

JUNK_DOMAINS   = {"sentry.io","example.com","wixpress.com","amazonaws.com","googletagmanager.com","schema.org","w3.org"}
JUNK_KEYWORDS  = ("font","fonts","icon","cdn","static","image","img","asset","pixel","tracker")
NOREPLY_PFX    = ("noreply","no-reply","donotreply","daemon","bounce","mailer")

# ── HELPERS ───────────────────────────────────────────────────────────────────
def decode_cf(enc: str) -> str:
    try:
        r = int(enc[:2], 16)
        return "".join(chr(int(enc[i:i+2], 16) ^ r) for i in range(2, len(enc), 2))
    except Exception:
        return ""

def same_domain(email: str, website: str) -> bool:
    try:
        return email.split("@")[1].lower().endswith(
            urlparse(website).netloc.lower().replace("www.", ""))
    except Exception:
        return False

def score(email: str, source: str, website: str) -> int:
    el = email.lower()
    if any(k in el for k in JUNK_KEYWORDS):                           return -100
    if el.split("@")[-1] in JUNK_DOMAINS:                             return -100
    if any(el.split("@")[0].startswith(p) for p in NOREPLY_PFX):     return -100
    if any(el.endswith(x) for x in (".png",".jpg",".gif",".svg",".js",".css")): return -100
    s  = 50 if same_domain(email, website) else -40
    s += {"mailto":30,"schema":28,"cf":26,"obfuscated":20,"dynamic":10,"regex":5}.get(source, 0)
    s += 20 if any(el.startswith(p) for p in ("info","contact","admin","hello","support","reception","enquir")) else 0
    s += 15 if el.endswith(".qa") else (5 if el.endswith((".com",".org",".net")) else 0)
    s -= 15 if re.search(r"\d{5,}", el.split("@")[0]) else 0
    return s

def parse_emails(html: str, source: str, website: str) -> list[tuple]:
    hits: list[tuple[str,str]] = []
    hits += [(m.group(1), "mailto")    for m in MAILTO_RE.finditer(html)]
    hits += [(decode_cf(m.group(1)), "cf") for m in CF_RE.finditer(html) if decode_cf(m.group(1))]
    hits += [(m.group(1), "schema")    for m in SCHEMA_RE.finditer(html)]
    hits += [(f"{m.group(1)}@{m.group(2)}.{m.group(3)}", "obfuscated") for m in OBF_RE.finditer(html)]
    hits += [(m.group(1), source)      for m in EMAIL_RE.finditer(html)]
    try:
        soup = BeautifulSoup(html, "html.parser")
        hits += [(a["href"][7:].split("?")[0].strip(), "mailto")
                 for a in soup.find_all("a", href=True) if a["href"].lower().startswith("mailto:")]
    except Exception:
        pass
    return [(e, s, score(e, s, website)) for e, s in hits if "@" in e]

def pick_best(candidates: list[tuple]) -> Optional[str]:
    valid = [c for c in candidates if c[2] > -50]
    if not valid: return None
    best = max(valid, key=lambda x: x[2])
    return best[0] if best[2] > 0 else None

# ── SCRAPERS ──────────────────────────────────────────────────────────────────
def static_scrape(website: str) -> list[tuple]:
    if not website or website == "N/A": return []
    base   = website if website.startswith("http") else f"http://{website}"
    origin = f"{urlparse(base).scheme}://{urlparse(base).netloc}"
    hits, session = [], requests.Session()
    session.headers.update(HEADERS)
    for path in [""] + CONTACT_PATHS:
        try:
            r = session.get(urljoin(origin, path), timeout=10, allow_redirects=True)
            if r.status_code == 200:
                hits += parse_emails(r.text, "regex", website)
                if pick_best(hits): break
        except Exception:
            continue
    return hits

async def dynamic_scrape(context, website: str) -> list[tuple]:
    if not website or website == "N/A": return []
    base, hits, net_hits = website if website.startswith("http") else f"http://{website}", [], []
    async def on_response(resp):
        try:
            if any(t in resp.headers.get("content-type","") for t in ("json","text")):
                net_hits.extend(parse_emails(await resp.text(), "dynamic", website))
        except Exception: pass
    for url in [base, urljoin(base, "/contact"), urljoin(base, "/contact-us")]:
        page = None
        try:
            page = await context.new_page()
            page.on("response", on_response)
            await page.goto(url, timeout=18000, wait_until="domcontentloaded")
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(0.6)
            hits += parse_emails(await page.content(), "dynamic", website)
            if pick_best(hits): break
        except Exception: pass
        finally:
            if page:
                try: await page.close()
                except Exception: pass
    return hits + net_hits

def serpapi_fallback(name: str) -> Optional[str]:
    try:
        data = requests.get("https://serpapi.com/search.json", timeout=12, params={
            "engine":"google","q":f'"{name}" email contact Qatar',"api_key":API_KEY,"num":5
        }).json()
        snippets = " ".join(r.get("snippet","") for r in data.get("organic_results",[]))
        return pick_best(parse_emails(snippets, "regex", ""))
    except Exception:
        return None

async def resolve(context, website: str, name: str) -> str:
    for candidates in [static_scrape(website), await dynamic_scrape(context, website)]:
        email = pick_best(candidates)
        if email: return email
    return serpapi_fallback(name) or ""

# ── COLLECTOR ─────────────────────────────────────────────────────────────────
async def collect() -> list[dict]:
    records, seen, q_idx, token = [], set(), 0, None
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        sem = asyncio.Semaphore(MAX_CONCURRENT)

        async def process(place, ctx):
            name = place.get("title","")
            if not name or name in seen: return None
            website = place.get("website","")
            async with sem:
                email = await resolve(ctx, website, name)
            return {"Company Name": name.strip(), "Website": website.strip(),
                    "Email": email.strip(), "Phone": place.get("phone","").strip(),
                    "Address": place.get("address","").strip()}

        while len(records) < TARGET and q_idx < len(SEARCH_QUERIES):
            params = {"engine":"google_maps","q":SEARCH_QUERIES[q_idx],
                      "ll":"@25.2854,51.5310,11z","hl":"en","type":"search","api_key":API_KEY}
            if token: params["next_page_token"] = token
            log.info(f"[{len(records)}/{TARGET}] Query: {SEARCH_QUERIES[q_idx]}")
            try:
                data    = requests.get("https://serpapi.com/search.json", params=params, timeout=30).json()
                results = data.get("local_results", [])
            except Exception:
                q_idx += 1; continue
            if not results:
                q_idx += 1; token = None; continue

            ctxs  = [await browser.new_context() for _ in range(min(MAX_CONCURRENT, len(results)))]
            batch = await asyncio.gather(
                *[process(pl, ctxs[i % len(ctxs)]) for i, pl in enumerate(results)],
                return_exceptions=True)

            for rec in batch:
                if not rec or isinstance(rec, Exception) or rec["Company Name"] in seen: continue
                seen.add(rec["Company Name"]); records.append(rec)
                log.info(f"  [{len(records)}/{TARGET}] {rec['Company Name']} | {rec['Email'] or '—'}")
                if len(records) >= TARGET: break

            for c in ctxs:
                try: await c.close()
                except Exception: pass
            token = data.get("serpapi_pagination",{}).get("next_page_token")
            if not token: q_idx += 1
            await asyncio.sleep(1.5)
        await browser.close()
    return records

# ── MAIN ──────────────────────────────────────────────────────────────────────
async def main():
    log.info(f"Scraping {TARGET} Qatar healthcare businesses")
    records = await collect()
    df = pd.DataFrame(records, columns=["Company Name","Website","Email","Phone","Address"])
    df.to_csv("qatar_healthcare_companies.csv", index=False, encoding="utf-8-sig")
    found = (df["Email"] != "").sum()
    log.info(f"Done — {len(df)} records, {found} emails ({found/max(len(df),1)*100:.0f}%)")

if __name__ == "__main__":
    asyncio.run(main())