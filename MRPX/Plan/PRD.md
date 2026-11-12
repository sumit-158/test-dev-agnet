# PRD-MRPX-002: Shortage Rebalancing: Short in One Plant, Stock Held in Another

| Field | Value |
|---|---|
| Project ID | MRPX-002 |
| Version | 0.1 (DRAFT, awaiting product owner validation) |
| Status | Draft |
| Product owner | Head of Supply Chain Planning |
| Stage requested | PoC |

## 1. Problem
A plant can be short of a material while another plant holds stock of the very same material. Planners find
this by chance, if at all, because shortage data and inventory data are reviewed in separate reports. The
result is expedited purchases and late deliveries while usable stock sits elsewhere.

## 2. Users and audience
Supply planners and team leads at the plants (about 25 people), and the Head of Supply Chain Planning for the
weekly review. General planning audience, not procurement.

## 3. Goal and success measure
For the latest daily MRP result, list every material that is short in a plant while another plant holds
stock of it, showing how much of the shortage that stock could cover. Success: for 2 plants chosen by the
product owner, the planners confirm that the listed transfer candidates are real and that none of their
known ones is missing, and the material description, criticality and product family shown match the
material master.

## 4. User stories
- **US-1** As a supply planner I want to see, for my plant, the short materials that are in stock in another
  plant, so that I can ask for a transfer before buying.
- **US-2** As a supply planner I want to see, for each such material, the shortage quantity, the stock
  quantity and the plant holding it, and the quantity that could be moved (the smaller of the two), so that I
  know how much of the gap a transfer could close.
- **US-3** As a supply planner I want to see how many weeks late each shortage is expected to be, so that I
  can tell the urgent from the large.
- **US-4** As a team lead I want to filter by country, so that I can review all plants of my country.
- **US-5** As a supply planner I want to see what each material is (its description, type, product family and
  criticality A, B or C), so that I can recognise it and tell the critical ones from the rest.
- **US-6** As a supply planner I want to filter the list by criticality and by product family, so that I can
  start with the critical A materials.
- **US-7** As a supply planner I want to see the date of the MRP result and the inventory month used, so that
  I know the figures are current.

## 4b. Deliverable (what the product is)
- **One governed data view** for the planners: one row per short material, short plant and plant
  holding stock, with the material description, type, product family and criticality, the shortage quantity, stock quantity, movable quantity, weeks late, the MRP result date
  and the inventory month.
- **One Databricks App** that hosts the whole user-facing product and reads only that view:
  - a dashboard page with filters for plant, country, criticality and product family, a table of transfer
    candidates sorted by movable quantity, and the MRP result date and inventory month shown on the page;
  - any further screens the user stories need (for example a material detail view), all inside the same app;
  - access through the users' Databricks workspace login, with the app querying the view through a SQL warehouse.
- Refreshed once per day after the MRP run.
- Not part of this product: a separate Lakeview dashboard, a machine learning model, alerts or e-mails.

## 5. Data
- SAP MRP data (the daily planning results of the SAP MRP run): the shortages.
- Inventory stock per material and plant: the stock held elsewhere.
- Material master data (description, type, product family and criticality of each material).
- Plant master data (plant names and countries).
Access: all three are available in the company data platform. No other data is needed.

## 6. Golden example (checked by the analyst against the data, to be confirmed by the product owner)
For the latest daily MRP result (2026-08-30) and the latest inventory month (August 2026): material
`1236-561-01` is short **336,233** units in plant 3300 (ASM Korea Ltd., KR), expected **9 weeks** late. The material is "EMI GASKET / SPIRAL / SSN-053W", criticality **A**, product
family **PE**.
Plant 1000 holds **356,500** units of it. The movable quantity is **336,233**: the
stock alone would cover the whole shortage. This is the largest movable quantity of all candidates.
Overall for these dates, counting only normal stock (no special stock): **18,348 materials**, **115,077**
pairs of a short plant and a plant holding stock, across 22 short plants and 34 plants holding stock.

## 7. Non-functional requirements
- Any plant view in the Databricks App appears in under 5 seconds.
- Data is refreshed once per day, after the MRP run.
- The view shows the MRP result date and the inventory month.

## 8. Out of scope
Creating transfer orders or purchase orders, forecasting, alerts or e-mails, currency conversion, deciding
whether a transfer is legally or commercially allowed, judging whether stock is excess or needed, and any
change to SAP.

## 9. Guardrails
No personal data. Read-only use of the source data.

## 10. Stage
PoC first. MVP and Prod are planned later.
