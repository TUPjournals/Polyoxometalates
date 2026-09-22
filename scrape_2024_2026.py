#!/usr/bin/env python3
"""Scrape Polyoxometalates 2024 + 2026 articles and merge with existing 2025 data."""

import requests
import json
import re
import time
import html as html_module
import os

JOURNAL_ID = '1556556375104610305'
ISSN = '2957-9821'
JOURNAL_NAME = 'Polyoxometalates'
DOI_PREFIX = '10.26599/POM.'
PUBLISHER = '清华大学出版社'
BASE_DIR = 'D:/Claw/Polyoxometalates'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

def extract_var_page(text):
    start = text.index('var page = ')
    start += len('var page = ')
    depth = 0
    end = start
    for i, ch in enumerate(text[start:], start):
        if ch == '[': depth += 1
        elif ch == ']':
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    return json.loads(text[start:end].replace('\\/', '/'))

def get_articles_from_data(data):
    articles = []
    for item in data:
        if item.get('doi') and not item.get('voList'):
            articles.append(item)
        elif item.get('voList'):
            for article in item['voList']:
                if article.get('doi'):
                    articles.append(article)
    return articles

def extract_meta(html, name):
    p1 = rf'<meta\s+name="{re.escape(name)}"\s+content="([^"]*)"'
    p2 = rf'<meta\s+content="([^"]*)"\s+name="{re.escape(name)}"'
    for p in [p1, p2]:
        m = re.findall(p, html)
        if m: return m
    return []

