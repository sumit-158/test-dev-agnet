# PRD-SCO-001: PIR / Source List Request Chat (intent, line-item extraction and evidence review)

| Field | Value |
|---|---|
| Project ID | SCO-001 |
| Version | 0.1 (standalone; a small AI slice of the SCO agent use case) |
| Status | Draft |
| Product owner | SCO Procurement Data team lead |
| Stage requested | PoC |

## 1. Problem
Requesters ask the SCO Procurement Data team to create or update Purchasing Info Records (PIR) and Source Lists
(SL). Each request is free text plus a supplier quotation (PDF or screenshot), often in a different layout and
language each time. A data steward reads both, decides what is being asked, and copies the values for every
part by hand. Most of the time goes into finding where each value came from and checking that it is right, not
into typing it.

## 2. Users
About 10 SCO procurement data stewards (they review and correct), and the requesters (buyers and material
managers at the plants) who send the requests.

## 3. Goal and success measure
A user sends a request in a chat (text, attachments or both). The AI says what kind of request it is, lists every
PIR or SL line item with its fields, and shows for each value exactly where it came from, so that a steward can
check and correct a request in a few clicks. Success, measured on the SCO demo requests (section 5):
- the golden example (section 6) gives exactly the expected request type, line items and values;
- the request type (section 4, US-2) is correct for at least 90 % of the demo requests;
- the number of line items is correct for at least 90 % of the demo requests;
- at least 90 % of the extracted field values are correct before any user correction;
- every non-empty value has a source the user can click, and for at least 90 % of them the highlighted area
  contains that value.

## 4. User stories
- **US-1** As a requester I want to type my request in a chat and attach one or more files (PDF, PNG, JPG), and
  send more messages to the same chat to add or change information, so that I don't need a special form.
- **US-2** As a steward I want the AI first to name the request type: create PIR, update PIR, create SL, update
  SL, create PIR and SL, or "not a PIR/SL request", so that I know which fields to expect. When it is not a
  PIR/SL request, the AI says so in the chat and extracts nothing.
- **US-3** As a steward I want the AI to read both the messages and the attachments together and return the list
  of line items: one line item per part number and per document type (PIR or SL). A part that needs both a PIR
  and an SL always gives two separate line items, so a request for 3 parts that needs both gives 6 line items.
  The request is free text: the AI extracts whatever meaningful PIR/SL information the text and attachments
  contain, for create and update alike, and does not expect a fixed form or a fixed set of fields per request.
- **US-4** As a steward I want each line item to show these fields, which are the fields the SCO team reviews
  today (internal name in brackets):

  **PIR line item**

  | Field | Meaning and format |
  |---|---|
  | Action | Create or Update |
  | Supplier (`supplier`) | 5-digit vendor code if given, otherwise the supplier name as written |
  | Vendor Material No. (`material`) | ASM part number, a code such as `1340-385-01` or `2000-04275`, never a description |
  | Material (`vendor_material_no`) | Item description as free text, never the part number |
  | Plant (`plant`) | SAP plant code, only when the request gives one; no default plant |
  | Purchasing Org. (`purchasing_org`) | 3000, 3300 or 8000; the column "Prog." in ASM tables; not the purchasing group (e.g. `S33`) |
  | C/R. of Origin (`country_of_origin`) | ISO-2 country code; never taken from an e-mail signature or company name |
  | Pl. Deliv. Time (`lead_time_days`) | Days, 1 to 365 ("8 weeks" becomes 56); shown in weeks |
  | Standard Qty (`standard_qty`) | Whole number, at least 1 |
  | Amount (`amount`) | Price per unit, no currency symbol or thousand separator |
  | Cond. Currency (`currency`) | ISO currency code (KRW, JPY, EUR, USD, ...) |
  | Pricing Unit (`pricing_unit`) | 1, 10, 100 or 1000 |
  | Unit of Measure (`unit_of_measure`) | EA, PC, M, KG, L, BOX, SET or ROLL |
  | Valid-From Date (`valid_from`) | YYYY-MM-DD |
  | Valid To Date (`valid_to`) | YYYY-MM-DD; `9999-12-31` means unlimited |

  **SL line item**

  | Field | Meaning and format |
  |---|---|
  | Action | Create or Update |
  | Vendor Material No. (`material`) | as for PIR |
  | Material (`vendor_material_no`) | as for PIR |
  | Plant (`plant`) | as for PIR |
  | Supplier (`supplier`) | as for PIR |
  | Purch. Organization (`purchasing_org`) | as for PIR |
  | Valid From / Valid To (`valid_from`, `valid_to`) | as for PIR |
  | Fixed Vendor (`fixed_vendor`) | `X` only when the request says fixed, sole or fixed source vendor; otherwise empty |

  Any value that is not found in the text or the attachments stays empty and is shown as missing. This applies to
  every field, including Plant, Valid To Date and Pricing Unit. The AI does not fill it with a guess or a default.
- **US-5** As a steward I want the screen split in two: the chat (messages and attachment previews) on the left,
  and the request type and line items on the right, so that I can see the source and the result side by side.
- **US-6** As a steward I want every extracted value to carry its source: which message or which attachment and
  page, the exact text it was read from, and a bounding box around that text, so that I can see why the AI chose
  that value.
