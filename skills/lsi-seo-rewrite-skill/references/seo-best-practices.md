# SEO Best Practices Reference

Comprehensive guide for on-page SEO optimization, commercial factors, technical considerations, and multi-language support for e-commerce content.

## On-Page SEO Standards

### Title Tag Optimization

**Length Requirements:**
- **50-60 characters** maximum (display limit in SERP)
- **Primary keyword placement**: Near the beginning of title
- **Brand placement**: At the end (pipe separator: `| Brand Name`) unless brand is the primary keyword

**Formula by Page Type:**
- **Product**: `Brand + Product Name + Key Descriptor | Site Name`
- **Category**: `Category Name + Target Audience + Selection Signal | Site Name`
- **Blog**: `Primary Keyword + Hook/Angle + Article Type | Site Name`
- **Landing**: `Value Proposition + Primary Benefit + Urgency Signal`

**Best Practices:**
- Each page must have a unique title (no duplicates)
- Include target keyword naturally without keyword stuffing
- Avoid stop words that waste character space ("and", "or", "the")
- No keyword repetition in title
- Use actionable language for commercial pages

### Meta Description Optimization

**Length Requirements:**
- **150-160 characters** maximum (optimal display)
- **Minimum 120 characters** to provide sufficient context

**Content Structure:**
1. **Opening hook**: Strong verb or benefit statement
2. **Value proposition**: Unique selling point or key feature
3. **Call-to-action**: Clear directive ("Learn more", "Shop now", "Get started")
4. **LSI integration**: 1-2 secondary keywords where natural

**Formula:**
```
[Action verb] + [Primary benefit] + [Specific feature/attribute] + [LSI term]. [CTA].
```

**Best Practices:**
- Write for humans, not robots (must sound natural)
- Include at least one compelling reason to click
- Avoid misleading claims that increase bounce rate
- No double quotes (use single quotes if needed)
- Each page must have a unique description

### Heading Hierarchy

**Structure Rules:**
- **One H1 per page**: Only one H1 tag, matching or closely related to title tag
- **H2 nesting**: H2s divide content into main sections
- **H3-H6 hierarchy**: Use sequentially (no skipping levels)
- **Keyword placement in H2/H3**: Include LSI terms naturally in subheadings

**Best Practices:**
- Headings must describe the content that follows
- Use heading hierarchy to create content outline
- Style headings visually with CSS, not by changing tag levels
- Include primary keyword in H1 or first H2
- Use question-based H2s when targeting PAA (People Also Ask) queries

**Prohibited Patterns:**
- Multiple H1 tags on a single page
- Skipping heading levels (H1 → H3)
- Using headings for styling only
- Generic headings ("Introduction", "Conclusion")

### URL Structure Best Practices

**URL Format:**
```
protocol://domain.com/category-name/page-name
```

**Character Guidelines:**
- Use lowercase letters only
- Separate words with hyphens (`-`)
- Maximum length: 50-60 characters for path
- Remove stop words (a, an, the, and)
- No special characters (except hyphen)
- No underscores (`_`)

**URL by Page Type:**
- **Product**: `/product/brand-product-name-descriptor`
- **Category**: `/category/category-name` (no filters in URL)
- **Blog**: `/blog/primary-keyword-hook`
- **Landing**: `/campaign/benefit-focused-url`

**Technical Requirements:**
- No dynamic parameters in canonical URLs (`?id=`, `&color=`)
- Use canonical tags for duplicate content situations
- No session IDs in URLs
- HTTPS required for all e-commerce pages
- URL should match H1 where possible

### Internal Linking Guidance

**Anchor Text Principles:**
- Use descriptive anchor text (not "click here")
- Include target keyword naturally in anchor
- Vary anchor text to avoid over-optimization
- Anchor text should indicate destination content

**Link Distribution:**
- **Product pages**: Link from relevant categories, related products
- **Category pages**: Link to parent categories, subcategories, featured products
- **Blog posts**: Link to relevant products, related articles, cornerstone content

**Best Practices:**
- 3-5 internal links per 500-word content minimum
- Link to important pages from multiple relevant sources
- Use contextual links within content body
- Ensure link juice flows to priority pages
- No broken links (404s)
- No orphan pages (pages with no internal links pointing to them)

## Commercial Factors & E-A-T

