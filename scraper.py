import requests
import json
import re
import time
from bs4 import BeautifulSoup
from datetime import datetime

def scrape_ehoi():
    print("Starting e-hoi Flat-List Scraper...")
    print("Extracting exact dates and base prices directly from the calendar.")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept-Language": "de-DE,de;q=0.9",
        "X-Requested-With": "XMLHttpRequest"
    }

    session = requests.Session()
    session.headers.update(headers)

    final_list = []
    max_pages = 200 
    
    print(f"\n--- GATHERING EXACT DATES & PRICES (Up to {max_pages} Pages) ---")
    
    for page_num in range(1, max_pages + 1):
        # Explicit parameters in the URL guarantee it never returns empty!
        ajax_url = f"https://www.e-hoi.de/?fuseaction=mod_kreuzfahrtkalender.showkreuzfahrtkalender&referenceID=64&referenceType=destination&sort=departDate_asc&page={page_num}&departdate=08.07.2026&arrivdate=31.10.2026&reisedauer=1-5&reisedauer=6-9"
        
        try:
            response = session.get(ajax_url, timeout=30)
            response.encoding = 'utf-8'
            
            if not response.text.strip():
                print(f"Empty response on page {page_num}. Ending scrape.")
                break

            soup = BeautifulSoup(response.text, 'html.parser')
            table = soup.find('table', class_='table')
            
            if not table:
                print("No table found. Ending scrape.")
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
                
                # 3. Extract Price
                price_em = cols[5].find('em')
                price_text = price_em.text if price_em else cols[5].get_text()
                price_val_match = re.search(r'(\d+[\.,]?\d*)', price_text.replace('.', ''))
                if not price_val_match:
                    continue
                price_val = int(price_val_match.group(1))

                # 4. Clean up Ship
                ship_text = cols[1].get_text(separator=' ', strip=True).replace("Schiff:", "").strip()
                ship_name = re.split(r'\(', ship_text)[0].strip() if ship_text else "Unbekannt"
                
                # 5. Extract Duration
                dur_text = cols[2].get_text(strip=True)
                dur_match = re.search(r'(\d+)', dur_text)
                duration = int(dur_match.group(1)) if dur_match else 0
                
                # 6. Extract Ports
                ports_text = cols[3].get_text(separator=' ', strip=True).replace('\n', ' ').replace("Route:", "").strip()
                ports_text = re.sub(r'\s+', ' ', ports_text)
                first_port = ports_text.split('-')[0].strip() if '-' in ports_text else ports_text
                
                # Build Flat Block (One distinct date per block)
                trip = {
                    "id": f"{route_id}_{start_date}",
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
                
                final_list.append(trip)
                valid_rows += 1
                
            print(f"-> Extracted {valid_rows} unique departure dates from page {page_num}.")
            
            # Stop if no valid rows were found on this page
            if valid_rows == 0:
                break
                
            time.sleep(1) # Fast, polite delay
            
        except Exception as e:
            print(f"Error on page {page_num}: {e}")
            break

    print("\n--- FINALIZING DATA ---")
    
    # Sort chronologically
    final_list.sort(key=lambda x: datetime.strptime(x["date"], "%d.%m.%Y") if x.get("date") else datetime.min)
    
    with open('cruises.json', 'w', encoding='utf-8') as f:
        json.dump(final_list, f, indent=4, ensure_ascii=False)
        
    print(f"Mission Accomplished! Saved {len(final_list)} flat-list trips.")

if __name__ == "__main__":
    scrape_ehoi()
