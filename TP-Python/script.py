#!/usr/bin/env python3
"""
Tubi to Prowlarr Analyzer
Combines HTML parsing and torrent availability checking
Supports multiple HTML file batches with persistent API key storage
"""

import csv
import time
import os
import sys
from pathlib import Path
from datetime import datetime
from bs4 import BeautifulSoup
import requests


PROWLARR_URL = "http://localhost:9696"
API_KEY_FILE = "prowlarr_current_api_key"
REQUEST_DELAY = 0.5


def get_api_key():
    """Get API key from file or prompt user."""
    script_dir = Path(__file__).parent
    key_file = script_dir / API_KEY_FILE

    if key_file.exists():
        key = key_file.read_text().strip()
        if key:
            return key, key_file

    return None, key_file


def save_api_key(key, key_file):
    """Save API key to file."""
    key_file.write_text(key)
    print(f"  ✓ API key saved to {key_file.name}")


def validate_api_key(api_key):
    """Test if API key works with Prowlarr."""
    try:
        url = f"{PROWLARR_URL}/api/v1/search"
        params = {'query': 'test', 'apikey': api_key}
        response = requests.get(url, params=params, timeout=10)
        return response.status_code == 200
    except:
        return False


def get_working_api_key():
    """Get and validate API key, with retry logic."""
    api_key, key_file = get_api_key()

    if api_key:
        print(f"\nFound saved API key: {api_key[:8]}...")
        print("Testing connection...")
        if validate_api_key(api_key):
            print("  ✓ API key valid")
            return api_key
        else:
            print(f"\n✗ Not able to complete operation with key [{api_key}]")

    # Need to get new key
    while True:
        api_key = input("\nEnter your Prowlarr API key: ").strip()
        if not api_key:
            print("API key required!")
            continue

        print("Testing connection...")
        if validate_api_key(api_key):
            print("  ✓ API key valid")
            save_api_key(api_key, key_file)
            return api_key
        else:
            print(f"\n✗ Not able to complete operation with key [{api_key}]")
            print("Please check:")
            print("  - Is Prowlarr running on localhost:9696?")
            print("  - Did you copy the correct API key from Settings > General?")
            retry = input("\nTry again? (y/n): ").strip().lower()
            if retry != 'y':
                sys.exit(1)


def parse_tubi_html(html_content, source_name):
    """Parse Tubi HTML and extract content metadata."""
    soup = BeautifulSoup(html_content, 'html.parser')
    items = []

    tiles = soup.find_all('div', class_='web-content-tile')

    for tile in tiles:
        try:
            title_link = tile.find('a', class_='web-content-tile__title')
            if not title_link:
                continue

            title = title_link.get_text(strip=True)
            href = title_link.get('href', '')
            full_url = f"https://tubitv.com{href}" if href.startswith('/') else href

            content_type = 'unknown'
            if '/movies/' in href:
                content_type = 'movie'
            elif '/series/' in href:
                content_type = 'series'

            year_elem = tile.find('div', class_='web-content-tile__year')
            year = year_elem.get_text(strip=True) if year_elem else ''

            duration_elem = tile.find('div', class_='web-content-tile__duration')
            duration = duration_elem.get_text(strip=True) if duration_elem else ''

            rating_elem = tile.find('div', class_='web-rating')
            rating = rating_elem.get_text(strip=True) if rating_elem else ''

            descriptor_elems = tile.find_all('span', class_='web-content-tile__descriptor-item')
            descriptors = ', '.join([d.get_text(strip=True) for d in descriptor_elems]) if descriptor_elems else ''

            tags_elem = tile.find('div', class_='web-content-tile__tags')
            genres = ''
            if tags_elem:
                tags_text = tags_elem.get_text(strip=True)
                genres = tags_text.replace('\xa0·\xa0', ', ').replace('·', ', ')

            items.append({
                'title': title,
                'type': content_type,
                'year': year,
                'duration': duration,
                'rating': rating,
                'genres': genres,
                'descriptors': descriptors,
                'tubi_url': full_url,
                'batch': source_name
            })

        except Exception as e:
            continue

    return items