### Trust Signals

**Required Elements for E-commerce:**
- **SSL Certificate**: HTTPS required for all pages
- **Contact Information**: Physical address, phone, email
- **Legal Policies**: Privacy policy, terms of service, return policy
- **Business Details**: Company registration number (if applicable)
- **About Page**: Company story, team information

**Implementation Priority:**
1. Footer links to all policies
2. Contact page with multiple contact methods
3. About page with team credentials
4. Trust badges (payment methods, security seals)

### User-Generated Content (UGC) Integration

**Types of UGC for SEO:**
- **Product Reviews**: Customer feedback and ratings
- **Q&A Sections**: User questions and answers (both community and official)
- **User Photos**: Customer-uploaded product images
- **Testimonials**: Customer success stories

**SEO Benefits:**
- Generates unique, regularly updated content
- Adds long-tail keywords naturally
- Improves dwell time (time on page)
- Increases conversion rate
- Strengthens E-A-T signals

**Implementation Guidelines:**
- Display reviews prominently on product pages
- Include schema markup for reviews (AggregateRating)
- Moderate UGC to prevent spam
- Respond to negative reviews publicly

### Authority Signals

**Author Credentials (for blog/content):**
- Author bio with relevant experience
- Professional credentials and certifications
- Links to social profiles or personal websites
- Author archive page

**Business Authority:**
- Industry awards and recognition
- Media mentions and press coverage
- Partnerships with recognized brands
- Case studies and success stories

**Content Quality Indicators:**
- Date published and updated
- Content accuracy with cited sources
- Depth of coverage (comprehensive vs. superficial)
- Unique insights, not just aggregated information

### Media Representation

**Image Optimization:**
- Use descriptive file names (e.g., `brand-product-name.jpg`)
- Include alt text with target keyword where relevant
- Compress images for page speed (WebP format preferred)
- Responsive images for mobile
- Implement image schema markup where appropriate

**Video Content:**
- Video titles optimized for search
- Video descriptions with keywords and CTAs
- Video transcripts for accessibility and SEO
- Video schema markup
- Video sitemap submission

**Before/After Content:**
- Showcase transformations where applicable
- Use to demonstrate product effectiveness
- Valuable for commercial investigation queries

## Technical SEO Considerations

### Canonical Handling

**When to Use Canonical Tags:**
- Product pages accessible via multiple URLs
- Category filtering and sorting options
- Print-friendly versions of pages
- HTTP/HTTPS and WWW/non-WWW variations

**Implementation:**
```html
<link rel="canonical" href="https://domain.com/preferred-url" />
```

**Best Practices:**
- Point to the preferred version of the page
- Use absolute URLs in canonical tags
- The canonical URL should return 200 status code
- Don't canonicalize to a redirect
- Self-referencing canonicals are acceptable (and recommended)

### Duplicate Content Prevention

**Sources of Duplicate Content:**
- Manufacturer descriptions used by multiple retailers
- URL parameters creating duplicate paths
- Print versions of pages
- HTTP/HTTPS duplicates
- WWW/non-WWW duplicates
- Trailing slash variations

**Prevention Strategies:**
1. **Rewrite manufacturer descriptions** completely (50-100% unique)
2. **Implement canonical tags** for alternative URL versions
3. **Use 301 redirects** for permanently moved content
4. **Implement parameter handling** in Google Search Console
5. **Consistent internal linking** to preferred URLs
6. **Meta robots noindex** for pages that shouldn't be indexed

**Thin Content Avoidance:**
- Minimum word count requirements (see Content Quality Standards)
- No pages with only manufacturer descriptions
- No placeholder or "coming soon" pages indexed
- No near-duplicate pages with minor variations

### Schema Markup Suggestions

**E-commerce Schema Types:**

**Product Schema:**
- Product name, image, description
- Brand and manufacturer information
- SKU/ISBN identifiers
- Offers (price, availability, condition)
- AggregateRating (from reviews)
- Review elements

**Organization Schema:**
- Organization name, logo, URL
- Contact information (address, phone)
- Social media profiles
- Same-as links to knowledge graph entities

**Breadcrumb Schema:**
- Hierarchical site navigation
- Category lineage
- Improves rich snippet display

**Article Schema (for blog):**
- Headline, image, publication date
- Author information
- Publisher information
- Modified date for updated content

