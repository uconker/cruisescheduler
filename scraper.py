import requests
import json
import re
import time

def scrape_ehoi():
    # The base URL including duration filters for 1-5 and 6-9 days
    base_url = "https://www.e-hoi.de/mittelmeer-kreuzfahrten/fahrgebiet-64.html?sort=price-asc&departdate=08.07.2026&arrivdate=11.10.2026&daterange=08.07.2026%20-%2011.10.2026&reisedauer=1-5&reisedauer=6-9&filterby=arrivdate"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7"
    }

    cruise_db = {}
    passenger_counts = [2, 3, 4]
    pages_per_query = 5  # Scrape up to 5 pages per group size to ensure we get plenty of data

    session = requests.Session()
    session.headers.update(headers)

    # =================================================================
    # STEP 1: Gather the list of cruises and pricing tiers
    # =================================================================
    for p_count in passenger_counts:
        print(f"\n--- GATHERING CRUISES FOR {p_count} ADULTS ---")
        
        # Initialize session cookie
        init_url = f"{base_url}&personen={p_count}"
        session.get(init_url)
        time.sleep(1)
        
        for page_num in range(1, pages_per_query + 1):
            url = f"{init_url}&page={page_num}"
            print(f"Fetching page {page_num}...")
            
            try:
                response = session.get(url, timeout=15)
                response.encoding = 'utf-8'
                
                match = re.search(r'json_search\s*=\s*(\{.*?\});', response.text, re.DOTALL)
                if not match:
                    print(f"End of data reached or could not find json_search on page {page_num}.")
                    break

                data = json.loads(match.group(1))
                raw_routes = data.get("routen", [])
                
                if not raw_routes:
                    print(f"No routes found on page {page_num}.")
                    break
                    
                for route in raw_routes:
                    route_id = str(route.get("routeplanid", ""))
                    best_price = route.get("bestprice")

                    if not route_id:
                        continue

                    if route_id not in cruise_db:
                        clean_ports = re.sub(r'<[^>]*>', '', route.get("porttext", ""))
                        clean_ports = " -> ".join([p.strip() for p in clean_ports.split("-") if p.strip()])
                        
                        cruise_url = route.get("producturl", "")
                        if cruise_url.startswith("/"):
                            cruise_url = "https://www.e-hoi.de" + cruise_url

                        cruise_db[route_id] = {
                            "id": route_id,
                            "title": route.get("routetitle", ""),
                            "ship": route.get("ship", ""),
                            "duration_days": route.get("duration", ""),
                            "cabin_type": route.get("kabine", ""),
                            "url": cruise_url,
                            "ports": clean_ports,
                            "prices_per_person": {},
                            "exact_dates": [],
                            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")
                        }
                    
                    if best_price:
                        cruise_db[route_id]["prices_per_person"][f"{p_count}_adults"] = best_price
                    
                time.sleep(1.5) 
                
            except Exception as e:
                print(f"Error scraping page {page_num}: {e}")
                break

    # =================================================================
    # STEP 2: Use the Print Backdoor to get exact dates!
    # =================================================================
    print("\n--- EXTRACTING EXACT DATES VIA PRINT BACKDOOR ---")
    
    for route_id, cruise in cruise_db.items():
        try:
            # The incredible print backdoor URL you found!
            print_url = f"https://www.e-hoi.de/?fuseaction=print_product.showprintproduct&liRoutePlanIDs={route_id}&showArrayInfos=pricematrix"
            print_resp = session.get(print_url, timeout=10)
            print_resp.encoding = 'utf-8'
            
            # Extract all dates matching DD.MM.YYYY from the raw print HTML
            raw_dates = set(re.findall(r'(?<!\d)(\d{2}\.\d{2}\.\d{4})(?!\d)', print_resp.text))
            
            # Filter strictly for July, August, September, and October 2026
            valid_dates = set()
            for d in raw_dates:
                if d.endswith(('.07.2026', '.08.2026', '.09.2026', '.10.2026')):
                    valid_dates.add(d)
            
            cruise["exact_dates"] = sorted(list(valid_dates))
            print(f"Cruise {route_id}: Found {len(valid_dates)} valid dates.")
            
            time.sleep(1) # Be gentle to their servers
            
        except Exception as e:
            print(f"Could not fetch dates for {route_id}: {e}")

    # Convert dictionary back to list, KEEPING ONLY those with valid dates!
    final_cruise_list = [c for c in cruise_db.values() if len(c["exact_dates"]) > 0]

    with open('cruises.json', 'w', encoding='utf-8') as f:
        json.dump(final_cruise_list, f, indent=4, ensure_ascii=False)
        
    print(f"\nCompleted! Saved {len(final_cruise_list)} unique itineraries with exact dates.")

if __name__ == "__main__":
    scrape_ehoi()
