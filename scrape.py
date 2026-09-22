#!/usr/bin/env python3
"""Scrape Polyoxometalates 2025 articles from SciOpen."""

import requests
import json
import re
import time
import html as html_module

JOURNAL_ID = '1556556375104610305'
ISSN = '2957-9821'
JOURNAL_NAME = 'Polyoxometalates'
DOI_PREFIX = '10.26599/POM.'
PUBLISHER = '清华大学出版社'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

# 2025 = Volume 4, Issues 1-4
ISSUE_INDICES = [
    '1808770454720688129',  # Vol 4 Iss 1 (March)
    '1829461788590710785',  # Vol 4 Iss 2 (June)
    '1848912245268516866',  # Vol 4 Iss 3 (September)
    '1968854170804494337',  # Vol 4 Iss 4 (December)
]


def extract_var_page(text):
    """Extract var page JSON array from SciOpen stage_page HTML."""
    start = text.index('var page = ')
    start += len('var page = ')
    depth = 0
    end = start
    for i, ch in enumerate(text[start:], start):
        if ch == '[':
            depth += 1
        elif ch == ']':
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    json_str = text[start:end].replace('\\/', '/')
    return json.loads(json_str)


def get_articles_from_data(data):
    """Extract articles from both flat-array and voList structures."""
    articles = []
    for item in data:
        # If the item has a doi directly, it's a flat article
        if item.get('doi') and not item.get('voList'):
            articles.append(item)
        # If the item has a voList, extract from it
        elif item.get('voList'):
            for article in item['voList']:
                if article.get('doi'):
                    articles.append(article)
    return articles


def extract_meta(html, name):
    """Extract meta tag content, trying both attribute orders."""
    p1 = rf'<meta\s+name="{re.escape(name)}"\s+content="([^"]*)"'
    p2 = rf'<meta\s+content="([^"]*)"\s+name="{re.escape(name)}"'
    for p in [p1, p2]:
        m = re.findall(p, html)
        if m:
            return m
    return []