**FAQ Schema:**
- Question-answer pairs
- Increases likelihood of PAA inclusion
- Valuable for product and service pages

**Implementation Priority:**
1. Product schema for all product pages
2. Breadcrumb schema for navigation hierarchy
3. Organization schema for home/about pages
4. FAQ schema for FAQ sections
5. Article schema for blog content
6. Review/AggregateRating for pages with reviews

### Mobile Optimization

**Mobile-First Requirements:**
- Responsive design that adapts to all screen sizes
- Touch-friendly navigation (minimum 48x48px tap targets)
- Readable text without zooming (16px base font minimum)
- No horizontal scrolling
- Fast mobile page load times

**Content Parity:**
- Same content on mobile and desktop
- No hidden content on mobile
- Equivalent meta tags across devices
- Mobile-specific structured data where applicable

**Mobile Performance:**
- Accelerated Mobile Pages (AMP) optional but beneficial
- Progressive Web App (PWA) features for engagement
- Mobile-friendly interstitials (no intrusive pop-ups)

## Content Quality Standards

### Minimum Word Counts by Page Type

**Product Pages:**
- **Minimum: 300 words** total content
- **Lead paragraph**: 100-150 words
- **Body content**: 200+ words
- Below 300 words = thin content risk

**Category Pages:**
- **Minimum: 500 words** total content
- **Lead section**: 150-200 words
- **Content blocks**: 300+ words
- Includes selection guidance, product types, applications

**Blog Posts:**
- **Minimum: 500 words** for basic posts
- **Optimal: 1000-1500 words** for comprehensive guides
- **Lead paragraph**: 100-150 words
- Multiple H2 sections (3-5 minimum)

**Landing Pages:**
- **Minimum: 400 words** for focused landing pages
- **Optimal: 600-800 words** for comprehensive offer pages
- Hero section + problem + solution + benefits + FAQ

### Readability Requirements

**General Standards:**
- **Flesch Reading Ease**: 60-70 (standard content)
- **Sentence length**: Average 15-20 words
- **Paragraph length**: Maximum 3-4 sentences (40-50 words)
- **Short words preferred**: Use simple language over jargon
- **Active voice**: Prefer active over passive (80%+ active)

**E-commerce Specific:**
- Technical terminology allowed where product-appropriate
- Explain technical terms for general audience
- Use bullet points for features and specifications
- Use tables for comparisons
- Scannable content with clear sections

**Format for Readability:**
- One idea per paragraph
- Use bullet points for lists
- Use bold text for emphasis (sparingly)
- Use numbered lists for steps or sequences
- Include subheadings every 300 words

### Uniqueness Standards

**Minimum Uniqueness:**
- **80% unique** compared to any other page on site
- **90% unique** compared to manufacturer descriptions
- **100% unique** meta titles and descriptions

**Checking Methodology:**
- Use Copyscape or similar plagiarism checker
- Compare against competitor content
- Check for internal duplication
- Verify manufacturer description uniqueness

**Rewrite Standards:**
- Completely rewrite manufacturer descriptions
- Add unique value propositions
- Include original insights or use cases
- Combine multiple sources into original synthesis
- Add brand-specific context and positioning

### Value Proposition Clarity

**Requirement Definition:**
Every page must answer: "Why choose this product/service?"

**Elements of Clear Value Proposition:**
1. **Specific outcome**: What result will the user achieve?
2. **Timeframe**: How quickly will they see results?
3. **Differentiation**: What makes this offering different from alternatives?
4. **Proof**: What evidence supports the claims?

**Testing Clarity:**
- Can a 12-year-old understand what is offered?
- Is the primary benefit clear above the fold?
- Is the specific value stated in numbers or measurements where applicable?
- Is it clear who should and should not use the product?

## Multi-Language SEO

### Language-Specific Considerations

#### English (en)
- **Primary search engine**: Google
- **Character limits**: Apply standard character limits (title: 50-60, description: 150-160)
- **Keyword placement**: Early placement in titles and headings
- **Content tone**: Can vary by brand (professional, casual, technical)
- **Reference**: Apply all Tier 1-3 anti-AI patterns from anti-ai-patterns.md

