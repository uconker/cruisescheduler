import requests
import json
import re
import time

def scrape_ehoi():
    # The exact query URL matching your group preferences
    url = "https://www.e-hoi.de/?fuseaction=search.doSearch&usersearch=1&sort=price-asc&departdate=07.07.2026&arrivdate=07.09.2026&daterange=07.07.2026_20-_2007.09.2026&cruisingareaid=64&reisedauer=6-9&filterby=cruisingareaid"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "de-DE,de;q=0.9"
    }

    print("Fetching live cruise data from e-hoi...")
    response = requests.get(url, headers=headers)
    response.encoding = 'utf-8'
    
    # Use Regex to extract the pure JSON object embedded in the script tag
    match = re.search(r'json_search\s*=\s*(\{.*?\});', response.text)
    
    if not match:
        print("Error: Could not find the embedded data on the page. e-hoi might have changed their script layout.")
        return

    try:
        raw_json_text = match.group(1)
        data = json.loads(raw_json_text)
        
        raw_routes = data.get("routen", [])
        clean_cruises = []
        
        for route in raw_routes:
            # Strip out HTML links from the port list to make it clean text
            clean_ports = re.sub(r'<[^>]*>', '', route.get("porttext", ""))
            clean_ports = " -> ".join([p.strip() for p in clean_ports.split("-") if p.strip()])

            clean_cruises.append({
                "id": route.get("routeplanid"),
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
            
        # Save the structured data back into your repo's cruises.json database
        with open('cruises.json', 'w', encoding='utf-8') as f:
            json.dump(clean_cruises, f, indent=4, ensure_ascii=False)
            
        print(f"Success! Extracted {len(clean_cruises)} cruises and saved to cruises.json")

    except Exception as e:
        print(f"Failed to parse data: {e}")

if __name__ == "__main__":
    scrape_ehoi()