def search_prowlarr(title, api_key):
    """Search Prowlarr for torrent availability."""
    try:
        url = f"{PROWLARR_URL}/api/v1/search"
        params = {'query': title, 'apikey': api_key}
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        results = response.json()

        if not results:
            return False, 0, 0

        max_seeders = 0
        for result in results:
            seeders = result.get('seeders', 0) or 0
            if seeders > max_seeders:
                max_seeders = seeders

        return True, max_seeders, len(results)

    except Exception as e:
        return None, 0, 0


def determine_status(found, max_seeders):
    """Determine torrent status category."""
    if not found:
        return False, "not_found"
    if max_seeders <= 5:
        return True, "low_seed"
    return True, "healthy"


def collect_html_files():
    """Collect multiple HTML files from user with naming."""
    batches = []
    batch_count = 0

    print("=" * 70)
    print("Tubi HTML File Collection")
    print("=" * 70)

    while True:
        batch_count += 1
        print(f"\n--- Batch {batch_count} ---")

        # Get file path
        file_path = input("Paste the path to your Tubi HTML file: ").strip().strip('"')
        path = Path(file_path)

        if not path.exists():
            print(f"✗ File not found: {file_path}")
            retry = input("Try again? (y/n): ").strip().lower()
            if retry == 'y':
                batch_count -= 1  # Don't count this attempt
                continue
            else:
                if not batches:
                    print("No files processed. Exiting.")
                    sys.exit(0)
                break

        # Read and parse HTML
        try:
            with open(path, 'r', encoding='utf-8') as f:
                html_content = f.read()
        except Exception as e:
            print(f"✗ Error reading file: {e}")
            if not batches:
                continue
            break

        items = parse_tubi_html(html_content, "temp")  # Batch name updated below

        if not items:
            print("✗ No content found in this file!")
            retry = input("Try a different file? (y/n): ").strip().lower()
            if retry == 'y':
                batch_count -= 1
                continue
            else:
                if not batches:
                    sys.exit(0)
                break

        print(f"✓ Found {len(items)} titles")

        # Get batch name
        batch_name = input(f"Name this batch (or press Enter for auto-name): ").strip()
        if not batch_name:
            batch_name = f"SET {['ONE', 'TWO', 'THREE', 'FOUR', 'FIVE', 'SIX'][batch_count-1] if batch_count <= 6 else f'SET {batch_count}'}"
            print(f"  Auto-named: {batch_name}")

        # Update batch name in items
        for item in items:
            item['batch'] = batch_name

        batches.append({
            'name': batch_name,
            'items': items,
            'count': len(items)
        })

        # Ask for another
        another = input("\nWould you like to analyze another HTML file? (y/n): ").strip().lower()
        if another != 'y':
            break

    return batches


def process_batch(batch, api_key, batch_num, total_batches):
    """Process a single batch through Prowlarr."""
    print("\n" + "=" * 70)
    print(f"Processing Batch {batch_num}/{total_batches}: {batch['name']}")
    print(f"Titles: {batch['count']}")
    print("=" * 70)

    results = []
    not_found_list = []
    low_seed_list = []
    items = batch['items']

    for i, item in enumerate(items, 1):
        title = item['title']
        year = item.get('year', '')

        print(f"[{i}/{batch['count']}] {title} ({year})...", end=" ")

        found, max_seeders, total_results = search_prowlarr(title, api_key)

        if found is None:
            print("[ERROR]")
            item['torrent_found'] = False
            item['seed_status'] = "error"
            item['max_seeders'] = 0
            item['total_results'] = 0
        else:
            torrent_found, seed_status = determine_status(found, max_seeders)
            item['torrent_found'] = torrent_found
            item['seed_status'] = seed_status
            item['max_seeders'] = max_seeders
            item['total_results'] = total_results

            if seed_status == "not_found":
                print("[NOT FOUND]")
                not_found_list.append(item)
            elif seed_status == "low_seed":
                print(f"[LOW SEED - {max_seeders}]")
                low_seed_list.append(item)
            else:
                print(f"[HEALTHY - {max_seeders}]")

        results.append(item)

        if i < len(items):
            time.sleep(REQUEST_DELAY)

    # Print batch summary
    not_found_count = sum(1 for r in results if r['seed_status'] == 'not_found')
    low_count = sum(1 for r in results if r['seed_status'] == 'low_seed')
    healthy_count = sum(1 for r in results if r['seed_status'] == 'healthy')

    print("\n" + "-" * 70)
    print(f"Batch Summary: {batch['name']}")
    print(f"  Not Found: {not_found_count} | Low Seed: {low_count} | Healthy: {healthy_count}")

    if not_found_list:
        print("\n  Not Found:")
        for item in not_found_list:
            print(f"    • {item['title']} ({item['year']})")

    if low_seed_list:
        print("\n  Low Seed:")
        for item in low_seed_list:
            print(f"    • {item['title']} ({item['year']}) - {item['max_seeders']} seeders")

    return results


