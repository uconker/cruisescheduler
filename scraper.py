import requests
import json
import re
import time

def scrape_ehoi():
    # The base URL WITHOUT usersearch=1 so that pagination works correctly
    base_url = "https://www.e-hoi.de/?fuseaction=search.doSearch&sort=price-asc&departdate=07.07.2026&arrivdate=07.09.2026&daterange=07.07.2026_20-_2007.09.2026&cruisingareaid=64&reisedauer=6-9&filterby=cruisingareaid"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7"
    }

    cruise_db = {}
    passenger_counts = [2, 3, 4]
    pages_per_query = 3

    # Use a session to maintain cookies
    session = requests.Session()
    session.headers.update(headers)

    for p_count in passenger_counts:
        print(f"\n--- FINDING CRUISES FOR {p_count} ADULT OCCUPANCY ---")
        
        for page_num in range(1, pages_per_query + 1):
            # Append the current page and passenger count to the clean base URL
            url = f"{base_url}&personen={p_count}&page={page_num}"
            print(f"Fetching page {page_num}...")
            
            try:
                response = session.get(url, timeout=15)
                response.encoding = 'utf-8'
                
                # Extract the JSON embedded in the script tag
                match = re.search(r'json_search\s*=\s*(\{.*?\});', response.text)
                if not match:
                    print(f"Could not find json_search on page {page_num}")
                    break

                data = json.loads(match.group(1))
                raw_routes = data.get("routen", [])
                
                if not raw_routes:
                    print(f"No routes found on page {page_num}")
                    break
                    
                for route in raw_routes:
                    route_id = route.get("routeplanid")
                    best_price = route.get("bestprice")

                    if route_id not in cruise_db:
                        clean_ports = re.sub(r'<[^>]*>', '', route.get("porttext", ""))
                        clean_ports = " -> ".join([p.strip() for p in clean_ports.split("-") if p.strip()])

                        cruise_db[route_id] = {
                            "id": route_id,
                            "title": route.get("routetitle"),
                            "ship": route.get("ship"),
                            "duration_days": route.get("duration"),
                            "cabin_type": route.get("kabine"),
                            "url": route.get("producturl"),
                            "ports": clean_ports,
                            "prices_per_person": {},
                            "exact_dates": [], 
                            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")
                        }
                    
                    cruise_db[route_id]["prices_per_person"][f"{p_count}_adults"] = best_price
                    
                # Small pause to be polite
                time.sleep(1.5) 
                
            except Exception as e:
                print(f"Error scraping page {page_num}: {e}")
                break

    print("\n--- FETCHING EXACT DEPARTURE DATES ---")
    
    for route_id, cruise_data in cruise_db.items():
        try:
            # The endpoint e-hoi uses to show the date slider
            dates_url = f"https://www.e-hoi.de/?fuseaction=search.showTrips&routeplanid={route_id}"
            dates_resp = session.get(dates_url, timeout=10)
            
            # Find all strings that look like dates (dd.mm.yyyy)
            found_dates = set(re.findall(r'\d{2}\.\d{2}\.\d{4}', dates_resp.text))
            
            cruise_db[route_id]["exact_dates"] = sorted(list(found_dates))
            print(f"Found {len(found_dates)} exact dates for Cruise {route_id}")
            
            time.sleep(1)
            
        except Exception as e:
            print(f"Could not fetch dates for {route_id}: {e}")

    final_cruise_list = list(cruise_db.values())

    with open('cruises.json', 'w', encoding='utf-8') as f:
        json.dump(final_cruise_list, f, indent=4, ensure_ascii=False)
        
    print(f"\nCompleted! Saved {len(final_cruise_list)} unique itineraries with exact dates.")

if __name__ == "__main__":
    scrape_ehoi()