#### Russian (ru)
- **Primary search engines**: Yandex (primary), Google (secondary)
- **Character limits**: Similar to English, but Cyrillic characters may display differently
- **Yandex-specific factors**:
  - Commercial factors carry significant weight
  - Regional domain preference (.ru, .ua, .by, .kz)
  - Business credibility signals are critical
  - User behavior metrics are heavily weighted
- **Cyrillic URL handling**: Use transliteration for URLs (Cyrillic → Latin characters)
- **Content tone**: More formal business tone preferred for commercial content
- **Reference**: Apply Russian-specific anti-AI patterns (see multi-language-support.md)

#### Ukrainian (uk)
- **Primary search engine**: Google Ukraine
- **Character limits**: Similar to English
- **Regional considerations**:
  - .ua domain preference for local businesses
  - Ukrainian language support required for local SEO
  - Cultural context in product descriptions
- **Content tone**: Formal for commercial, can be more casual for lifestyle content
- **Reference**: Apply Ukrainian-specific anti-AI patterns (see multi-language-support.md)

### Hreflang Implementation Guidance

**Hreflang Tag Purpose:**
- Signals to search engines which language version to show users
- Prevents duplicate content issues across language versions
- Improves user experience by showing appropriate language version

**Implementation:**
```html
<link rel="alternate" hreflang="en" href="https://domain.com/en/product" />
<link rel="alternate" hreflang="ru" href="https://domain.com/ru/product" />
<link rel="alternate" hreflang="uk" href="https://domain.com/uk/product" />
<link rel="alternate" hreflang="x-default" href="https://domain.com/product" />
```

**Best Practices:**
- Implement hreflang tags for all language versions
- Use x-default for users with unmatched language preferences
- Ensure return links between all language versions
- Use ISO 639-1 language codes (en, ru, uk)
- Self-referencing hreflang tags recommended

**URL Structure for Multi-Language:**
- Subdirectory approach: `/en/`, `/ru/`, `/uk/`
- Subdomain approach: `en.domain.com`, `ru.domain.com`
- Subdirectory preferred for SEO benefits (single domain authority)

### Language-Specific LSI Handling

**English LSI:**
- Derived from Google SERP analysis
- "People Also Ask" and "Related Searches" sources
- Industry terminology and professional terms
- Natural language variations and synonyms

**Russian LSI:**
- Derived from Yandex and Google SERPs
- Industry-specific Russian terminology
- Case endings and grammatical variations
- Cultural and regional language variations

**Ukrainian LSI:**
- Derived from Google Ukraine SERP analysis
- Distinct from Russian terminology (where applicable)
- Cultural and regional language preferences
- Loanwords vs. traditional Ukrainian terms

**LSI Integration by Language:**
- Use language-specific LSI dictionaries (see packaging-lsi-dictionary.md for Russian examples)
- Apply density rules equally across languages (8-12 terms per 1000 words)
- Respect language-specific grammar and syntax
- Use appropriate character counting for density calculation (Cyrillic characters count as single characters)

## Quality Checklist Summary

### Pre-Publication Verification

**Title Tag Check:**
- [ ] Length 50-60 characters
- [ ] Primary keyword present
- [ ] Unique across site
- [ ] No keyword repetition

**Meta Description Check:**
- [ ] Length 150-160 characters
- [ ] CTA included
- [ ] LSI terms integrated
- [ ] Unique across site

**Heading Check:**
- [ ] Only one H1
- [ ] H1 includes primary keyword
- [ ] H2/H3 include LSI terms
- [ ] Proper heading hierarchy

**Content Quality Check:**
- [ ] Minimum word count met
- [ ] No duplicate content
- [ ] Readable at 8th-grade level
- [ ] Clear value proposition

**Technical Check:**
- [ ] Canonical tag present (if needed)
- [ ] Schema markup implemented
- [ ] Mobile-responsive
- [ ] Page load under 3 seconds

**Multi-Language Check (if applicable):**
- [ ] Correct language specified
- [ ] Hreflang tags implemented
- [ ] Language-specific LSI used
- [ ] Character limits appropriate for language

## References

This document synthesizes best practices from:
- Strategic SEO Planning (seo-plan/SKILL.md)
- Deep On-Page SEO Optimization for E-commerce (Оптимизация SEO для E-commerce Сайтов.md)
- Google Search Quality Guidelines
- Yandex Webmaster Guidelines
- Industry-standard SEO frameworks