def save_combined_csv(all_results, batches):
    """Save all results to CSV with batch separators."""
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    output_file = f"tubi_analysis_{timestamp}.csv"

    # Prepare fieldnames
    fieldnames = ['title', 'type', 'year', 'duration', 'rating', 'genres', 'descriptors', 
                  'tubi_url', 'torrent_found', 'seed_status', 'max_seeders', 'total_results']

    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        current_batch = None
        for item in all_results:
            # Insert separator if new batch
            if item['batch'] != current_batch:
                if current_batch is not None:
                    # Empty row for spacing
                    writer.writerow({})
                # Separator row
                separator = {k: '' for k in fieldnames}
                separator['title'] = f"=== {item['batch'].upper()} ==="
                writer.writerow(separator)
                current_batch = item['batch']

            # Write item (remove batch key)
            row = {k: v for k, v in item.items() if k in fieldnames}
            writer.writerow(row)

    return output_file


def main():
    print("=" * 70)
    print("Tubi to Prowlarr Analyzer")
    print("=" * 70)

    # Step 1: Collect HTML files
    batches = collect_html_files()

    if not batches:
        print("\nNo files to process. Exiting.")
        return

    total_titles = sum(b['count'] for b in batches)
    print("\n" + "=" * 70)
    print(f"Collection Complete: {len(batches)} batches, {total_titles} total titles")
    print("=" * 70)
    for batch in batches:
        print(f"  • {batch['name']}: {batch['count']} titles")

    # Step 2: Get API Key
    print("\n" + "=" * 70)
    print("Prowlarr Configuration")
    print("=" * 70)
    api_key = get_working_api_key()

    # Step 3: Process each batch
    print("\n" + "=" * 70)
    print("Starting Prowlarr Analysis")
    print("=" * 70)

    all_results = []
    for i, batch in enumerate(batches, 1):
        batch_results = process_batch(batch, api_key, i, len(batches))
        all_results.extend(batch_results)

        if i < len(batches):
            print("\n" + "=" * 70)
            cont = input("Press Enter to continue to next batch...")

    # Step 4: Save results
    print("\n" + "=" * 70)
    print("Saving Results")
    print("=" * 70)

    output_file = save_combined_csv(all_results, batches)
    print(f"✓ Saved to: {output_file}")

    # Final summary
    not_found_total = sum(1 for r in all_results if r['seed_status'] == 'not_found')
    low_total = sum(1 for r in all_results if r['seed_status'] == 'low_seed')
    healthy_total = sum(1 for r in all_results if r['seed_status'] == 'healthy')

    print(f"\nFinal Summary:")
    print(f"  Total: {len(all_results)} titles")
    print(f"  Not Found: {not_found_total}")
    print(f"  Low Seed: {low_total}")
    print(f"  Healthy: {healthy_total}")
    print("\nDone!")


if __name__ == "__main__":
    main()
