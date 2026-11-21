# Store

Factory store app for ERPNext. Desk module name is **Store**. Python package remains `k95_store` so existing sites can migrate without reinstalling.

Stock truth is ERPNext: Item, Warehouse, Batch, Purchase Receipt, Stock Entry, Bin / SLE.

## Documents

Setup: Store Settings, Batch Format Rule  
Inward: Gate Entry, Putaway, GRN Charge, Damage Report  
Outward: Reservation, Issue, Production Issue Request, Labelling Material Request  
Control: Stock Return, Vendor Return, Transfer, Opening Stock, Cycle Count, Adjustment, Reconciliation Log

GRN is native **Purchase Receipt**. Lot is native **Batch**. Location is native **Warehouse**.

## Deploy (this bench → dev site → main site)

1. Commit this app on the develop machine.
2. On the **dev** site:

```bash
bench get-app /path/to/k95_store
# or: git pull inside apps/k95_store
bench --site DEV_SITE migrate
bench --site DEV_SITE clear-cache
bench restart
```

3. After dev is verified, same migrate on the **main** site. Do not skip `migrate`. Custom fields and the Store module rename run in `after_migrate` / patches.

4. Set **Store Settings** on each site (company, Receiving, Rejected, Quarantine, landed-cost account).

Package name for `install-app` / `apps.txt` is still `k95_store`. The module users see is Store.
