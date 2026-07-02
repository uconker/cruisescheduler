import requests
import json
import re
import time

def scrape_ehoi():
    base_url = "https://www.e-hoi.de/?fuseaction=search.doSearch&usersearch=1&sort=price-asc&departdate=07.07.2026&arrivdate=07.09.2026&daterange=07.07.2026_20-_2007.09.2026&cruisingareaid=64&reisedauer=6-9&filterby=cruisingareaid"
    
    # Advanced headers to mimic a real desktop browser
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://www.e-hoi.de/"
    }

    cruise_db = {}
    passenger_counts = [2, 3, 4]
    pages_per_query = 4  # Grabs up to 40 unique cruises per occupancy tier

    # Create a persistent session to hold cookies across pagination
    session = requests.Session()
    session.headers.update(headers)

    for p_count in passenger_counts:
        print(f"\n--- SCRAPING FOR {p_count} ADULT OCCUPANCY ---")
        
        # We need to hit the base page first to establish the session cookie for this passenger count
        init_url = f"{base_url}&personen={p_count}"
        session.get(init_url)
        time.sleep(1)
        
        for page_num in range(1, pages_per_query + 1):
            url = f"{init_url}&page={page_num}"
            print(f"Fetching page {page_num}...")
            
            try:
                response = session.get(url, timeout=15)
                response.encoding = 'utf-8'
                
                match = re.search(r'json_search\s*=\s*(\{.*?\});', response.text)
                if not match:
                    print(f"No JSON data found on page {page_num}. Moving to next tier.")
                    break

                data = json.loads(match.group(1))
                raw_routes = data.get("routen", [])
                
                if not raw_routes:
                    print(f"No more routes found on page {page_num}.")
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
                            "departure_month": route.get("departdate_formatted"),
                            "url": route.get("producturl"),
                            "ports": clean_ports,
                            "prices_per_person": {},
                            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")
                        }
                    
                    cruise_db[route_id]["prices_per_person"][f"{p_count}_adults"] = best_price
                    
                time.sleep(2)  # 2-second delay to safely avoid bot-blocking
                
            except Exception as e:
                print(f"Error scraping page {page_num} for {p_count} adults: {e}")
                break

    final_cruise_list = list(cruise_db.values())

    with open('cruises.json', 'w', encoding='utf-8') as f:
        json.dump(final_cruise_list, f, indent=4, ensure_ascii=False)
        
    print(f"\nCompleted! Saved {len(final_cruise_list)} total unique itineraries.")

if __name__ == "__main__":
    scrape_ehoi()
