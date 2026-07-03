import requests
import json
import re
import time

def scrape_ehoi():
    # The updated URL including duration filters for 1-5 and 6-9 days
    base_url = "https://www.e-hoi.de/mittelmeer-kreuzfahrten/fahrgebiet-64.html?sort=price-asc&departdate=08.07.2026&arrivdate=11.10.2026&daterange=08.07.2026%20-%2011.10.2026&reisedauer=1-5&reisedauer=6-9&filterby=arrivdate"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept-Language": "de-DE,de;q=0.9"
    }

    cruise_db = {}
    passenger_counts = [2, 3, 4]
    pages_per_query = 5  # Increased to 5 pages to grab even more cruises!

    session = requests.Session()
    session.headers.update(headers)

    # =================================================================
    # STEP 1: Gather the list of cruises and pricing tiers
    # =================================================================
    for p_count in passenger_counts:
        print(f"\n--- GATHERING CRUISES FOR {p_count} ADULTS ---")
        
        # Initialize session cookie
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
    # STEP 2: Visit each detail page and hunt for the exact dates
    # =================================================================
    print("\n--- EXTRACTING EXACT DATES FROM DETAIL PAGES ---")
    print("This will take a minute or two as we visit each cruise page...")
    
    for route_id, cruise in cruise_db.items():
        if not cruise["url"]:
            continue

        try:
            detail_resp = session.get(cruise["url"], timeout=15)
            detail_resp.encoding = 'utf-8'
            
            # Aggressively hunt for standard dates like: 14.08.2026
            raw_dates = re.findall(r'(?<!\d)(\d{2}\.\d{2}\.2026)(?!\d)', detail_resp.text)
            
            # Hunt for ranges like "08.10. - 12.10.2026" and grab the start date "08.10.2026"
            range_dates = re.findall(r'(\d{2}\.\d{2}\.)\s*(?:-|bis)\s*\d{2}\.\d{2}\.(2026)', detail_resp.text)
            for dm, yyyy in range_dates:
                raw_dates.append(f"{dm}{yyyy}")
                
            # Clean up and deduplicate the list of dates
            unique_dates = sorted(list(set(raw_dates)))
            cruise["exact_dates"] = unique_dates
            print(f"Cruise {route_id}: Found {len(unique_dates)} dates.")
            
            # Brief pause so we don't get blocked by e-hoi for spamming their server
            time.sleep(1)

        except Exception as e:
            print(f"Failed to fetch dates for {route_id}: {e}")

    # Convert dictionary back to list and save
    final_cruise_list = list(cruise_db.values())

    with open('cruises.json', 'w', encoding='utf-8') as f:
        json.dump(final_cruise_list, f, indent=4, ensure_ascii=False)
        
    print(f"\nCompleted! Successfully saved {len(final_cruise_list)} itineraries.")

if __name__ == "__main__":
    scrape_ehoi()
