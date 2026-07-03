import requests
import json
import re
import time

def scrape_ehoi():
    # Base URL using the robust fuseaction search, including 1-9 days duration and the Jul-Oct window
    base_url = "https://www.e-hoi.de/?fuseaction=search.doSearch&sort=price-asc&departdate=01.07.2026&arrivdate=31.10.2026&daterange=01.07.2026%20-%2031.10.2026&cruisingareaid=64&reisedauer=1-5&reisedauer=6-9"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "de-DE,de;q=0.9"
    }

    cruise_db = {}
    passenger_counts = [2, 3, 4]
    pages_per_query = 4  # Scrapes up to 4 pages per group size

    session = requests.Session()
    session.headers.update(headers)

    # =================================================================
    # STEP 1: Gather the list of cruises and pricing tiers
    # =================================================================
    for p_count in passenger_counts:
        print(f"\n--- GATHERING CRUISES FOR {p_count} ADULTS ---")
        
        # Initialize session cookie for the specific passenger count
        session.get(f"{base_url}&personen={p_count}")
        time.sleep(1)
        
        for page_num in range(1, pages_per_query + 1):
            url = f"{base_url}&personen={p_count}&page={page_num}"
            print(f"Fetching page {page_num}...")
            
            try:
                response = session.get(url, timeout=15)
                response.encoding = 'utf-8'
                
                match = re.search(r'json_search\s*=\s*(\{.*?\});', response.text, re.DOTALL)
                if not match:
                    break

                data = json.loads(match.group(1))
                raw_routes = data.get("routen", [])
                
                if not raw_routes:
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
    # STEP 2: Force e-hoi's APIs to give us the July - October Dates
    # =================================================================
    print("\n--- EXTRACTING EXACT DATES FROM APIs ---")
    
    for route_id, cruise in cruise_db.items():
        try:
            valid_dates = set()
            
            # Hit the Print Backdoor WITHOUT injecting dates into the URL parameters. 
            # This prevents the "URL Reflection" bug where 01.07.2026 was getting scraped falsely.
            print_url = f"https://www.e-hoi.de/?fuseaction=print_product.showprintproduct&liRoutePlanIDs={route_id}&showArrayInfos=pricematrix"
            print_resp = session.get(print_url, timeout=10)
            
            # REGEX A: Match explicit ranges (e.g. 04.10.2026 - 08.10.2026) to grab ONLY the DEPARTURE date
            for match in re.finditer(r'(\d{2})\.(\d{2})\.(2026)\s*(?:-|bis)\s*\d{2}\.\d{2}\.\d{4}', print_resp.text):
                day, month, year = match.groups()
                if month in ['07', '08', '09', '10']: # strictly Jul, Aug, Sep, Oct
                    valid_dates.add(f"{day}.{month}.{year}")
                    
            # REGEX B: Match range starts with omitted year (e.g. 08.10. - 12.10.2026)
            for match in re.finditer(r'(\d{2})\.(\d{2})\.\s*(?:-|bis)\s*\d{2}\.\d{2}\.(2026)', print_resp.text):
                day, month, year = match.groups()
                if month in ['07', '08', '09', '10']:
                    valid_dates.add(f"{day}.{month}.{year}")

            # REGEX C: Match single standalone dates inside table cells just in case (<td>15.08.2026</td>)
            for match in re.finditer(r'<td>\s*(\d{2})\.(\d{2})\.(2026)\s*</td>', print_resp.text):
                day, month, year = match.groups()
                if month in ['07', '08', '09', '10']:
                    valid_dates.add(f"{day}.{month}.{year}")
            
            cruise["exact_dates"] = sorted(list(valid_dates))
            print(f"Cruise {route_id}: Found {len(valid_dates)} valid dates.")
            
            time.sleep(1) # Be gentle to their servers
            
        except Exception as e:
            print(f"Could not fetch dates for {route_id}: {e}")

    # =================================================================
    # STEP 3: Clean up and Save
    # =================================================================
    
    # CRITICAL: Delete any cruise that STILL has no dates in our specific window
    final_cruise_list = [c for c in cruise_db.values() if len(c["exact_dates"]) > 0]

    with open('cruises.json', 'w', encoding='utf-8') as f:
        json.dump(final_cruise_list, f, indent=4, ensure_ascii=False)
        
    print(f"\nCompleted! Saved {len(final_cruise_list)} perfectly filtered itineraries.")

if __name__ == "__main__":
    scrape_ehoi()
