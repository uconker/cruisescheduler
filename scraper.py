import cloudscraper
import json
import re
import time
from bs4 import BeautifulSoup
import os

def scrape_ehoi():
    print("Starting e-hoi Flat-List Crawler (Anti-Bot Edition)...")
    
    # Use cloudscraper to bypass Cloudflare on GitHub Action IPs
    session = cloudscraper.create_scraper(
        browser={
            'browser': 'chrome',
            'platform': 'windows',
            'desktop': True
        }
    )
    
    cruise_db = {}
    max_pages = 200 
    
    print("\n--- GATHERING ALL TRIPS & 2-ADULT PRICES ---")
    
    # Initial visit to get natural browser cookies
    try:
        print("Acquiring initial cookies...")
        session.get("https://www.e-hoi.de", timeout=30)
        time.sleep(2)
    except Exception as e:
        print(f"Initial cookie fetch failed: {e}")

    page_num = 1
    
    while page_num <= max_pages:
        # Explicit URL with all parameters attached
        ajax_url = f"https://www.e-hoi.de/?fuseaction=mod_kreuzfahrtkalender.showkreuzfahrtkalender&referenceID=64&referenceType=destination&departdate=08.07.2026&arrivdate=11.10.2026&daterange=08.07.2026%20-%2011.10.2026&reisedauer=1-5&reisedauer=6-9&personen=2&sort=departDate_asc&page={page_num}"
        
        try:
            ajax_headers = {
                "X-Requested-With": "XMLHttpRequest",
                "Referer": "https://www.e-hoi.de/mittelmeer-kreuzfahrten/fahrgebiet-64.html"
            }
            
            max_retries = 3
            response = None
            for attempt in range(max_retries):
                try:
                    response = session.get(ajax_url, headers=ajax_headers, timeout=60)
                    break
                except Exception as e:
                    print(f"  -> Timeout/Error on page {page_num}! Retrying ({attempt + 1}/{max_retries})...")
                    time.sleep(5)
            
            if not response:
                print(f"Giving up on page {page_num}.")
                break

            response.encoding = 'utf-8'
            
            # Anti-Bot Detection Check
            if "cloudflare" in response.text.lower() or "just a moment" in response.text.lower():
                print(f"🚨 BLOCKED BY CLOUDFLARE on page {page_num}! Scraper detected as a bot.")
                print("Aborting scrape to protect existing JSON data.")
                return # Abort without overwriting the file

            if not response.text.strip():
                print(f"Empty response on page {page_num}. This usually means the end of the calendar.")
                break

            soup = BeautifulSoup(response.text, 'html.parser')
            table = soup.find('table', class_='table')
            
            if not table:
                print(f"No table found on page {page_num}. Ending scrape.")
                break
                
            tbody = table.find('tbody')
            if not tbody:
                break
                
            rows = tbody.find_all('tr')
            if not rows:
                break
                
            valid_rows = 0
            
            for row in rows:
                cols = row.find_all('td')
                if len(cols) < 6:
                    continue
                    
                # Extract Exact Date
                date_text = cols[0].get_text(separator=' ', strip=True)
                date_match = re.search(r'(\d{2}\.\d{2}\.\d{4})', date_text)
                if not date_match:
                    continue
                start_date = date_match.group(1)
                
                # Extract Link & Route ID
                link_elem = cols[5].find('a', href=True)
                if not link_elem:
                    continue
                url = link_elem['href']
                if url.startswith('/'):
                    url = "https://www.e-hoi.de" + url
                    
                id_match = re.search(r'/(\d+)_\d+/', url)
                if not id_match:
                    id_match = re.search(r'routeplanid=(\d+)', url)
                    if not id_match:
                        continue
                route_id = id_match.group(1)
                
                # Extract Price
                price_em = cols[5].find('em')
                price_text = price_em.text if price_em else cols[5].get_text()
                price_val_match = re.search(r'(\d+[\.,]?\d*)', price_text.replace('.', ''))
                if not price_val_match:
                    continue
                price_val = int(price_val_match.group(1))

                # Clean Up
                ship_text = cols[1].get_text(separator=' ', strip=True).replace("Schiff:", "").strip()
                ship_name = re.split(r'\(', ship_text)[0].strip() if ship_text else "Unbekannt"
                
                dur_text = cols[2].get_text(strip=True)
                dur_match = re.search(r'(\d+)', dur_text)
                duration = int(dur_match.group(1)) if dur_match else 0
                
                ports_text = cols[3].get_text(separator=' ', strip=True).replace('\n', ' ').replace("Route:", "").strip()
                ports_text = re.sub(r'\s+', ' ', ports_text)
                
                # Unique Key Generation
                trip_key = f"{route_id}_{start_date}"
                
                if trip_key not in cruise_db:
                    first_port = ports_text.split('-')[0].strip() if '-' in ports_text else ports_text
                    cruise_db[trip_key] = {
                        "id": trip_key,
                        "date": start_date,
                        "title": f"Mittelmeer Kreuzfahrt ab {first_port}",
                        "ship": ship_name,
                        "duration_days": duration,
                        "cabin_type": "Günstigste verfügbare Kabine",
                        "url": url,
                        "ports": ports_text,
                        "prices_per_person": {
                            "2_adults": price_val
                        },
                        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")
                    }
                    valid_rows += 1
                
            print(f"-> Extracted {valid_rows} unique departure blocks from calendar page {page_num}.")
            
            if valid_rows == 0:
                break
                
            page_num += 1
            time.sleep(1.5) 
            
        except Exception as e:
            print(f"Error on page {page_num}: {e}")
            break

    # If the database is completely empty, don't overwrite the existing file
    if len(cruise_db) == 0:
        print("🚨 Scrape finished but 0 cruises were found. Aborting to protect existing JSON.")
        return

    print("\n--- FINALIZING DATA ---")
    trips_list = list(cruise_db.values())
    with open('cruises.json', 'w', encoding='utf-8') as f:
        json.dump(trips_list, f, indent=4, ensure_ascii=False)
        
    print(f"Mission Accomplished! Perfectly saved {len(trips_list)} flat-list trips.")

if __name__ == "__main__":
    scrape_ehoi()