def clean_affiliation(raw):
    """Clean affiliation string - remove Chinese characters, normalize."""
    if not raw:
        return []
    cleaned = re.sub(r'[\u4e00-\u9fff]+', '', raw)
    cleaned = re.sub(r',\s*,+', ',', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip().strip(',').strip()
    country_end = re.compile(r',\s*([A-Z][A-Z\s]+?)\.\s*')
    splits = list(country_end.finditer(cleaned))
    if not splits:
        return [cleaned] if cleaned else []
    affiliations, start = [], 0
    for m in splits:
        affil = cleaned[start:m.end()].strip().rstrip('.').strip()
        if affil:
            affiliations.append(affil)
        start = m.end()
    remaining = cleaned[start:].strip()
    if remaining:
        affiliations.append(remaining)
    return affiliations


def fetch_article_details(doi):
    """Fetch article detail page and extract metadata."""
    url = f'https://www.sciopen.com/article/{doi}'
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        if resp.status_code != 200:
            print(f"  Failed to fetch {doi}: {resp.status_code}")
            return None
        text = resp.text
    except Exception as e:
        print(f"  Error fetching {doi}: {e}")
        return None

    # Extract meta tags
    title = extract_meta(text, 'citation_title')
    title = title[0] if title else ''

    authors = extract_meta(text, 'citation_author')

    affiliations = []
    for raw in extract_meta(text, 'citation_author_institution'):
        affiliations.extend(clean_affiliation(raw))

    keywords = extract_meta(text, 'citation_keywords')

    volume = extract_meta(text, 'citation_volume')
    volume = volume[0] if volume else ''

    issue = extract_meta(text, 'citation_issue')
    issue = issue[0] if issue else ''

    firstpage = extract_meta(text, 'citation_firstpage')
    firstpage = firstpage[0] if firstpage else ''

    lastpage = extract_meta(text, 'citation_lastpage')
    lastpage = lastpage[0] if lastpage else ''

    pub_date = extract_meta(text, 'citation_publication_date')
    pub_date = pub_date[0] if pub_date else ''

    online_date = extract_meta(text, 'citation_online_date')
    online_date = online_date[0] if online_date else ''

    pdf_url = extract_meta(text, 'citation_pdf_url')
    pdf_url = pdf_url[0] if pdf_url else ''

    publisher = extract_meta(text, 'citation_publisher')
    publisher = publisher[0] if publisher else PUBLISHER

    issn = extract_meta(text, 'citation_issn')
    issn = issn[0] if issn else ISSN

    language = extract_meta(text, 'citation_language')
    language = language[0] if language else 'en'

    # Extract abstract from HTML
    abstract = ''
    abs_match = re.search(r'<h2>Abstract</h2>\s*<div>(.*?)</div>', text, re.DOTALL)
    if abs_match:
        abstract = abs_match.group(1)
        abstract = re.sub(r'<[^>]+>', '', abstract)
        abstract = html_module.unescape(abstract)
        abstract = re.sub(r'\s+', ' ', abstract).strip()

    # Extract dates
    received = re.search(r'Received[:\s]+(\d{1,2}\s+\w+\s+\d{4})', text)
    revised = re.search(r'Revised[:\s]+(\d{1,2}\s+\w+\s+\d{4})', text)
    accepted = re.search(r'Accepted[:\s]+(\d{1,2}\s+\w+\s+\d{4})', text)

    received_date = received.group(1) if received else ''
    revised_date = revised.group(1) if revised else ''
    accepted_date = accepted.group(1) if accepted else ''

    # Extract article type
    art_type = 'Research Article'
    type_match = re.search(r'<span>(Review Article|Research Article|Communication|Editorial|Perspective|Letter|Issue Information)</span>', text)
    if type_match:
        art_type = type_match.group(1)

    # Internal ID from RIS link
    internal_id = ''
    ris_match = re.search(r'download_ris\?tag=2&id=(\d+)', text)
    if ris_match:
        internal_id = ris_match.group(1)

    return {
        'title': title,
        'authors': [{'name': a} for a in authors],
        'affiliations': affiliations,
        'keywords': keywords,
        'abstract': abstract,
        'volume': volume,
        'issue': issue,
        'firstpage': firstpage,
        'lastpage': lastpage,
        'publication_date': pub_date,
        'online_date': online_date,
        'received': received_date,
        'revised': revised_date,
        'accepted': accepted_date,
        'type': art_type,
        'url': f'https://www.sciopen.com/article/{doi}',
        'pdf': pdf_url,
        'internal_id': internal_id,
        'publisher': publisher,
        'issn': issn,
        'language': language,
    }


def parse_journal_and_issue(ji_str):
    """Parse '2025, 4(2): 9140085' into year, volume, issue, article_number."""
    m = re.search(r'(\d{4}),\s*(\d+)\((\d+)\):\s*([\d-]+)', ji_str)
    if m:
        return m.group(1), m.group(2), m.group(3), m.group(4)
    return '', '', '', ''


def main():
    # Step 1: Fetch article list from all 4 issues
    all_articles_raw = []
    
    for issue_idx in ISSUE_INDICES:
        url = 'https://www.sciopen.com/journal/join_journal/stage_page'
        params = {'stage': 5, 'id': JOURNAL_ID, 'issn': ISSN, 'issueIndex': issue_idx}
        resp = requests.get(url, params=params, headers=HEADERS, timeout=30)
        
        data = extract_var_page(resp.text)
        articles = get_articles_from_data(data)
        all_articles_raw.extend(articles)
        print(f"Issue {issue_idx}: {len(articles)} articles")
        time.sleep(0.5)

    # Deduplicate by DOI
    seen = set()
    unique_raw = []
    for a in all_articles_raw:
        doi = a.get('doi')
        if doi and doi not in seen:
            seen.add(doi)
            unique_raw.append(a)

    # Filter for 2025
    articles_2025 = [a for a in unique_raw if '2025' in a.get('journalAndIssue', '')]
    print(f"\nTotal unique 2025 articles: {len(articles_2025)}")

    # Step 2: Fetch details for each article
    final_articles = []
    for i, raw in enumerate(articles_2025):
        doi = raw.get('doi')
        print(f"\n[{i+1}/{len(articles_2025)}] Fetching {doi}...")
        
        details = fetch_article_details(doi)
        if not details:
            continue

        # Build final article record
        year, volume, issue, article_num = parse_journal_and_issue(raw.get('journalAndIssue', ''))
        
        # Use type from list page if detail page didn't find one
        art_type = details['type']
        if art_type == 'Issue Information':
            # Skip Issue Information pages
            print(f"  Skipping Issue Information")
            continue
        
        # Normalize type
        if art_type == 'Review Article':
            art_type = 'Review'
        
        article = {
            'doi': doi,
            'title': details['title'],
            'authors': details['authors'],
            'affiliations': details['affiliations'],
            'keywords': details['keywords'],
            'abstract': details['abstract'],
            'volume': volume,
            'issue': issue,
            'firstpage': details['firstpage'] or article_num,
            'lastpage': details['lastpage'] if details['lastpage'] else '',
            'year': year,
            'publication_date': details['publication_date'],
            'online_date': details['online_date'],
            'received': details['received'],
            'revised': details['revised'],
            'accepted': details['accepted'],
            'type': art_type,
            'url': details['url'],
            'pdf': details['pdf'],
            'internal_id': details['internal_id'],
            'publisher': details['publisher'],
            'issn': details['issn'],
            'language': details['language'],
        }
        
        final_articles.append(article)
        print(f"  Type: {art_type}, Authors: {len(details['authors'])}, Keywords: {len(details['keywords'])}, Abstract: {len(details['abstract'])} chars")
        time.sleep(0.8)

    # Sort by volume/issue/article number
    final_articles.sort(key=lambda a: (int(a['volume']) if a['volume'] else 0, 
                                        int(a['issue']) if a['issue'] else 0, 
                                        int(a['firstpage']) if a['firstpage'] else 0))
    
    # Save to JSON
    output_path = 'D:/Claw/Polyoxometalates/articles_md/articles.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(final_articles, f, ensure_ascii=False, indent=2)
    
    print(f"\n{'='*60}")
    print(f"Saved {len(final_articles)} articles to {output_path}")
    
    # Summary
    from collections import Counter
    types = Counter(a['type'] for a in final_articles)
    print(f"Types: {dict(types)}")
    
    with_abstract = sum(1 for a in final_articles if a['abstract'])
    print(f"With abstract: {with_abstract}/{len(final_articles)}")
    
    with_keywords = sum(1 for a in final_articles if a['keywords'])
    print(f"With keywords: {with_keywords}/{len(final_articles)}")


if __name__ == '__main__':
    main()
