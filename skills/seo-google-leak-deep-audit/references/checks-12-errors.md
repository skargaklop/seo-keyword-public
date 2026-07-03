# 12 Structural Checks

Each check outputs:
- `id`, `title`, `stage`, `proxy_metric`, `evidence_urls[]`, `severity`, `fix_steps[]`, `confidence`.

1. **Topical dilution clusters**
   - Detect off-topic outliers relative to site centroid.
2. **Low effort / low originality**
   - Detect pages with weak structural depth and high templating.
3. **Intent vs click pattern mismatch**
   - Clickbait-title + weak answer-first; with GSC/GA4 detect CTR/engagement mismatch.
4. **UI penalty smearing**
   - Detect intrusive sticky/fixed overlays, especially on mobile.
5. **Broken author entity graph**
   - Missing `Person` schema / `sameAs` / author hubs.
6. **Toxic outgoing link neighborhood**
   - Dofollow outlinks to risky domains or UGC/link-farm patterns.
7. **Syntactic vs semantic date mismatch**
   - "Updated" signal without substantive yearly/structural content refresh.
8. **Anchor inconsistency / over-optimization**
   - Overused exact anchors and poor anchor-target semantic coherence.
9. **Lexical cannibalization / near-duplicates**
   - High shingle similarity across multiple landing pages.
10. **Mobile experience failure**
   - Layout friction / render blocking / smartphone optimization risk.
11. **No Passage Indexing architecture**
   - Long monolithic content lacking extractable Q/A and factual blocks.
12. **Conversion hubs isolated**
   - Money pages too deep and weakly linked from high-prominence nodes.

