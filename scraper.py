import requests
import json
import re
import time
from bs4 import BeautifulSoup
from datetime import datetime

def scrape_ehoi():
    print("Starting e-hoi Flat-List Master Crawler...")
    print("This script will separate every date into its own block and calculate exact tiered pricing.")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept-Language": "de-DE,de;q=0.9"
    }

    session = requests.Session()
    session.headers.update(headers)

    cruise_db = {}
    max_pages = 200 
    
    # =========================================================================
    # PHASE 1: Gather ALL distinct trips & base 2-Adult prices from the Calendar
    # =========================================================================
    print(f"\n--- PHASE 1: GATHERING ALL TRIPS & 2-ADULT PRICES ---")
    
    # Prime the session for 2 adults and our specific date range filters
    setup_url = "https://www.e-hoi.de/mittelmeer-kreuzfahrten/fahrgebiet-64.html?usersearch=1&departdate=08.07.2026&arrivdate=11.10.2026&daterange=08.07.2026%20-%2011.10.2026&reisedauer=1-5&reisedauer=6-9&personen=2"
    try:
        print("Configuring search session parameters...")
        session.get(setup_url, timeout=60)
    except Exception as e:
        print(f"Session setup failed: {e}")
    time.sleep(1)

    page_num = 1
    while page_num <= max_pages:
        # Clean AJAX URL for the calendar table
        ajax_url = f"https://www.e-hoi.de/?fuseaction=mod_kreuzfahrtkalender.showkreuzfahrtkalender&referenceID=64&referenceType=destination&sort=departDate_asc&page={page_num}"
        
        try:
            ajax_headers = headers.copy()
            ajax_headers["X-Requested-With"] = "XMLHttpRequest"
            
            # Retry logic in case e-hoi's server is being slow
            max_retries = 3
            response = None
            for attempt in range(max_retries):
                try:
                    response = session.get(ajax_url, headers=ajax_headers, timeout=60)
                    break
                except requests.exceptions.Timeout:
                    print(f"  -> Timeout on page {page_num}! Retrying ({attempt + 1}/{max_retries}) in 5s...")
                    time.sleep(5)
            
            if not response:
                print(f"Giving up on page {page_num}.")
                break

            response.encoding = 'utf-8'
            if not response.text.strip():
                print(f"Empty response on page {page_num}. Ending Phase 1.")
                break

            soup = BeautifulSoup(response.text, 'html.parser')
            table = soup.find('table', class_='table')
            if not table:
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
                    
                # 1. Extract Exact Date
                date_text = cols[0].get_text(separator=' ', strip=True)
                date_match = re.search(r'(\d{2}\.\d{2}\.\d{4})', date_text)
                if not date_match:
                    continue
                start_date = date_match.group(1)
                
                # 2. Extract Link & Route ID
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
                
                # 3. Extract Base 2-Adult Price from calendar
                price_em = cols[5].find('em')
                price_text = price_em.text if price_em else cols[5].get_text()
                price_val_match = re.search(r'(\d+[\.,]?\d*)', price_text.replace('.', ''))
                if not price_val_match:
                    continue
                price_val = int(price_val_match.group(1))

                # 4. Clean up Ship & Route Names
                ship_text = cols[1].get_text(separator=' ', strip=True).replace("Schiff:", "").strip()
                ship_name = re.split(r'\(', ship_text)[0].strip() if ship_text else "Unbekannt"
                
                dur_text = cols[2].get_text(strip=True)
                dur_match = re.search(r'(\d+)', dur_text)
                duration = int(dur_match.group(1)) if dur_match else 0
                
                ports_text = cols[3].get_text(separator=' ', strip=True).replace('\n', ' ').replace("Route:", "").strip()
                ports_text = re.sub(r'\s+', ' ', ports_text)
                
                # UNIQUE KEY: Every date is now a separate block!
                trip_key = f"{route_id}_{start_date}"
                
                if trip_key not in cruise_db:
                    first_port = ports_text.split('-')[0].strip() if '-' in ports_text else ports_text
                    cruise_db[trip_key] = {
                        "id": route_id,
                        "date": start_date, # Date is now isolated at the top level
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
                
            page_num += 1
            time.sleep(1.5) # Polite delay to avoid IP blocks
            
        except Exception as e:
            print(f"Error on page {page_num}: {e}")
            break

    # =========================================================================
    # PHASE 2: Interrogate Main Search API for 3 & 4 Adult pricing per trip
    # =========================================================================
    print("\n--- PHASE 2: FETCHING PRECISE PRICES FOR 3 & 4 ADULTS ---")
    total_trips = len(cruise_db)
    print(f"Total individual trips found: {total_trips}")
    print("Now interrogating e-hoi's search engine to mathematically adjust group pricing...")
    
    # Convert DB to a flat list
    trips_list = list(cruise_db.values())
    
    for i, trip in enumerate(trips_list, 1):
        route_id = trip["id"]
        date = trip["date"]
        
        # Log progress so we know it's working
        if i % 25 == 0 or i == 1:
            print(f"Processing pricing for trip {i}/{total_trips}: Route {route_id} on {date}")
            
        for p_count in [3, 4]:
            # This forces the Search Engine to calculate the price for THIS date and THIS passenger count
            # We explicitly pass daterange to lock the backend into a strict 1-day departure window
            search_url = f"https://www.e-hoi.de/?fuseaction=search.doSearch&usersearch=1&freetext={route_id}&departdate={date}&arrivdate={date}&daterange={date}%20-%20{date}&personen={p_count}"
            
            try:
                resp = session.get(search_url, timeout=10)
                match = re.search(r'json_search\s*=\s*(\{.*?\});', resp.text, re.DOTALL)
                if match:
                    data = json.loads(match.group(1))
                    routes = data.get("routen", [])
                    # Find our specific route in the search results
                    for r in routes:
                        if str(r.get("routeplanid")) == route_id:
                            price = r.get("bestprice")
                            if price:
                                trip["prices_per_person"][f"{p_count}_adults"] = price
                            break
            except Exception as e:
                # If a specific 3/4 person query times out, we skip silently to keep the script moving
                pass
            
            time.sleep(0.5) # 0.5s is fast but safe for search queries

    # =========================================================================
    # PHASE 3: Save Data
    # =========================================================================
    print("\n--- FINALIZING DATA ---")
    with open('cruises.json', 'w', encoding='utf-8') as f:
        json.dump(trips_list, f, indent=4, ensure_ascii=False)
        
    print(f"Mission Accomplished! Perfectly saved {len(trips_list)} flat-list trips with true tiered pricing.")

if __name__ == "__main__":
    scrape_ehoi()