- **US-7** As a steward I want to click a field on the right and have the left side scroll to the source message
  or open the attachment at the right page, with a yellow box around the source text, so that I can check the
  value at a glance. When a value has several sources (for example the e-mail table and the quotation), all of
  them are boxed. Values the AI calculated (for example weeks converted to days, or a total divided by the
  quantity) say so and box the numbers they came from.
- **US-8** As a steward I want the AI to mark a field when the sources disagree (for example the request table
  says one country of origin and the quotation another), showing both values and their sources, so that I decide
  which is right.
- **US-9** As a steward I want to decide whether the extraction is good or needs an update, and correct it in
  either of two ways, with the same result:
  - **direct edit** on the right-hand side: change any value, add or remove a line item, change the request type;
  - **in the chat**: for example "line 2 amount is 8000", "add plant 3300 to all lines" or "this is also an SL
    request". The AI applies only the change asked for, shows which values it changed, and asks back when the
    instruction is unclear.

  Values changed by the user (by edit or chat) are marked as corrected and are never overwritten by a later
  extraction. A correction typed in the chat becomes the source of that value, so clicking it boxes that chat
  message.
- **US-10** As a steward I want to copy or download the reviewed line items (JSON or CSV with the field names
  above), so that I can use them in the next step. Nothing is sent to SAP.

## 5. Data
- Chat messages typed by the user (any language; English, Korean, Japanese, German and Dutch are common).
- Attachments: PDF (text or scanned) and images (PNG, JPG) only. Excel, Word and `.eml` files are not supported
  in the PoC.
- Test material: the SCO demo requests and quotations in `SCO_INBOX_AGENT/apps/demo_data/emails` (message text
  pasted into the chat, attachments uploaded).
- No SAP master data is read. The PoC does not check whether a vendor, material or plant exists in SAP.

## 6. Golden example (checked against the demo data)
Request "Urgent-SCO_Request to update PIR data_Fusion_Best" (2025-11-26): the message text says "Could you
update PIR data as below part, I attached supplier quotation", includes a table with 2 rows, and has 1 PDF
attached (`BE25112601_RAIL-DIN 35MM X 7.5MM.pdf`). The expected result:
- request type **update PIR**; **2 line items**; no plant in the request, so Plant is empty and flagged.
- line 1: Supplier `18570`, Vendor Material No. `1038-967-34`, Material `RAIL-DIN 35MM X 7.5MM X 450MM LG`,
  Purchasing Org. `3300`, C/R. of Origin `KR`, Pl. Deliv. Time `7` days, Standard Qty `1`, Amount `7000`,
  Cond. Currency `KRW`, Pricing Unit `1`, Unit of Measure `EA`, Valid-From Date `2025-11-26`, Valid To Date empty.
- line 2: same values, except Vendor Material No. `1038-967-04` and Material `RAIL-DIN 35MM X 7.5MM X 75MM LG`.
- `S33` in the table is the purchasing group and must not appear as Purchasing Org.
- Clicking Amount on line 1 scrolls to the message and boxes `7,000` in its table row. If the quotation also shows
  the price, the price in the PDF is boxed as a second source.
- Known trap: the current SCO inbox pipeline reads C/R. of Origin as `DE` from the quotation, while the requester's
  table says `KR`. The PoC must show the value from the request table, show the disagreement (US-8) if the PDF
  says otherwise, and box both sources.

## 7. Non-functional requirements
- Runs as a Databricks App (chat and review screen in one app); models are called from Databricks.
- Request type shown within 5 seconds of sending; line items for a request with up to 10 parts and 3 PDF pages
  within 60 seconds.
- A request with up to 50 parts and 20 attachment pages works.
- Bounding boxes line up with the attachment preview at any zoom level.
- Model cost for the PoC below USD 200 per month (about 10 stewards, about 40 requests per day).

## 8. Out of scope
Reading the SCO mailbox, creating or changing anything in SAP, checking values against SAP master data, ticket
queues, assignment, approval flows, audit trails, user management, notifications, and replying to the requester.
The PoC keeps a chat only for the browser session; storing chats is not needed.

## 9. Guardrails
Every extracted value comes from the request text or an attachment, with a source. The model never invents a
value, a default or a part number. When unsure, the AI leaves the field empty and says why. Prices and supplier
quotations are confidential: they stay inside the ASM environment and are not used to train models. No personal
data (such as names, phone numbers or signatures) is extracted into line items.

## 10. Stage
PoC first, as a Databricks App. An MVP could add Excel and `.eml` attachments, checks against SAP master data,
and connection to the SCO inbox.

## 11. Decisions (former open questions)
- **D-1** Anything not found in the text or attachments stays empty, including Plant. No defaults.
- **D-2** A part that needs both a PIR and an SL gives two separate line items.
- **D-3** Only PDF and image attachments in the PoC; no Excel, Word or `.eml`.
- **D-4** Requests are free text. The AI extracts whatever meaningful PIR/SL information it finds, for create and
  update alike; the user decides whether it is right and corrects it in the chat or by direct edit (US-9).
- **D-5** The app is a Databricks App.
- Not in scope for now: a formal test set with expected answers from the product owner, and a time-per-request
  baseline.
