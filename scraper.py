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

    all_clean_cruises = []
    seen_ids = set()
    
    # We will grab the first 5 pages of results to expand our list
    pages_to_scrape = 5

    for page_num in range(1, pages_to_scrape + 1):
        url = f"{base_url}&page={page_num}"
        print(f"Fetching page {page_num} of live cruise data...")
        
        try:
            response = requests.get(url, headers=headers, timeout=15)
            response.encoding = 'utf-8'
            
            # Extract the json_search block from this specific page
            match = re.search(r'json_search\s*=\s*(\{.*?\});', response.text)
            
            if not match:
                print(f"Could not find data on page {page_num}. Stopping.")
                break

            data = json.loads(match.group(1))
            raw_routes = data.get("routen", [])
            
            if not raw_routes:
                print(f"No more cruises found on page {page_num}. Stopping.")
                break
                
            for route in raw_routes:
                route_id = route.get("routeplanid")
                
                # Prevent adding duplicate cruises if e-hoi overlaps results
                if route_id in seen_ids:
                    continue
                seen_ids.add(route_id)

                # Clean up the port text string
                clean_ports = re.sub(r'<[^>]*>', '', route.get("porttext", ""))
                clean_ports = " -> ".join([p.strip() for p in clean_ports.split("-") if p.strip()])

                all_clean_cruises.append({
                    "id": route_id,
                    "title": route.get("routetitle"),
                    "ship": route.get("ship"),
                    "duration_days": route.get("duration"),
                    "price_eur": route.get("bestprice"),
                    "cabin_type": route.get("kabine"),
                    "departure_month": route.get("departdate_formatted"),
                    "url": route.get("producturl"),
                    "ports": clean_ports,
                    "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")
                })
                
            # Pause briefly to be polite to the e-hoi servers
            time.sleep(1.5)
            
        except Exception as e:
            print(f"Error scraping page {page_num}: {e}")
            break
            
    # Save our newly expanded list back into cruises.json
    with open('cruises.json', 'w', encoding='utf-8') as f:
        json.dump(all_clean_cruises, f, indent=4, ensure_ascii=False)
        
    print(f"Success! Extracted a total of {len(all_clean_cruises)} unique cruises across pages.")

if __name__ == "__main__":
    scrape_ehoi()
