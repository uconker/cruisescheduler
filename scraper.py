import requests
import json
import re
import time

def scrape_ehoi():
    base_url = "https://www.e-hoi.de/?fuseaction=search.doSearch&usersearch=1&sort=price-asc&departdate=07.07.2026&arrivdate=07.09.2026&daterange=07.07.2026_20-_2007.09.2026&cruisingareaid=64&reisedauer=6-9&filterby=cruisingareaid"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "de-DE,de;q=0.9"
    }

    # Master database dictionary keyed by cruise ID
    cruise_db = {}
    
    # We will test 2, 3, and 4 adult passengers
    passenger_counts = [2, 3, 4]
    pages_per_query = 3  # Scrapes 3 pages per occupancy level (gets up to 30 cheapest options per tier)

    for p_count in passenger_counts:
        print(f"\n--- SCRAPING FOR {p_count} ADULT OCCUPANCY ---")
        
        for page_num in range(1, pages_per_query + 1):
            # Append the passenger occupancy and page count variables to the URL structure
            url = f"{base_url}&personen={p_count}&page={page_num}"
            print(f"Fetching page {page_num}...")
            
            try:
                response = requests.get(url, headers=headers, timeout=15)
                response.encoding = 'utf-8'
                
                match = re.search(r'json_search\s*=\s*(\{.*?\});', response.text)
                if not match:
                    break

                data = json.loads(match.group(1))
                raw_routes = data.get("routen", [])
                
                if not raw_routes:
                    break
                    
                for route in raw_routes:
                    route_id = route.get("routeplanid")
                    best_price = route.get("bestprice")

                    # If we haven't seen this cruise yet, parse its core data structure
                    if route_id not in cruise_db:
                        clean_ports = re.sub(r'<[^>]*>', '', route.get("porttext", ""))
                        clean_ports = " -> ".join([p.strip() for p in clean_ports.split("-") if p.strip()])

                        cruise_db[route_id] = {
                            "id": route_id,
                            "title": route.get("routetitle"),
                            "ship": route.get("ship"),
                            "duration_days": route.get("duration"),
                            "cabin_type": route.get("kabine"),
                            "departure_month": route.get("departdate_formatted"),
                            "url": route.get("producturl"),
                            "ports": clean_ports,
                            "prices_per_person": {},
                            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")
                        }
                    
                    # Log the price to the corresponding dictionary entry key
                    cruise_db[route_id]["prices_per_person"][f"{p_count}_adults"] = best_price
                    
                time.sleep(1.5)  # Respect rate limits between page calls
                
            except Exception as e:
                print(f"Error scaling page {page_num} for {p_count} adults: {e}")
                break

    # Convert our master storage dictionary back to an aligned list layout
    final_cruise_list = list(cruise_db.values())

    # Save to your local JSON repository tracker
    with open('cruises.json', 'w', encoding='utf-8') as f:
        json.dump(final_cruise_list, f, indent=4, ensure_ascii=False)
        
    print(f"\nCompleted! Generated data for {len(final_cruise_list)} total unique itineraries.")

if __name__ == "__main__":
    scrape_ehoi()
