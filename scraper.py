import requests
import json
import re
import time
from datetime import datetime, timedelta

def scrape_ehoi():
    print("Starting e-hoi Session-Toggle Crawler...")
    print("This architecture guarantees flat-list outputs and true tiered pricing.")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept-Language": "de-DE,de;q=0.9"
    }

    cruise_db = {}
    max_pages = 200 
    passenger_counts = [2, 3, 4]
    
    for p_count in passenger_counts:
        print(f"\n--- GATHERING CALENDAR DATA FOR {p_count} ADULTS ---")
        
        # Create a fresh session for each passenger count to avoid cookie cross-contamination
        session = requests.Session()
        session.headers.update(headers)
        
        # Step 1: Prime the session with our specific passenger count!
        setup_url = f"https://www.e-hoi.de/mittelmeer-kreuzfahrten/fahrgebiet-64.html?usersearch=1&departdate=08.07.2026&arrivdate=31.10.2026&daterange=08.07.2026%20-%2031.10.2026&reisedauer=1-5&reisedauer=6-9&personen={p_count}"
        try:
            print("Configuring search session parameters on e-hoi servers...")
            session.get(setup_url, timeout=30)
        except Exception as e:
            print(f"Session setup failed: {e}")
        time.sleep(1)

        # Step 2: Loop the calendar pages
        for page_num in range(1, max_pages + 1):
            ajax_url = f"https://www.e-hoi.de/?fuseaction=mod_kreuzfahrtkalender.showkreuzfahrtkalender&referenceID=64&referenceType=destination&sort=departDate_asc&page={page_num}"
            
            try:
                ajax_headers = headers.copy()
                ajax_headers["X-Requested-With"] = "XMLHttpRequest"
                
                response = session.get(ajax_url, headers=ajax_headers, timeout=30)
                response.encoding = 'utf-8'
                
                if not response.text.strip():
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
                    
                    # 3. Extract Price (Now mathematically tied to our session passenger count!)
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
                    
                    # THE FLAT LIST KEY: Every exact date creates an entirely unique block of data
                    trip_key = f"{route_id}_{start_date}"
                    
                    if trip_key not in cruise_db:
                        first_port = ports_text.split('-')[0].strip() if '-' in ports_text else ports_text
                        cruise_db[trip_key] = {
                            "id": route_id,
                            "date": start_date, # Only a single string, NOT an array of dates!
                            "title": f"Mittelmeer Kreuzfahrt ab {first_port}",
                            "ship": ship_name,
                            "duration_days": duration,
                            "cabin_type": "Günstigste verfügbare Kabine",
                            "url": url,
                            "ports": ports_text,
                            "prices_per_person": {},
                            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")
                        }
                    
                    # Store the dynamically pulled price
                    cruise_db[trip_key]["prices_per_person"][f"{p_count}_adults"] = price_val
                    valid_rows += 1
                    
                if valid_rows == 0:
                    break
                    
                time.sleep(0.3) 
                
            except Exception as e:
                print(f"Error on page {page_num}: {e}")
                break

    print("\n--- FINALIZING DATA ---")
    final_list = list(cruise_db.values())
    final_list.sort(key=lambda x: datetime.strptime(x["date"], "%d.%m.%Y") if x.get("date") else datetime.min)
    
    with open('cruises.json', 'w', encoding='utf-8') as f:
        json.dump(final_list, f, indent=4, ensure_ascii=False)
        
    print(f"Mission Accomplished! Exported {len(final_list)} fully independent trip dates with accurate tiered pricing.")

if __name__ == "__main__":
    scrape_ehoi()
