import requests
import json
import re
import time
from bs4 import BeautifulSoup
from datetime import datetime

def scrape_ehoi():
    print("Starting e-hoi Unbounded Master Calendar Crawler...")
    print("This script will scrape ALL available pages to build the complete database.")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept-Language": "de-DE,de;q=0.9"
    }

    session = requests.Session()
    session.headers.update(headers)

    cruise_db = {}
    passenger_counts = [2, 3, 4]
    
    # We use a high safety limit, but the script will naturally break when it hits the last page
    max_pages = 3000 
    
    for p_count in passenger_counts:
        print(f"\n--- GATHERING ALL CALENDAR DATA FOR {p_count} ADULTS ---")
        
        # Prime the session with the main search URL and your specific date/duration filters
        setup_url = f"https://www.e-hoi.de/mittelmeer-kreuzfahrten/fahrgebiet-64.html?usersearch=1&departdate=08.07.2026&arrivdate=11.10.2026&daterange=08.07.2026%20-%2011.10.2026&reisedauer=1-5&reisedauer=6-9&personen={p_count}"
        
        try:
            print("Configuring search session parameters...")
            session.get(setup_url, timeout=15)
        except Exception as e:
            print(f"Session setup failed: {e}")
        time.sleep(1)

        page_num = 1
        total_rows_extracted = 0

        while page_num <= max_pages:
            # The hidden AJAX endpoint
            ajax_url = f"https://www.e-hoi.de/?fuseaction=mod_kreuzfahrtkalender.showkreuzfahrtkalender&referenceID=64&referenceType=destination&sort=departDate_asc&page={page_num}"
            
            # Log every 50 pages to keep the GitHub Action logs clean
            if page_num % 50 == 1 or page_num == 1:
                print(f"Reading Calendar Pages {page_num} to {page_num+49}...")
            
            try:
                # Add the XMLHttpRequest header so the server thinks it's a real background form submission
                ajax_headers = headers.copy()
                ajax_headers["X-Requested-With"] = "XMLHttpRequest"
                
                response = session.get(ajax_url, headers=ajax_headers, timeout=15)
                response.encoding = 'utf-8'
                
                if not response.text.strip():
                    print(f"Warning: Received empty response on page {page_num}. Moving to next group size.")
                    break

                soup = BeautifulSoup(response.text, 'html.parser')
                
                table = soup.find('table', class_='table')
                if not table:
                    print(f"No table found on page {page_num}. Ending pagination.")
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
                        
                    # 1. Extract Exact Date (removing mobile CSS labels if present)
                    date_text = cols[0].get_text(strip=True).replace('Termin:', '')
                    date_match = re.search(r'(\d{2}\.\d{2}\.\d{4})', date_text)
                    if not date_match:
                        continue
                    start_date = date_match.group(1)
                    
                    # 2. Extract Link & ID
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
                    
                    # 3. Extract Price for this specific passenger count
                    price_em = cols[5].find('em')
                    if price_em:
                        price_text = price_em.text
                    else:
                        price_text = cols[5].get_text()
                        
                    price_val_match = re.search(r'(\d+[\.,]?\d*)', price_text.replace('.', ''))
                    if not price_val_match:
                        continue
                    price_val = int(price_val_match.group(1).replace('.', ''))

                    # 4. Extract Ship (removing mobile CSS labels)
                    ship_text = cols[1].get_text(separator=' ', strip=True).replace('Schiff:', '').strip()
                    ship_name = ship_text.split('(')[0].strip() if '(' in ship_text else ship_text
                    
                    # 5. Extract Duration
                    dur_text = cols[2].get_text(strip=True).replace('Dauer:', '')
                    dur_match = re.search(r'(\d+)', dur_text)
                    duration = int(dur_match.group(1)) if dur_match else 0
                    
                    # 6. Extract Route (removing mobile CSS labels)
                    ports_text = cols[3].get_text(separator=' ', strip=True).replace('\n', ' ')
                    ports_text = ports_text.replace('Route:', '').strip()
                    ports_text = re.sub(r'\s+', ' ', ports_text)
                    
                    # Build Record
                    if route_id not in cruise_db:
                        first_port = ports_text.split('-')[0].strip() if '-' in ports_text else ports_text
                        cruise_db[route_id] = {
                            "id": route_id,
                            "title": f"Mittelmeer Kreuzfahrt ab {first_port}",
                            "ship": ship_name,
                            "duration_days": duration,
                            "cabin_type": "Innenkabine", 
                            "url": url,
                            "ports": ports_text,
                            "prices_per_person": {},
                            "exact_dates": set(),
                            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")
                        }
                        
                    cruise_db[route_id]["exact_dates"].add(start_date)
                    
                    # Save lowest price found for this occupancy tier
                    current_min = cruise_db[route_id]["prices_per_person"].get(f"{p_count}_adults", float('inf'))
                    if price_val < current_min:
                        cruise_db[route_id]["prices_per_person"][f"{p_count}_adults"] = price_val
                        
                    valid_rows += 1
                    total_rows_extracted += valid_rows
                    
                if valid_rows == 0:
                    print(f"Empty table on page {page_num}. Ending pagination for {p_count} adults.")
                    break
                    
                page_num += 1
                time.sleep(0.1) # Fast scraping mode to get through 900+ pages quickly
                
            except Exception as e:
                print(f"Error on page {page_num}: {e}")
                break

        print(f"Finished extracting {total_rows_extracted} total dates for {p_count} adults.")

    print("\n--- FINALIZING DATA ---")
    final_list = []
    for cruise in cruise_db.values():
        try:
            # Sort the scraped dates cleanly
            cruise["exact_dates"] = sorted(list(cruise["exact_dates"]), key=lambda d: datetime.strptime(d, "%d.%m.%Y"))
        except:
            cruise["exact_dates"] = sorted(list(cruise["exact_dates"]))
        final_list.append(cruise)
    
    with open('cruises.json', 'w', encoding='utf-8') as f:
        json.dump(final_list, f, indent=4, ensure_ascii=False)
        
    print(f"Mission Accomplished! Saved {len(final_list)} unique cruises spanning all available dates.")

if __name__ == "__main__":
    scrape_ehoi()
