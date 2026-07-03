# LSI SEO Rewrite Skill

Production-ready skill for rewriting product pages, category pages, blog posts, and landing pages with LSI keyword integration, anti-AI-pattern cleanup, SEO structure, and page-type-specific examples.

## seos-cli adoption

`seos-cli` is optional for this skill. It is useful only for producing draft/reference SEO text from project settings before the skill applies its own stricter rewrite method.

Candidate commands:

```powershell
seos-cli config check
seos-cli seo-text --keywords "main keyword, supporting keyword" --language en --format json --out outputs/seo-text-draft.json
seos-cli run --keywords "main keyword" --steps seo-text,export --language en --format xlsx --out outputs/seo-text.xlsx
```

Do not treat `seos-cli` output as final. Final content must still satisfy the LSI density, anti-AI pattern cleanup, page-type template, SUCKS/FAB, meta tag, and language-specific checks in `SKILL.md`.

## Contents

- `SKILL.md` - main skill entrypoint.
- `references/` - synthesized frameworks used by the skill at runtime.
- `references/page-templates/` - page-type templates for product, category, blog, and landing pages.
- `examples/before-after/` - example transformations for each supported page type.
- `.planning/` - GSD planning, review, convergence, and verification artifacts.
- `archive/source-references/` - upstream source snapshots used while building the synthesized references.

## Source Repositories Used

See [archive/source-references/README.md](archive/source-references/README.md) for the repository and registry links used to build this skill, including:

- [conorbronsdon/avoid-ai-writing](https://github.com/conorbronsdon/avoid-ai-writing)
- [rand/cc-polymath](https://github.com/rand/cc-polymath)
- [cdeistopened/skill-stack](https://github.com/cdeistopened/skill-stack)
- [hardikpandya/stop-slop](https://github.com/hardikpandya/stop-slop)
- [brianlovin/claude-config](https://github.com/brianlovin/claude-config)
- [Yeachan-Heo/oh-my-claudecode](https://github.com/Yeachan-Heo/oh-my-claudecode)
- [worldwonderer/oh-story-claudecode](https://github.com/worldwonderer/oh-story-claudecode)

## Runtime References

The deployable skill should load the synthesized files in `references/` first. The archived source snapshots are retained for attribution and future refresh work, not as primary runtime references.
