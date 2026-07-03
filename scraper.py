import requests
import json
import re
import time

def scrape_ehoi():
    # The exact URL you provided, formatted for the scraper
    base_url = "https://www.e-hoi.de/mittelmeer-kreuzfahrten/fahrgebiet-64.html?sort=price-asc&departdate=08.07.2026&arrivdate=11.10.2026&daterange=08.07.2026%20-%2011.10.2026&reisedauer=1-5&reisedauer=6-9&filterby=arrivdate"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7"
    }

    cruise_db = {}
    passenger_counts = [2, 3, 4]
    pages_per_query = 4 # Scrape up to 4 pages per group size

    session = requests.Session()
    session.headers.update(headers)

    for p_count in passenger_counts:
        print(f"\n--- FINDING CRUISES FOR {p_count} ADULT OCCUPANCY ---")
        
        # Initialize the session cookie for this specific group size
        init_url = f"{base_url}&personen={p_count}"
        session.get(init_url)
        time.sleep(1)
        
        for page_num in range(1, pages_per_query + 1):
            url = f"{init_url}&page={page_num}"
            print(f"Fetching page {page_num}...")
            
            try:
                response = session.get(url, timeout=15)
                response.encoding = 'utf-8'
                
                # Extract the hidden data layer from the raw HTML
                match = re.search(r'json_search\s*=\s*(\{.*?\});', response.text, re.DOTALL)
                if not match:
                    print(f"End of data reached on page {page_num}.")
                    break

                try:
                    data = json.loads(match.group(1))
                except json.JSONDecodeError:
                    print(f"Failed to read data format on page {page_num}.")
                    break

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

                        # --- THE AGGRESSIVE DATE EXTRACTOR ---
                        # Convert the entire route object to a string to hunt for dates
                        route_str = json.dumps(route)
                        found_dates = set()

                        # 1. Find standard exact dates: 08.10.2026
                        dates_dmy = re.findall(r'(?<!\d)(\d{2}\.\d{2}\.\d{4})(?!\d)', route_str)
                        found_dates.update(dates_dmy)

                        # 2. Find internal system dates: 2026-10-08 -> Convert to 08.10.2026
                        dates_ymd = re.findall(r'(?<!\d)(\d{4}-\d{2}-\d{2})(?!\d)', route_str)
                        for ymd in dates_ymd:
                            parts = ymd.split('-')
                            if len(parts) == 3:
                                found_dates.add(f"{parts[2]}.{parts[1]}.{parts[0]}")

                        # 3. Find ranges from your screenshot: "08.10. - 12.10.2026" -> Extract "08.10.2026"
                        pairs = re.findall(r'(\d{2}\.\d{2}\.)\s*(?:-|bis)\s*\d{2}\.\d{2}\.(\d{4})', route_str)
                        for dm, yyyy in pairs:
                            found_dates.add(f"{dm}{yyyy}")

                        # Filter out bad dates (must contain 2026 based on your search)
                        valid_dates = [d for d in found_dates if "2026" in d]

                        cruise_db[route_id] = {
                            "id": route_id,
                            "title": route.get("routetitle", "Unbekannte Route"),
                            "ship": route.get("ship", "Unbekanntes Schiff"),
                            "duration_days": route.get("duration", ""),
                            "cabin_type": route.get("kabine", ""),
                            "url": route.get("producturl", f"https://www.e-hoi.de/kreuzfahrt/{route_id}"),
                            "ports": clean_ports,
                            "prices_per_person": {},
                            "exact_dates": sorted(valid_dates),
                            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")
                        }
                    
                    # Update pricing tier for the group size
                    if best_price:
                        cruise_db[route_id]["prices_per_person"][f"{p_count}_adults"] = best_price
                    
                time.sleep(1.5) 
                
            except Exception as e:
                print(f"Error scraping page {page_num}: {e}")
                break

    final_cruise_list = list(cruise_db.values())

    with open('cruises.json', 'w', encoding='utf-8') as f:
        json.dump(final_cruise_list, f, indent=4, ensure_ascii=False)
        
    print(f"\nCompleted! Saved {len(final_cruise_list)} unique itineraries with exact dates.")

if __name__ == "__main__":
    scrape_ehoi()
