import requests
import json
import re
import time
from bs4 import BeautifulSoup
from datetime import datetime

def scrape_ehoi():
    print("Starting e-hoi Master Calendar Crawler...")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept-Language": "de-DE,de;q=0.9"
    }

    session = requests.Session()
    session.headers.update(headers)

    cruise_db = {}
    passenger_counts = [2, 3, 4]
    
    # Check 10 pages per group size (up to 100 dates per tier)
    pages_per_query = 10 
    
    for p_count in passenger_counts:
        print(f"\n--- GATHERING CALENDAR DATA FOR {p_count} ADULTS ---")
        
        # Prime the session with the main search URL so e-hoi registers our filters
        setup_url = f"https://www.e-hoi.de/mittelmeer-kreuzfahrten/fahrgebiet-64.html?departdate=08.07.2026&arrivdate=11.10.2026&reisedauer=1-5&reisedauer=6-9&personen={p_count}"
        try:
            session.get(setup_url, timeout=15)
        except Exception:
            pass
        time.sleep(1)

        for page_num in range(1, pages_per_query + 1):
            # The hidden AJAX endpoint that returns the calendar table directly
            ajax_url = f"https://www.e-hoi.de/?fuseaction=mod_kreuzfahrtkalender.showkreuzfahrtkalender&referenceID=64&referenceType=destination&sort=departDate_asc&departdate=08.07.2026&arrivdate=11.10.2026&reisedauer=1-5&reisedauer=6-9&page={page_num}&personen={p_count}"
            
            print(f"Reading Calendar Page {page_num}...")
            
            try:
                response = session.get(ajax_url, timeout=15)
                response.encoding = 'utf-8'
                soup = BeautifulSoup(response.text, 'html.parser')
                
                table = soup.find('table', class_='table')
                if not table:
                    print("No more table rows found. Moving to next group size.")
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
                    date_text = cols[0].get_text(strip=True)
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
                        continue
                    route_id = id_match.group(1)
                    
                    # 3. Extract Price for this specific passenger count
                    price_div = cols[5].find('div', class_=re.compile(r'price'))
                    if not price_div:
                        continue
                    price_em = price_div.find('em')
                    if not price_em:
                        continue
                    price_val_match = re.search(r'(\d+[\.,]?\d*)', price_em.text.replace('.', ''))
                    if not price_val_match:
                        continue
                    price_val = int(price_val_match.group(1))

                    # 4. Extract Ship
                    ship_text = cols[1].get_text(separator=' ', strip=True)
                    ship_match = re.split(r'\(', ship_text)
                    ship_name = ship_match[0].strip() if ship_match else "Unbekannt"
                    
                    # 5. Extract Duration
                    dur_text = cols[2].get_text(strip=True)
                    dur_match = re.search(r'(\d+)', dur_text)
                    duration = int(dur_match.group(1)) if dur_match else 0
                    
                    # 6. Extract Route
                    ports_text = cols[3].get_text(separator=' ', strip=True).replace('\n', ' ')
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
                    
                if valid_rows == 0:
                    break
                    
                time.sleep(1) # Polite delay
                
            except Exception as e:
                print(f"Error on page {page_num}: {e}")
                break

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
        
    print(f"Mission Accomplished! Saved {len(final_list)} unique cruises with perfect dates and tiered pricing.")

if __name__ == "__main__":
    scrape_ehoi()
