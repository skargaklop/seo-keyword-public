# Anti-AI Pattern Detection System

A 3-tier system for detecting and eliminating AI writing patterns from content. Use this reference when auditing text for AI tells, rewriting AI-generated content, or establishing quality standards for human-sounding prose.

## How This System Works

Patterns are organized by reliability as an AI signal:

- **Tier 1 — Always Remove**: These patterns appear 5-20x more often in AI text than human text. Replace on sight.
- **Tier 2 — Flag in Clusters**: Individually fine, but 2+ in the same paragraph is a strong AI signal. Flag when they appear together.
- **Tier 3 — Flag at High Density**: Common words that AI overuses. Only flag when they make up roughly 3%+ of total words.

## Tier 1 — Always Remove

These are the highest-confidence AI signals. Always replace them.

### Structural Patterns

**Correlative Construction** (The #1 AI Tell)
- ❌ "X aren't just Y, they're Z"
- ❌ "It's not about X, it's about Y"
- ✅ State the point directly

**Forbidden Rhetorical Flourishes**
- ❌ "The best part? ..."
- ❌ "The secret? ..."
- ❌ "Here's the thing..."
- ❌ "Let's be honest..."
- ❌ "At the end of the day..."
- ✅ Cut entirely

**Forbidden Staccato Phrasing**
- ❌ "No fluff. No filler. Just results."
- ❌ "Big ideas. Small words. Maximum impact."
- ✅ Vary sentence structure instead

**Forbidden Openers**
- ❌ "In the ever-evolving world of..."
- ❌ "In today's fast-paced..."
- ❌ "Gone are the days when..."
- ✅ Start with the actual point

**Forbidden Constructions**
- ❌ "The truth is..." / "The reality is..."
- ❌ "Let that sink in"
- ❌ "Now more than ever..."
- ❌ "Sounds impossible? It's not."
- ❌ "What if I told you..."

### Vocabulary Words — Tier 1

| Replace | With | Notes |
|---|---|---|
| delve / delve into | explore, dig into, look at | #1 AI vocabulary tell |
| landscape (metaphor) | field, space, industry, world | Never correct in prose |
| tapestry | describe actual complexity | Never correct |
| realm | area, field, domain | Never correct |
| paradigm | model, approach, framework | Never correct |
| embark | start, begin | Never correct |
| beacon | rewrite entirely | Never correct |
| testament to | shows, proves, demonstrates | Never correct |
| robust | strong, reliable, solid | Never correct |
| comprehensive | thorough, complete, full | Never correct |
| cutting-edge | latest, newest, advanced | Never correct |
| leverage (verb) | use | Never correct |
| pivotal | important, key, critical | Never correct |
| underscores | highlights, shows | Never correct |
| meticulous / meticulously | careful, detailed, precise | Never correct |
| seamless / seamlessly | smooth, easy, without friction | Never correct |
| game-changer / game-changing | describe what changed and why | Never correct |
| hit differently / hits different | say what changed, or cut | Never correct |
| utilize | use | Never correct |
| watershed moment | turning point, shift | Never correct |
| marking a pivotal moment | state what happened | Never correct |
| the future looks bright | say something specific or nothing | Never correct |
| only time will tell | say something specific or nothing | Never correct |
| nestled | is located, sits, is in | Never correct |
| vibrant | describe what makes it active | Never correct |
| thriving | growing, active (or cite number) | Never correct |
| despite challenges… continues to thrive | name challenge and response | Never correct |
| showcasing | showing, demonstrating (or cut) | Never correct |
| deep dive / dive into | look at, examine, explore | Never correct |
| unpack / unpacking | explain, break down, walk through | Never correct |
| bustling | busy, active (or cite what makes it busy) | Never correct |
| intricate / intricacies | complex, detailed (or name complexity) | Never correct |
| complexities | name actual complexities | Never correct |
| ever-evolving | changing, growing (or describe how) | Never correct |
| enduring | lasting, long-running (or cite how long) | Never correct |
| daunting | hard, difficult, challenging | Never correct |
| holistic / holistically | complete, full, whole (or describe what) | Never correct |
| actionable | practical, useful, concrete | Never correct |
| impactful | effective, significant (or describe impact) | Never correct |
| learnings | lessons, findings, takeaways | Never correct |
| thought leader / thought leadership | expert, authority | Never correct |
| best practices | what works, proven methods | Never correct |
| at its core | cut — just state the thing | Never correct |
| synergy / synergies | describe actual combined effect | Never correct |
| interplay | relationship, connection, interaction | Never correct |
| in order to | to | Never correct |
| due to the fact that | because | Never correct |
| serves as | is | Never correct |
| features (verb) | has, includes | Never correct |
| boasts | has | Never correct |
| presents (inflated) | is, shows, gives | Never correct |
| commence | start, begin | Never correct |
| ascertain | find out, determine, learn | Never correct |
| endeavor | effort, attempt, try | Never correct |
| keen (as intensifier) | interested, eager, enthusiastic | Never correct |
| symphony (metaphor) | describe actual coordination | Never correct |
| embrace (metaphor) | adopt, accept, use, switch to | Never correct |
| navigate / navigating (transitional) | work through, handle, deal with | Never correct |
| foster | encourage, support, build | Never correct |
| elevate | improve, raise, strengthen | Never correct |
| unleash | release, enable, unlock | Never correct |
| streamline | simplify, speed up | Never correct |
| empower | enable, let, allow | Never correct |
| bolster | support, strengthen, back up | Never correct |
| spearhead | lead, drive, run | Never correct |
| resonate / resonates with | connect with, appeal to, matter to | Never correct |
| revolutionize | change, transform, reshape | Never correct |
| facilitate / facilitates | enable, help, allow, run | Never correct |
| underpin | support, form the basis of | Never correct |
| nuanced | specific, subtle, detailed (or name nuance) | Never correct |
| crucial | important, key, necessary | Never correct |
| multifaceted | describe actual facets, or cut | Never correct |
| ecosystem (metaphor) | system, community, network, market | Never correct |
| myriad | many, numerous (or give a number) | Never correct |
| plethora | many, a lot of (or give a number) | Never correct |
| encompass | include, cover, span | Never correct |
| catalyze | start, trigger, accelerate | Never correct |
| reimagine | rethink, redesign, rebuild | Never correct |
| galvanize | motivate, rally, push | Never correct |
| augment | add to, expand, supplement | Never correct |
| cultivate | build, develop, grow | Never correct |
| illuminate | clarify, explain, show | Never correct |
| elucidate | explain, clarify, spell out | Never correct |
| juxtapose | compare, contrast, set side by side | Never correct |
| paradigm-shifting | describe what actually shifted | Never correct |
| transformative / transformation | describe what changed and how | Never correct |
| cornerstone | foundation, basis, key part | Never correct |
| paramount | most important, top priority | Never correct |
| poised (to) | ready, set, about to | Never correct |
| burgeoning | growing, emerging (or cite number) | Never correct |
| nascent | new, early-stage, emerging | Never correct |
| quintessential | typical, classic, defining | Never correct |
| overarching | main, central, broad | Never correct |
| underpinning / underpinnings | basis, foundation, what supports | Never correct |

### Formatting — Tier 1

**Em Dashes**
- Rule: Target zero. Hard max: one per 1,000 words
- Applies to: Headings, section titles, and body prose
- Catch both: Unicode em dash (—) and double-hyphen substitute (--)
- Fix: Replace with commas, periods, parentheses, or two sentences

**Bold Overuse**
- Rule: One bolded phrase per major section at most, or none
- Fix: If something's important enough to bold, restructure the sentence to lead with it

**Emoji in Headers**
- Rule: Remove entirely. No `## 🚀 What This Means`
- Exception: Social posts may use one or two emoji sparingly — at the end of a line, never mid-sentence

**Curly Quotation Marks and Apostrophes**
- Rule: Weak paste-from-chat signal — meaningful in plain-text contexts (code comments, commit messages, plaintext drafts)
- Treat as: Corroborating, never conclusive
- Fix: Replace with straight quotes in plain-text/code; leave in finished publications and locale-correct punctuation

### Common Openers/Closers — Tier 1

**Meta-Commentary**
- ❌ "I hope this helps!"
- ❌ "Certainly!"
- ❌ "Absolutely!"
- ❌ "Great question!"
- ❌ "Feel free to reach out"
- ✅ Remove entirely

**Generic Conclusions**
- ❌ "In conclusion..."
- ❌ "In summary..."
- ❌ "To summarize..."
- ❌ "The future looks bright"
- ❌ "Only time will tell"
- ✅ Let the conclusion speak for itself

## Tier 2 — Flag in Clusters

These words are legitimate on their own. When **2 or more appear in the same paragraph**, the paragraph likely needs a rewrite.

| Replace | With | Notes |
|---|---|---|
| harness | use, take advantage of | |
| navigate / navigating | work through, handle, deal with | |
| foster | encourage, support, build | |
| elevate | improve, raise, strengthen | |
| unleash | release, enable, unlock | |
| streamline | simplify, speed up | |
| empower | enable, let, allow | |
| bolster | support, strengthen, back up | |
| spearhead | lead, drive, run | |
| resonate / resonates with | connect with, appeal to, matter to | |
| revolutionize | change, transform, reshape (or describe what changed) | |
| facilitate / facilitates | enable, help, allow, run | |
| underpin | support, form the basis of | |
| nuanced | specific, subtle, detailed (or name the actual nuance) | |
| crucial | important, key, necessary | |
| multifaceted | describe the actual facets, or cut | |
| ecosystem (metaphor) | system, community, network, market | |
| myriad | many, numerous (or give a number) | |
| plethora | many, a lot of (or give a number) | |
| encompass | include, cover, span | |
| catalyze | start, trigger, accelerate | |
| reimagine | rethink, redesign, rebuild | |
| galvanize | motivate, rally, push | |
| augment | add to, expand, supplement | |
| cultivate | build, develop, grow | |
| illuminate | clarify, explain, show | |
| elucidate | explain, clarify, spell out | |
| juxtapose | compare, contrast, set side by side | |
| paradigm-shifting | describe what actually shifted | |
| transformative / transformation | describe what changed and how | |
| cornerstone | foundation, basis, key part | |
| paramount | most important, top priority | |
| poised (to) | ready, set, about to | |
| burgeoning | growing, emerging (or cite a number) | |
| nascent | new, early-stage, emerging | |
| quintessential | typical, classic, defining | |
| overarching | main, central, broad | |
| underpinning / underpinnings | basis, foundation, what supports | |

### Tier 2 Phrases (Multi-Word Boilerplate)

Flag when **2+ uses of the same phrase** appear in one piece, plus a cluster rule: three or more distinct phrases from this table in one piece is a strong signal.

| Phrase | What to do |
|---|---|
| emerging sector / emerging space / emerging category | Name the actual sector |
| the integration of (X with Y) | Describe what's being integrated |
| the intersection of (X and Y) | Pick the specific overlap or cut |
| community-driven | Name what the community does |
| long-term sustainability | Cite time horizon and constraint |
| user engagement | Name the actual action |
| decentralized compute | Specify architecture or cut |
| (sustainable) reward emissions | Cite emission schedule and sink |
| tokenized incentive structures | Describe actual mechanism |
| designed for long-term [X] | Cut "designed for" |
| the integration of | Describe what's being integrated |
| the intersection of | Pick the overlap that matters |

## Tier 3 — Flag at High Density

These are normal words. Only flag them when they make up roughly **3%+ of total words** in the text — a sign that AI filled space with vague praise instead of specifics.

| Word | What to do |
|---|---|
| significant / significantly | Replace some with specifics: numbers, comparisons, examples |
| innovative / innovation | Describe what's actually new |
| effective / effectively | Say how or cite a metric |
| dynamic / dynamics | Name the actual forces or changes |
| scalable / scalability | Describe what scales and to what |
| compelling | Say why it compels |
| unprecedented | Name the precedent it breaks (or cut) |
| exceptional / exceptionally | Cite what makes it an exception |
| remarkable / remarkably | Say what's worth remarking on |
| sophisticated | Describe the sophistication |
| instrumental | Say what role it played |
| world-class / state-of-the-art / best-in-class | Cite a benchmark or comparison |

### Additional Tier 3 Patterns

**Overuse of "Just"**
- Problem: AI uses "just" constantly as a softener
- ❌ "We just need to understand that it's just about learning"
- ✅ "It's about learning. Focus on what matters."
- Limit: Once per paragraph maximum

**Overuse of "Actually"**
- Problem: AI uses "actually" to sound like it's adding nuance
- ❌ "It's actually about teaching, but actually about community"
- ✅ "It's about teaching. It's also about community."
- Limit: Once per 500 words maximum

## Additional Structural AI Patterns

### Formatting Issues

**Excessive Bullet Lists**
- Convert bullet-heavy sections into prose paragraphs
- Bullets only for genuinely list-like content

**Title Case Headings**
- ❌ "Strategic Negotiations And Key Partnerships"
- ✅ "Strategic negotiations and key partnerships"
- Use sentence case for subheadings

**Inline-Header Lists**
- ❌ "**Performance:** Performance improved by..."
- ✅ Strip the bold header and write the point directly

**Numbered List Inflation**
- AI defaults to numbered lists because they're structurally safe
- Only use when content genuinely has that many discrete, parallel items

### Sentence-Level Issues

**"It's Not X, It's Y" Construction**
- Rule: Max one per piece, and only if it serves the argument
- This is the most common AI tell

**Hollow Intensifiers**
- Cut: genuine, real, truly, quite frankly, to be honest, let's be clear, it's worth noting that

**Hedging Language**
- Cut: perhaps, could potentially, it's important to note that, to be clear
- Replace with direct statements

**Missing Bridge Sentences**
- Each paragraph should connect to the last
- If paragraphs could be rearranged without notice, add connective tissue

**Compulsive Rule of Three**
- Vary groupings: use two items, four items, or a full sentence
- Max one "adjective, adjective, and adjective" pattern per piece

**Copula Avoidance**
- AI avoids "is" and "has" by substituting: serves as, features, boasts, presents
- Default to "is" or "has" unless a more specific verb adds meaning

**Synonym Cycling**
- AI rotates synonyms to avoid repeating: "developers… engineers… practitioners… builders"
- If the same word appears three times and that's the right word, keep all three

### Rhythm and Uniformity

**Structure is the #1 detection signal**. AI detection tools weight structural regularity higher than vocabulary.

**Sentence Length Uniformity**
- If most sentences are 15-25 words, the text sounds robotic
- Mix short punchy sentences (3-8 words) with longer flowing ones (20+)
- Fragments work. Questions break the monotony

**Paragraph Length Uniformity**
- If every paragraph is 3-5 sentences and same size, vary deliberately
- Some paragraphs should be one sentence. Some should be longer

**Vocabulary Diversity**
- In longer pieces (200+ words), check type-token ratio
- Human prose: 0.50-0.65 TTR
- AI text: sometimes under 0.40
- Fix: broaden the what — name specific things, cite specific cases

## Pattern Detection Checklist

Use this checklist when auditing content for AI patterns:

### Tier 1 — Must Fix
- [ ] No correlative constructions ("X aren't just Y, they're Z")
- [ ] No forbidden rhetorical flourishes ("The best part?", "Here's the thing...")
- [ ] No forbidden openers ("In today's fast-paced...", "Gone are the days...")
- [ ] No forbidden staccato phrasing ("No fluff. No filler. Just results.")
- [ ] No Tier 1 vocabulary words (delve, leverage, robust, seamless, etc.)
- [ ] Em dashes: zero or one per 1,000 words maximum
- [ ] Bold overuse: one per major section maximum
- [ ] No emoji in headers (except social posts, end-of-line only)
- [ ] No generic conclusions ("In conclusion...", "The future looks bright")
- [ ] No chatbot artifacts ("I hope this helps!", "Great question!")

### Tier 2 — Check Paragraphs
- [ ] No 2+ Tier 2 words in the same paragraph
- [ ] No 2+ Tier 2 phrases in the same piece
- [ ] No cluster of 3+ distinct Tier 2 phrases in one piece
- [ ] Check harness, navigate, foster, elevate, empower usage
- [ ] Check streamline, bolster, cultivate, illuminate usage
- [ ] Check ecosystem, myriad, plethora, encompass usage

### Tier 3 — High Density Check
- [ ] Tier 3 words don't exceed 3% of total word count
- [ ] Check significant, innovative, effective, dynamic usage
- [ ] Check scalable, compelling, unprecedented, exceptional usage
- [ ] Check "just" usage: once per paragraph maximum
- [ ] Check "actually" usage: once per 500 words maximum

### Structural Check
- [ ] Varied sentence lengths (not all 15-25 words)
- [ ] Varied paragraph lengths (not all 3-5 sentences)
- [ ] Bridge sentences between paragraphs
- [ ] No compulsive rule of three
- [ ] No synonym cycling (repeat right words when needed)
- [ ] Reasonable type-token ratio (>0.40 in 200+ words)

## Context-Specific Exceptions

Some patterns are acceptable in specific contexts:

**Technical Documentation**
- Robust, comprehensive, seamless, ecosystem have legitimate technical meanings
- Leverage acceptable when discussing platform leverage/APIs
- Facilitate, underpin, streamline acceptable in technical context
- Delve, tapestry, beacon, testament to, game-changer, harness still flagged

**Academic Writing**
- May need more hedging (perhaps, could potentially)
- Passive voice may be appropriate for neutrality
- Still avoid: correlative constructions, Tier 1 vocabulary

**Legal Documents**
- Require specific phrasing that may sound formal
- Still avoid: correlative constructions, template phrases

**Internal Documentation**
- Can use shortcuts and simplified language
- Still avoid: obvious AI tells that make text generic

## Scoring Methodology

Rate content on a 0-100 scale (lower is better, less AI-like):

| Dimension | Question | Weight |
|-----------|----------|--------|
| Directness | Statements or announcements? | 15 |
| Rhythm | Varied or metronomic? | 20 |
| Trust | Respects reader intelligence? | 15 |
| Authenticity | Sounds human? | 25 |
| Density | Anything cuttable? | 15 |
| Structure | Varied sentence/paragraph length? | 10 |

**Score Interpretation:**
- 0-20: Highly human-sounding
- 21-40: Mostly human, some patterns
- 41-60: Mixed human/AI signals
- 61-80: Strong AI presence
- 81-100: Heavily AI-generated

**Revision Threshold:** Below 35/50, revise before publishing.

## Integration with LSI SEO Rewriting

When using this system for LSI SEO rewriting:

1. **First Pass**: Detect and eliminate Tier 1 patterns (always-remove)
2. **Second Pass**: Scan paragraphs for Tier 2 clusters
3. **Third Pass**: Check Tier 3 density if content feels vague
4. **Final Check**: Verify structural variety and rhythm

**Priority Order:**
1. Structure (rhythm, sentence/paragraph length) — highest signal
2. Tier 1 vocabulary — high confidence AI tells
3. Tier 2 clusters — context-dependent but strong signal
4. Tier 3 density — weak signal alone, meaningful in aggregate

## Quick Reference Tables

### Highest-Priority Removals (Top 10)
1. Correlative construction: "X aren't just Y, they're Z"
2. delve
3. leverage (verb)
4. robust
5. seamless
6. testament to
7. game-changer
8. In today's fast-paced...
9. The best part? ...
10. Let's be honest...

### Most Common Cluster Signals (Top 10)
1. harness + navigate + foster in same paragraph
2. ecosystem + myriad + plethora
3. revolutionize + transformative + paradigm-shifting
4. empower + elevate + unleash
5. streamline + facilitate + bolster
6. resonate + illuminate + elucidate
7. crucial + paramount + cornerstone
8. poised (to) + burgeoning + nascent
9. cultivate + augment + galvanize
10. underpin + underpinning + cornerstone

---

*This system consolidates patterns from avoid-ai-writing, stop-slop, anti-slop, and cdeistopened-anti-ai-writing references into a unified 3-tier detection framework.*
