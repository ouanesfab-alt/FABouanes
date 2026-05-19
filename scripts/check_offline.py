import sys

checks = [
    ("templates/operation_new.html", [
        "sale-form", "payment-form", "offline-db.js", "queueOperation"
    ]),
    ("templates/base.html", [
        "offline-pending-badge", "icon-online", "initOfflineSync", "offline-sync.js"
    ]),
    ("static/js/offline-db.js", [
        "queueOperation", "getRefData", "cacheRefData", "countPending"
    ]),
    ("static/js/offline-sync.js", [
        "syncPendingOperations", "initOfflineSync", "cacheReferenceData"
    ]),
    ("static/sw.js", [
        "offline-db.js", "offline-sync.js", "ONLINE_ONLY_PREFIXES"
    ]),
    ("app/api/v1/offline.py", [
        "create_sale_from_form", "create_payment_from_form", "offline"
    ]),
    ("app/api/router.py", [
        "offline_router"
    ]),
]

ok = True
for path, markers in checks:
    txt = open(path, encoding="utf-8").read()
    for m in markers:
        if m in txt:
            print(f"OK   [{path}] contains '{m}'")
        else:
            print(f"FAIL [{path}] MISSING '{m}'")
            ok = False

sys.exit(0 if ok else 1)
