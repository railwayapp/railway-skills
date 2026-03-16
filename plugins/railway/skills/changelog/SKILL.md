---
name: changelog
description: >
  Read and search Railway's product changelog. Use when the user asks about recent Railway changes,
  new features, what shipped, "what's new", release history, or wants to look up a specific changelog entry.
allowed-tools: WebFetch, Bash(curl:*)
---

# Changelog

Railway publishes a weekly product changelog. All changelog data is available as markdown for easy consumption.

## Data Sources

### Index: all entries

Fetch the full changelog index:

```
https://railway.com/llms-changelog.md
```

Returns a list of every changelog entry with this format per entry:

```
# Railway Product Changelog <Title>
- Title: <title>
- Number: #<4-digit number>
- Link: https://railway.com/changelog/<slug>.md
- Date: <M/D/YYYY>
----------------------------------------
```

Entries are numbered descending (newest first). The index currently contains 280+ entries spanning 2021 to present.

### Individual entry

Every entry link from the index is already an `.md` URL. Fetch it directly:

```
https://railway.com/changelog/<slug>.md
```

Returns full markdown with YAML frontmatter:

```yaml
---
title: "<title>"
date: <YYYY-MM-DD>
number: <4-digit number>
url: https://railway.com/changelog/<slug>
---
```

Followed by the full post body (headings, images, links, etc.).

## Quick Operations

### Get latest changelog entries

1. Fetch `https://railway.com/llms-changelog.md`
2. The first entries are the most recent. Extract the titles, dates, and links.

### Read a specific entry

1. Take the link from the index (already ends in `.md`)
2. Fetch it directly to get the full post content

### Search for a topic

1. Fetch the index
2. Scan entry titles for keywords
3. Fetch matching entries for full details

### Get the N most recent entries

1. Fetch the index
2. Take the first N entries
3. Optionally fetch each one for full content

## Routing

| Intent | Action |
|---|---|
| "What's new" / "latest changelog" / "recent changes" | Fetch index, return top 3-5 entries with titles and dates |
| "Tell me about <feature>" | Fetch index, find matching entry by title, fetch that entry's `.md` URL |
| "What shipped on <date>" | Fetch index, find entry matching the date, fetch full content |
| "Summarize changelog #<number>" | Fetch index, find by number, fetch full content |
| "What's the changelog URL" | Return `https://railway.com/changelog` (web) or `https://railway.com/llms-changelog.md` (markdown) |

## Execution Rules

1. Always fetch fresh data. The changelog updates weekly (typically Thursdays).
2. Use `WebFetch` to retrieve markdown content. Fall back to `curl` if WebFetch is unavailable.
3. When summarizing entries, preserve the entry number and date for reference.
4. Link to the human-readable URL (without `.md`) when presenting results to users.
5. For broad questions ("what's new"), return 3-5 recent entries. Don't dump the entire index.
6. For specific lookups, fetch the full entry content and summarize the relevant sections.

## Response Format

When presenting changelog entries:

- **Title** with link to `https://railway.com/changelog/<slug>` (no `.md` suffix for user-facing links)
- **Date** and **number**
- **Summary** of key items when full content is fetched
