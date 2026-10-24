# V3.4 changes (22 October 2026)

- Four main tabs: Recipe Book, Calculation (includes alcohol & meal breakdown), Purchase Order, Admin Settings.
- Removed the duplicate live calculation guide table; the authoritative guide stays editable under Admin Settings.
- Three-digit cocktail serving boxes, compact guest/table planning and side-by-side calculation areas.
- No alcoholic cocktail ingredients in a PO without the Alcohol Package. Non-alcoholic mixers/garnishes remain.
- Source-wise PO preview sorted Water → Juices → Soft Beverages → Mixers → Puree & Syrups → Wines → Beer → Spirits → Liqueurs → Others.
- Word purchase-order meal quantities are in separate right-aligned Breakfast / Lunch / Dinner / bold Total columns.
- Separate alcohol inventory Word download removed; optional inventory page appended to relevant source Word PO.
- Inline Recipe editing by category. Suggested Wikimedia Commons images with attribution, plus persistent override by HTTPS URL or optional private Google Drive upload.
- Admin action hashes legacy plaintext passwords without disrupting existing login; separate password reset is retained.
- Existing master, unit, price and PO formulas remain Google Sheet driven (no fixed guest-size or case-size changes).

## Test status

- 41 pure calculation, unit, authentication, image and DOCX tests pass locally.
- Word PO rendered and inspected at one page using sample 18-item data.
- Streamlit UI, Google Sheets writes and Google Drive upload were not exercised in a live authenticated session in this environment.
