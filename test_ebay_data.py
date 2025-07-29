#!/usr/bin/env python3

import requests
import csv
import json
import os
import base64
from dotenv import load_dotenv
from typing import Dict, List, Optional

# Load environment variables
load_dotenv()

class EbayTestRunner:
    def __init__(self):
        self.ebay_client_id = os.getenv('EBAY_CLIENT_ID')
        self.ebay_client_secret = os.getenv('EBAY_CLIENT_SECRET')
        self.ebay_environment = os.getenv('EBAY_ENVIRONMENT', 'PRODUCTION')
        self.ebay_access_token = None
        self.parts_list = []
        self.load_parts_list()
    
    def load_parts_list(self):
        try:
            with open('category_mapping.csv', 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    if row['search_query'] and row['category_id']:
                        self.parts_list.append({
                            'search_query': row['search_query'],
                            'category_id': row['category_id'],
                            'min_price': float(row.get('min_price', 0))
                        })
        except FileNotFoundError:
            print("category_mapping.csv not found!")
            return
    
    def decode_vin(self, vin: str) -> Optional[Dict]:
        url = f"https://vpic.nhtsa.dot.gov/api/vehicles/decodevin/{vin}?format=json"
        
        try:
            print(f"Decoding VIN: {vin}")
            response = requests.get(url, timeout=20)
            response.raise_for_status()
            
            data = response.json()
            if data.get('Results'):
                vehicle_info = {}
                for result in data['Results']:
                    if result['Variable'] == 'Make':
                        vehicle_info['make'] = result['Value']
                    elif result['Variable'] == 'Model':
                        vehicle_info['model'] = result['Value']
                    elif result['Variable'] == 'Model Year':
                        vehicle_info['year'] = result['Value']
                
                if all(v for v in vehicle_info.values()):
                    print(f"Vehicle: {vehicle_info['year']} {vehicle_info['make']} {vehicle_info['model']}")
                    return vehicle_info
                        
        except Exception as e:
            print(f"VIN decode error: {str(e)}")
            return None
    
    def get_ebay_access_token(self) -> bool:
        if not self.ebay_client_id or not self.ebay_client_secret:
            print("ERROR: eBay credentials not found in .env file")
            return False
        
        try:
            if self.ebay_environment == 'PRODUCTION':
                oauth_url = "https://api.ebay.com/identity/v1/oauth2/token"
            else:
                oauth_url = "https://api.sandbox.ebay.com/identity/v1/oauth2/token"
            
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Authorization': f'Basic {self._encode_credentials()}'
            }
            
            data = {
                'grant_type': 'client_credentials',
                'scope': 'https://api.ebay.com/oauth/api_scope'
            }
            
            response = requests.post(oauth_url, headers=headers, data=data, timeout=10)
            response.raise_for_status()
            
            token_data = response.json()
            self.ebay_access_token = token_data.get('access_token')
            
            if self.ebay_access_token:
                print("eBay authentication successful!")
                return True
            else:
                print("ERROR: No access token in response")
                return False
                
        except Exception as e:
            print(f"ERROR: Failed to get eBay access token: {str(e)}")
            return False
    
    def _encode_credentials(self) -> str:
        credentials = f"{self.ebay_client_id}:{self.ebay_client_secret}"
        return base64.b64encode(credentials.encode()).decode()
    
    def search_ebay_part(self, vehicle_info: Dict, part: Dict) -> List[Dict]:
        if not self.ebay_access_token and not self.get_ebay_access_token():
            return []
        
        # eBay Browse API endpoint
        if self.ebay_environment == 'PRODUCTION':
            search_url = "https://api.ebay.com/buy/browse/v1/item_summary/search"
        else:
            search_url = "https://api.sandbox.ebay.com/buy/browse/v1/item_summary/search"
        
        headers = {
            'Authorization': f'Bearer {self.ebay_access_token}',
            'Content-Type': 'application/json'
        }
        
        try:
            # Build search query with vehicle info
            search_query = f"{vehicle_info['year']} {vehicle_info['make']} {vehicle_info['model']} {part['search_query']}"
            
            # Add minimum price filter to exclude small accessories
            price_filter = f"price:[{part['min_price']}..]" if part['min_price'] > 0 else ""
            condition_filter = "conditionIds:{3000}"  # Used only
            buying_filter = "buyingOptions:{FIXED_PRICE}"
            
            # Combine filters with proper syntax
            filters = [condition_filter, buying_filter]
            if price_filter:
                filters.append(price_filter)
            
            params = {
                'q': search_query,
                'category_ids': part['category_id'],
                'filter': ','.join(filters),
                'sort': 'price',
                'limit': '200'
            }
            
            print(f"\nSearching: {search_query}")
            print(f"Category: {part['category_id']}, Min Price: ${part['min_price']}")
            
            response = requests.get(search_url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            items = []
            
            if 'itemSummaries' in data:
                for item in data['itemSummaries']:
                    if 'price' in item and 'value' in item['price']:
                        try:
                            price = float(item['price']['value'])
                            
                            # Add shipping cost if present
                            shipping_cost = 0.0
                            if 'shippingOptions' in item and item['shippingOptions']:
                                shipping_option = item['shippingOptions'][0]  # Take first shipping option
                                if 'shippingCost' in shipping_option and 'value' in shipping_option['shippingCost']:
                                    shipping_cost = float(shipping_option['shippingCost']['value'])
                            
                            total_price = price + shipping_cost
                            min_price = part.get('min_price', 10)
                            
                            if min_price <= total_price <= 5000:
                                items.append({
                                    'title': item.get('title', 'No title'),
                                    'price': price,
                                    'shipping': shipping_cost,
                                    'total_price': total_price,
                                    'itemId': item.get('itemId', ''),
                                    'condition': item.get('condition', ''),
                                    'location': item.get('itemLocation', {}).get('country', '')
                                })
                        except (ValueError, TypeError):
                            continue
            
            print(f"Found {len(items)} valid items")
            return items
            
        except Exception as e:
            print(f"ERROR: eBay search error for {part['search_query']}: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response status: {e.response.status_code}")
                print(f"Response text: {e.response.text[:500]}")
            return []
    
    def run_test(self, vin: str, part_name: str):
        print("="*60)
        print(f"EBAY DATA TEST - VIN: {vin}, PART: {part_name}")
        print("="*60)
        
        # Decode VIN
        vehicle_info = self.decode_vin(vin)
        if not vehicle_info:
            print("Failed to decode VIN. Exiting.")
            return
        
        # Find the part in our list
        target_part = None
        for part in self.parts_list:
            if part['search_query'].lower() == part_name.lower():
                target_part = part
                break
        
        if not target_part:
            print(f"Part '{part_name}' not found in parts_list.csv")
            print("Available parts:", [p['search_query'] for p in self.parts_list])
            return
        
        # Search eBay for this part
        items = self.search_ebay_part(vehicle_info, target_part)
        
        if not items:
            print("No items found!")
            return
        
        # Display results
        print(f"\n{'#':<3} {'Price':<10} {'Ship':<8} {'Total':<10} {'Title':<60}")
        print("-" * 95)
        
        for i, item in enumerate(items, 1):
            title_truncated = item['title'][:57] + "..." if len(item['title']) > 60 else item['title']
            shipping_display = f"${item['shipping']:.2f}" if item['shipping'] > 0 else "FREE"
            print(f"{i:<3} ${item['price']:<9.2f} {shipping_display:<8} ${item['total_price']:<9.2f} {title_truncated}")
        
        # Basic statistics using total price (price + shipping)
        total_prices = [item['total_price'] for item in items]
        total_prices.sort()
        
        print(f"\n=== PRICE STATISTICS (INCLUDING SHIPPING) ===")
        print(f"Total items: {len(total_prices)}")
        print(f"Total price range: ${min(total_prices):.2f} - ${max(total_prices):.2f}")
        print(f"Median total: ${total_prices[len(total_prices)//2]:.2f}")
        print(f"Average total: ${sum(total_prices)/len(total_prices):.2f}")
        
        # Show shipping statistics
        shipping_costs = [item['shipping'] for item in items if item['shipping'] > 0]
        free_shipping_count = len([item for item in items if item['shipping'] == 0])
        
        print(f"\n=== SHIPPING STATISTICS ===")
        print(f"Free shipping items: {free_shipping_count}/{len(items)}")
        if shipping_costs:
            print(f"Avg shipping cost: ${sum(shipping_costs)/len(shipping_costs):.2f}")
            print(f"Shipping range: ${min(shipping_costs):.2f} - ${max(shipping_costs):.2f}")
        
        # Export to CSV for your analysis
        filename = f"ebay_data_{part_name}_{vin[-6:]}.csv"
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['Index', 'Price', 'Shipping', 'Total_Price', 'Title', 'ItemID', 'Condition'])
            for i, item in enumerate(items, 1):
                writer.writerow([i, item['price'], item['shipping'], item['total_price'], item['title'], item['itemId'], item['condition']])
        
        print(f"\nData exported to: {filename}")
        print("You can now analyze this data with your own statistical models!")

def main():
    runner = EbayTestRunner()
    
    # Example usage
    print("eBay Data Test Script")
    print("Usage examples:")
    print("runner.run_test('1HGBH41JXMN109186', 'engine')")
    print("runner.run_test('WBAPH7C51BE5M2396', 'headlight')")
    print()
    
    # Interactive mode
    while True:
        try:
            vin = input("Enter VIN (or 'quit'): ").strip()
            if vin.lower() == 'quit':
                break
            
            part = input("Enter part name: ").strip()
            if part:
                runner.run_test(vin, part)
                print("\n" + "="*60 + "\n")
        except KeyboardInterrupt:
            print("\nExiting...")
            break

if __name__ == "__main__":
    main()