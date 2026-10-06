# Evidence model

The core entities are `Source`, `Fact`, `Offer` and `Check`.

```text
Source
  id, URL, publisher, type, retrieval time, content hash, origin, status
Fact
  exact subject, field, normalized value, source ID, evidence span, validation status
Offer
  title, exact manufacturer part number if resolved, seller, price/currency, origin, result
Check
  rule, required value, observed value, status, explanation, fact/source IDs
```

Source precedence is visible in the UI: manufacturer, retailer, marketplace and search result. A retailer or marketplace claim can inform discovery but cannot drive a positive specification check in the current engine. A manufacturer-listed state requires an explicit exact-part to exact-device relationship.

Prices are observations with currency and timestamp. A Google product ID is not treated as a manufacturer SKU. Multiple URLs are not assumed to be independent evidence. A source conflict suppresses a positive conclusion for that field.