def clean_affiliation(raw):
    if not raw: return []
    cleaned = re.sub(r'[\u4e00-\u9fff]+', '', raw)
    cleaned = re.sub(r',\s*,+', ',', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip().strip(',').strip()
    splits = list(re.finditer(r',\s*([A-Z][A-Z\s]+?)\.\s*', cleaned))
    if not splits: return [cleaned] if cleaned else []
    affiliations, start = [], 0
    for m in splits:
        affil = cleaned[start:m.end()].strip().rstrip('.').strip()
        if affil: affiliations.append(affil)
        start = m.end()
    remaining = cleaned[start:].strip()
    if remaining: affiliations.append(remaining)
    return affiliations

def fetch_article_details(doi):
    url = f'https://www.sciopen.com/article/{doi}'
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        if resp.status_code != 200: return None
        text = resp.text
    except: return None

    title = extract_meta(text, 'citation_title')
    authors = extract_meta(text, 'citation_author')
    affiliations = []
    for raw in extract_meta(text, 'citation_author_institution'):
        affiliations.extend(clean_affiliation(raw))
    keywords = extract_meta(text, 'citation_keywords')
    volume = extract_meta(text, 'citation_volume')
    issue = extract_meta(text, 'citation_issue')
    firstpage = extract_meta(text, 'citation_firstpage')
    lastpage = extract_meta(text, 'citation_lastpage')
    pub_date = extract_meta(text, 'citation_publication_date')
    online_date = extract_meta(text, 'citation_online_date')
    pdf_url = extract_meta(text, 'citation_pdf_url')
    publisher = extract_meta(text, 'citation_publisher')
    issn = extract_meta(text, 'citation_issn')
    language = extract_meta(text, 'citation_language')

    abstract = ''
    abs_match = re.search(r'<h2>Abstract</h2>\s*<div>(.*?)</div>', text, re.DOTALL)
    if abs_match:
        abstract = abs_match.group(1)
        abstract = re.sub(r'<[^>]+>', '', abstract)
        abstract = html_module.unescape(abstract)
        abstract = re.sub(r'\s+', ' ', abstract).strip()

    received = re.search(r'Received[:\s]+(\d{1,2}\s+\w+\s+\d{4})', text)
    revised = re.search(r'Revised[:\s]+(\d{1,2}\s+\w+\s+\d{4})', text)
    accepted = re.search(r'Accepted[:\s]+(\d{1,2}\s+\w+\s+\d{4})', text)

    art_type = 'Research Article'
    type_match = re.search(r'<span>(Review Article|Research Article|Communication|Editorial|Perspective|Letter|Issue Information)</span>', text)
    if type_match: art_type = type_match.group(1)
    if art_type == 'Review Article': art_type = 'Review'

    internal_id = ''
    ris_match = re.search(r'download_ris\?tag=2&id=(\d+)', text)
    if ris_match: internal_id = ris_match.group(1)

    return {
        'title': title[0] if title else '',
        'authors': [{'name': a} for a in authors],
        'affiliations': affiliations,
        'keywords': keywords,
        'abstract': abstract,
        'volume': volume[0] if volume else '',
        'issue': issue[0] if issue else '',
        'firstpage': firstpage[0] if firstpage else '',
        'lastpage': lastpage[0] if lastpage else '',
        'publication_date': pub_date[0] if pub_date else '',
        'online_date': online_date[0] if online_date else '',
        'received': received.group(1) if received else '',
        'revised': revised.group(1) if revised else '',
        'accepted': accepted.group(1) if accepted else '',
        'type': art_type,
        'url': f'https://www.sciopen.com/article/{doi}',
        'pdf': pdf_url[0] if pdf_url else '',
        'internal_id': internal_id,
        'publisher': publisher[0] if publisher else PUBLISHER,
        'issn': issn[0] if issn else ISSN,
        'language': language[0] if language else 'en',
    }

def parse_journal_and_issue(ji_str):
    m = re.search(r'(\d{4}),\s*(\d+)\((\d+)\):\s*([\d-]+)', ji_str)
    if m: return m.group(1), m.group(2), m.group(3), m.group(4)
    return '', '', '', ''

def main():
    # Load existing 2025 articles
    json_path = f'{BASE_DIR}/articles_md/articles.json'
    with open(json_path, 'r', encoding='utf-8') as f:
        existing = json.load(f)
    existing_dois = {a['doi'] for a in existing}
    print(f"Existing 2025 articles: {len(existing)}")

    # 2024 issue indices
    issue_map = {
        '2024': ['1722078327450664962', '1742028982172897282', '1754758470887350274', '1791365326195736577'],
        '2026': ['2017047833149534209', '2017126393839185922', '2059531611037814785', '2086623768441561090'],
    }

    all_new_raw = []
    for year, indices in issue_map.items():
        print(f"\n--- Fetching {year} ---")
        for idx in indices:
            url = 'https://www.sciopen.com/journal/join_journal/stage_page'
            params = {'stage': 5, 'id': JOURNAL_ID, 'issn': ISSN, 'issueIndex': idx}
            resp = requests.get(url, params=params, headers=HEADERS, timeout=30)
            data = extract_var_page(resp.text)
            articles = get_articles_from_data(data)
            print(f"  {idx}: {len(articles)} articles")
            all_new_raw.extend(articles)
            time.sleep(0.5)

    # Deduplicate
    seen = set()
    unique_new = []
    for a in all_new_raw:
        doi = a.get('doi')
        if doi and doi not in seen and doi not in existing_dois:
            seen.add(doi)
            unique_new.append(a)

    # Filter out Issue Information
    unique_new = [a for a in unique_new if a.get('type') != 'Issue Information']
    print(f"\nNew articles to fetch details: {len(unique_new)}")

    # Fetch details for all new articles
    new_articles = []
    for i, raw in enumerate(unique_new):
        doi = raw.get('doi')
        print(f"[{i+1}/{len(unique_new)}] {doi}...", end=' ', flush=True)
        
        details = fetch_article_details(doi)
        if not details:
            print("SKIP")
            continue
        
        year, volume, issue, article_num = parse_journal_and_issue(raw.get('journalAndIssue', ''))
        art_type = details['type']
        if art_type == 'Issue Information': continue
        
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
            'lastpage': details['lastpage'],
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
        new_articles.append(article)
        print(f"OK ({art_type})")
        time.sleep(0.5)

    # Merge with existing
    all_articles = existing + new_articles
    
    # Sort: volume desc, issue desc, firstpage desc (numeric)
    all_articles.sort(key=lambda a: (
        int(a['volume']) if a['volume'] else 0,
        int(a['issue']) if a['issue'] else 0,
        int(a['firstpage']) if a['firstpage'] else 0
    ), reverse=True)

    # Save
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(all_articles, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"Total articles: {len(all_articles)} (was {len(existing)}, added {len(new_articles)})")
    from collections import Counter
    print(f"By year: {dict(Counter(a['year'] for a in all_articles))}")
    print(f"By type: {dict(Counter(a['type'] for a in all_articles))}")
    print(f"With abstract: {sum(1 for a in all_articles if a['abstract'])}/{len(all_articles)}")

if __name__ == '__main__':
    main()
