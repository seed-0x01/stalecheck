#!/usr/bin/env python3
"""Falsifiable fixtures for stalecheck. Each assertion can fail on real output."""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build

PASS = 0
FAIL = 0


def check(label, condition):
    global PASS, FAIL
    if condition:
        PASS += 1
        print("PASS", label)
    else:
        FAIL += 1
        print("FAIL", label)


with tempfile.TemporaryDirectory() as d:
    oracle = {"ok": True, "usdc_total": 13.5, "runway_days_est": 20.0,
              "iso_utc": "2026-11-18T20:00:00Z", "path": "fixture"}

    # A live link and a dead link on the same page.
    open(os.path.join(d, "index.html"), "w").write(
        '<a href="/live.html">ok</a> <a href="/gone.html">dead</a>'
        ' <a href="/llms.txt">dynamic</a>'
    )
    open(os.path.join(d, "live.html"), "w").write("<p>here</p>")

    # An undated current-looking figure, a dated one, and a token tally.
    open(os.path.join(d, "figures.html"), "w").write(
        "<p>liquid 27.44 USDC right now</p>"
        "<p>filler filler filler filler filler filler filler filler filler filler filler filler filler filler filler filler filler filler filler filler </p>"
        "<p>deleted: the old 27.44 USDC claim was wrong</p>"
        "<p>filler filler filler filler filler filler filler filler filler filler filler filler filler filler filler filler filler filler filler filler </p>"
        "<p>45,324,074 tokens burned</p>"
    )

    # Embedded snapshots: one drifted, one matching.
    snap = json.dumps({"vitals": {"usdc_total": 14.442436, "iso_utc": "2026-11-17T20:29:28Z"}})
    good = json.dumps({"vitals": {"usdc_total": 13.5, "iso_utc": "2026-11-18T20:00:00Z"}})
    open(os.path.join(d, "snapshots.html"), "w").write(
        '<p>as of 2026-11-17T20:29:28Z — the oracle floor, not current</p>'
        '<script type="application/json" id="a">%s</script>'
        '<script type="application/json" id="b">%s</script>' % (snap, good)
    )

    r = build.scan(d, oracle)

    check("dead internal link detected",
          len(r["dead_links"]) == 1 and r["dead_links"][0]["href"] == "/gone.html")
    check("live internal link not flagged",
          all(x["href"] != "/live.html" for x in r["dead_links"]))
    check("dynamic route not flagged as dead",
          all(x["href"] != "/llms.txt" for x in r["dead_links"]))
    check("undated USDC figure surfaced",
          any(x["value"] == "27.44" and x["page"] == "figures.html" for x in r["unlabelled"]))
    check("dated historical figure suppressed",
          sum(1 for x in r["unlabelled"] if x["value"] == "27.44") == 1)
    check("token tally surfaced",
          any(x["kind"] == "tokens" and x["value"] == "45,324,074" for x in r["unlabelled"]))
    check("visibly dated snapshot classified as dated record",
          any(x["status"] == "dated record" and x["delta"] == 0.942436 for x in r["drift"]))
    check("matching snapshot passes",
          any(x["status"] == "matches" for x in r["drift"]))
    check("verdict FAIL when defects present", r["verdict"] == "FAIL")
    check("all 4 pages scanned", r["pages_scanned"] == 4)

    # A clean directory must pass.
    with tempfile.TemporaryDirectory() as clean:
        open(os.path.join(clean, "index.html"), "w").write(
            '<a href="/ok.html">fine</a><p>was once 27.44 USDC, deleted</p>'
        )
        open(os.path.join(clean, "ok.html"), "w").write("ok")
        c = build.scan(clean, oracle)
        check("clean directory verdict PASS", c["verdict"] == "PASS")
        check("clean directory has no unlabelled figures", len(c["unlabelled"]) == 0)

    # Missing oracle must say so, never invent a number.
    miss = build.load_oracle("/no/such/vitals.json")
    check("missing oracle reports ok=False", miss["ok"] is False)

print("\n%d/%d fixtures PASS" % (PASS, PASS + FAIL))
sys.exit(0 if FAIL == 0 else 1)
