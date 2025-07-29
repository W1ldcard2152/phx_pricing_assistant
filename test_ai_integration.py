#!/usr/bin/env python3
"""
Test script for AI-powered pricing analysis
Run this to test the Gemini AI integration with sample eBay data
"""

import os
from dotenv import load_dotenv
import google.generativeai as genai

# Load environment variables
load_dotenv()

def test_ai_integration():
    """Test the AI integration with sample automotive parts data"""
    
    # Check if Gemini API key is configured
    gemini_api_key = os.getenv('GEMINI_API_KEY')
    if not gemini_api_key:
        print("[ERROR] GEMINI_API_KEY not found in .env file")
        print("Please add your Gemini API key to the .env file as:")
        print("GEMINI_API_KEY=your_api_key_here")
        return False
    
    try:
        # Configure Gemini
        genai.configure(api_key=gemini_api_key)
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        print("[SUCCESS] Gemini API configured successfully")
        
        # Sample CSV data for testing (engine parts)
        sample_csv_data = """Price,Shipping,Total,Title
89.99,15.00,104.99,"2012 Honda Civic 1.8L Engine Motor Assembly 140K Miles"
125.50,25.00,150.50,"Honda Civic Engine 2012 2013 2014 R18Z1 1.8L 4 Cylinder"
75.00,0.00,75.00,"12 Honda Civic Engine 1.8 R18Z1 Motor"
200.00,50.00,250.00,"2012-2015 Honda Civic 1.8L Engine Complete Assembly"
45.99,12.99,58.98,"Honda Civic Engine Oil Filter 2012-2015"
350.00,0.00,350.00,"Honda Civic Si 2.4L Engine K24Z7 2012-2015"
"""
        
        # Create test prompt
        prompt = f"""You are an expert automotive parts pricing analyst for a junkyard business. You need to analyze eBay search results for "engine" parts and provide pricing recommendations.

**DATA TO ANALYZE:**
The following CSV contains eBay search results with columns: Price,Shipping,Total,Title

{sample_csv_data}

**YOUR TASK:**
Analyze this data and intelligently filter out inappropriate listings, then calculate three pricing tiers. You must be smart about identifying:

1. **Miscategorized Items**: Look for titles that contain accessories, small components, or items that aren't the actual part (e.g., for "engine" - filters, gaskets, mounts, belts; for "alternator" - brushes, pulleys, wires; for "headlight" - bulbs, ballasts, connectors)

2. **Obvious Outliers**: Items with suspiciously low prices (likely damaged/core parts) or extremely high prices (likely new/premium parts not suitable for junkyard comparison)

3. **Duplicate/Similar Listings**: If you see very similar titles and prices, they might be the same seller with multiple listings

4. **Non-Junkyard Appropriate**: New parts, aftermarket upgrades, or specialty items that don't represent typical junkyard inventory

**MINIMUM PRICE FILTER**: 
Apply a minimum price filter of $50. Remove any items below this threshold.

**REQUIRED OUTPUT FORMAT:**
Return your response as valid JSON with this exact structure:
{{
    "low_price": [budget tier price as number],
    "average_price": [standard tier price as number], 
    "high_price": [premium tier price as number],
    "items_analyzed": [total items in the dataset],
    "items_filtered_out": [number of items you removed],
    "reasoning": "[brief explanation of your filtering logic and price calculation method]"
}}

**PRICING GUIDANCE:**
- Low price: Should represent bottom 10-20% of valid listings (budget junkyard tier)
- Average price: Should represent 25-40% range of valid listings (standard junkyard tier)  
- High price: Should represent 45-60% range of valid listings (premium junkyard tier)
- Round prices to sensible increments ($5 for under $100, $10 for $100-500, $25 for over $500)
- Ensure the three tiers are meaningfully different from each other

Analyze the data carefully and return only the JSON response."""
        
        print("\n[TESTING] Testing AI analysis with sample engine data...")
        
        # Send to AI for analysis
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.1,
                max_output_tokens=1000
            )
        )
        
        print("[SUCCESS] AI analysis completed successfully!")
        print("\n[AI RESPONSE]")
        print(response.text)
        
        # Try to parse the JSON response
        import json
        response_text = response.text.strip()
        if response_text.startswith('```json'):
            response_text = response_text.replace('```json', '').replace('```', '').strip()
        elif response_text.startswith('```'):
            response_text = response_text.replace('```', '').strip()
        
        try:
            result = json.loads(response_text)
            print("\n[SUCCESS] JSON parsing successful!")
            print(f"   Budget Tier: ${result['low_price']}")
            print(f"   Standard Tier: ${result['average_price']}")
            print(f"   Premium Tier: ${result['high_price']}")
            print(f"   Items Analyzed: {result['items_analyzed']}")
            print(f"   Items Filtered: {result['items_filtered_out']}")
            print(f"   AI Reasoning: {result['reasoning'][:100]}...")
            return True
        except json.JSONDecodeError as e:
            print(f"[ERROR] JSON parsing failed: {e}")
            return False
            
    except Exception as e:
        print(f"[ERROR] AI integration test failed: {e}")
        return False

if __name__ == "__main__":
    print("Testing AI Integration for Phoenix Auction Assistant")
    print("=" * 50)
    
    success = test_ai_integration()
    
    if success:
        print("\n[SUCCESS] AI integration test passed!")
        print("\nNext steps:")
        print("1. Add your GEMINI_API_KEY to the .env file")
        print("2. Run the main application: python main.py")
        print("3. Enter a VIN and test the AI-powered pricing analysis")
    else:
        print("\n[ERROR] AI integration test failed!")
        print("Please check your Gemini API configuration.")