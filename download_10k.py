# Download the 10-K reports (2014 to 2026) of the 100 biggest US listed companies from SEC EDGAR
# and keep only the text of "Item 1A. Risk Factors" of each report.
#
# python download_10k.py      (it skips the reports that are already in data/item1a/)
#
# SEC asks for a User-Agent with a name and an email, and maximum 10 requests per second.

import re
import time
from pathlib import Path

import pandas as pd
import requests
import warnings
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

RAIZ = Path(__file__).resolve().parent
salida = RAIZ / "data" / "item1a"
salida.mkdir(parents=True, exist_ok=True)
headers = {"User-Agent": "Alejandro Lezcano Osorio alezcano02@gmail.com", "Accept-Encoding": "gzip, deflate"}

# some reports split the words of the headings with styled letters ("RIS K FACTORS"), so we allow a space between letters
def palabra(w):
    return r"\s?".join(w)


sep = r"\s*[\.\:\-\u2013\u2014]?\s*"
inicio = re.compile(r"item\s*1\s?a" + sep + palabra("risk") + r"\s+" + palabra("factors"), re.I)
fin = re.compile(r"item\s*1\s?b" + sep + palabra("unresolved") + r"\s+" + palabra("staff")
                 + r"|item\s*1\s?c" + sep + palabra("cybersecurity")
                 + r"|item\s*2" + sep + r"(description\s+of\s+)?" + palabra("properties"), re.I)


def item_1a(html):
    texto = BeautifulSoup(html, "lxml").get_text(" ")
    texto = re.sub(r"\s+", " ", texto.replace("\xa0", " "))
    # the heading appears in the table of contents too: we keep the longest section between a start and the next end
    mejor = ""
    for a in inicio.finditer(texto):
        b = fin.search(texto, a.end())
        if b and b.start() - a.end() > len(mejor):
            mejor = texto[a.end():b.start()]
    return mejor.strip()


tickers = requests.get("https://www.sec.gov/files/company_tickers.json", headers=headers, timeout=60).json()
empresas = pd.DataFrame(tickers.values()).drop_duplicates("cik_str").head(130)

filas = []
for _, e in empresas.iterrows():
    cik = int(e["cik_str"])
    sub = requests.get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json", headers=headers, timeout=60).json()
    time.sleep(0.12)
    rec = pd.DataFrame(sub["filings"]["recent"])
    # "recent" has only the last 1.000 filings: companies with many filings have the older 10-K in extra pages
    for extra in sub["filings"].get("files", []):
        if extra.get("filingTo", "") >= "2014-01-01":
            rec = pd.concat([rec, pd.DataFrame(requests.get("https://data.sec.gov/submissions/" + extra["name"], headers=headers, timeout=60).json())])
            time.sleep(0.12)
    rec = rec[(rec["form"] == "10-K") & (rec["filingDate"] >= "2014-01-01")]
    if len(rec) < 5:          # foreign companies file 20-F or 40-F, we only keep US filers
        continue
    for _, f in rec.iterrows():
        archivo = salida / f"{e['ticker']}_{f['filingDate']}.txt"
        if not archivo.exists() or archivo.stat().st_size < 2000:     # we retry the reports where the section was not found
            url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{f['accessionNumber'].replace('-', '')}/{f['primaryDocument']}"
            r = requests.get(url, headers=headers, timeout=120)
            time.sleep(0.12)
            if r.status_code != 200:
                print("error", e["ticker"], f["filingDate"], r.status_code)
                continue
            archivo.write_text(item_1a(r.text), encoding="utf-8")
        filas.append({"ticker": e["ticker"], "cik": cik, "name": e["title"], "sic": sub.get("sic"),
                      "sic_description": sub.get("sicDescription"), "filing_date": f["filingDate"],
                      "report_date": f["reportDate"], "accession": f["accessionNumber"], "file": archivo.name,
                      "words": len(archivo.read_text(encoding="utf-8").split())})
    print(e["ticker"], len(filas), flush=True)
    if sum(1 for x in filas if x["ticker"] != e["ticker"]) and len({x["ticker"] for x in filas}) >= 100:
        break

pd.DataFrame(filas).to_csv(RAIZ / "data" / "filings.csv", index=False)
print("reports:", len(filas), "| companies:", len({x["ticker"] for x in filas}))
