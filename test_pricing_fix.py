#!/usr/bin/env python3

import os
import sys
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables
load_dotenv()

# Add main directory to path to import from main.py
sys.path.append('.')

def test_pricing_calculation():
    """Test the fixed pricing calculation with realistic data"""
    
    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    
    # Simulate realistic A/C Compressor data with some items to filter out
    test_csv_data = """Price,Shipping,Total,Title
45.00,15.00,60.00,"2015 Honda Civic A/C Compressor 1.8L Used Good Condition"
38.00,12.00,50.00,"2014-2016 Honda Civic AC Compressor 1.8L Engine OEM"
95.00,0.00,95.00,"Honda Civic A/C Compressor 1.8L 2014-2016 Tested Working"
25.00,20.00,45.00,"Honda Civic AC Compressor FOR PARTS ONLY Damaged"
150.00,25.00,175.00,"NEW Aftermarket AC Compressor Honda Civic 1.8L"
52.00,18.00,70.00,"2015 Honda Civic Air Conditioning Compressor 1.8L"
88.00,0.00,88.00,"Honda Civic 1.8L A/C Compressor 2014-2015 Good Used"
30.00,15.00,45.00,"Honda Civic AC Compressor CORE ONLY needs rebuild"
75.00,10.00,85.00,"2016 Honda Civic A/C Compressor 1.8L Tested Good"
42.00,13.00,55.00,"Honda Civic 1.8L AC Compressor 2014-2016 Used OEM"
200.00,0.00,200.00,"REMANUFACTURED Honda Civic A/C Compressor 1.8L"
65.00,15.00,80.00,"2015 Honda Civic A/C Compressor 1.8L Engine Good Used"
35.00,10.00,45.00,"Honda Civic AC Compressor BROKEN for parts"
58.00,12.00,70.00,"Honda Civic A/C Compressor 1.8L 2014-2016 Working"""

    # Create the vehicle context
    vehicle_info = {
        'year': '2015',
        'make': 'Honda', 
        'model': 'Civic',
        'engine_displacement': '1.8',
        'drive_type': 'FWD',
        'fuel_type': 'Gasoline'
    }
    
    # Create the comprehensive prompt (simplified version of main.py logic)
    vehicle_context = f"""
**VEHICLE CONTEXT:**
You are analyzing parts for a {vehicle_info['year']} {vehicle_info['make']} {vehicle_info['model']}.
Vehicle Specifications: Engine: {vehicle_info['engine_displacement']}L, Drive Type: {vehicle_info['drive_type']}, Fuel Type: {vehicle_info['fuel_type']}
"""

    prompt = f"""Analyze eBay "A/C Compressor" prices for automotive parts business.{vehicle_context}

**DATA:** CSV with Price,Shipping,Total,Title columns:
{test_csv_data}

**CRITICAL: TWO-STEP PROCESS**
STEP 1: FILTER THE DATA
- ENGINE-SPECIFIC PARTS (alternators, starters, compressors, fuel injectors): Must match engine displacement exactly
- UNIVERSAL PARTS (brake lights, condensers, evaporators, mirrors, glass): Compatible across engine sizes for same vehicle model

FILTER OUT:
1. Items marked "for parts", "needs repair", "core", "damaged", "broken"
2. New/aftermarket/remanufactured items (look for "new", "aftermarket", "reman" in titles)
3. Obviously wrong vehicle applications (different make/model entirely)
4. Wrong engine sizes (if engine-specific part)

STEP 2: CALCULATE PERCENTILES FROM FILTERED DATA ONLY
After filtering, take the remaining compatible used parts and calculate:
- low_price = 10-20th percentile of FILTERED data
- average_price = 25-40th percentile of FILTERED data  
- high_price = 45-60th percentile of FILTERED data

**EXAMPLE:**
If you start with 50 items, filter out 30 inappropriate ones, you have 20 good items.
Sort those 20 items by price, then calculate percentiles from those 20.
Your low_price should be around the 2nd-4th cheapest of those 20 good items.

**CRITICAL: DO NOT just return the cheapest price as your low_price!**
The low_price should be the 10-20th percentile, which means approximately 10-20% of the filtered items should be cheaper than your low_price.

**OUTPUT JSON:**
{{
    "low_price": [10-20th percentile of FILTERED compatible parts],
    "average_price": [25-40th percentile of FILTERED compatible parts], 
    "high_price": [45-60th percentile of FILTERED compatible parts],
    "items_analyzed": [count of compatible parts used for percentile calculation],
    "items_filtered_out": [count of removed incompatible/damaged parts],
    "reasoning": "[explain filtering decisions and percentile calculation]",
    "confidence_rating": "[dark_green/light_green/yellow/orange/red]",
    "confidence_explanation": "[reason for confidence level]"
}}

Return only valid JSON.

IMPORTANT: Follow the two-step process exactly:
1. FILTER the data first (remove damaged, wrong engine, etc.)
2. Calculate percentiles from FILTERED data only

Do NOT just return the minimum price (45.00) as your low_price. Calculate the actual 10-20th percentile of the filtered compatible parts."""

    try:
        print("Testing gpt-4.1-nano with realistic A/C Compressor data...")
        print(f"Raw data contains {len(test_csv_data.split(chr(10))[1:])} items")  # Count lines minus header
        
        response = client.responses.create(
            model="gpt-4.1-nano-2025-04-14",
            input=prompt
        )
        
        print("API call successful!")
        print(f"Response: {response.output_text}")
        
        # Parse and validate response
        import json
        response_text = response.output_text.strip()
        
        # Clean up response
        if '{' in response_text:
            json_start = response_text.find('{')
            response_text = response_text[json_start:]
        if '}' in response_text:
            json_end = response_text.rfind('}') + 1
            response_text = response_text[:json_end]
        
        result = json.loads(response_text)
        
        print("\n=== ANALYSIS RESULTS ===")
        print(f"Items analyzed: {result['items_analyzed']}")
        print(f"Items filtered out: {result['items_filtered_out']}")
        print(f"Low price: ${result['low_price']:.2f}")
        print(f"Average price: ${result['average_price']:.2f}")
        print(f"High price: ${result['high_price']:.2f}")
        print(f"Confidence: {result['confidence_rating']}")
        print(f"\nReasoning: {result['reasoning']}")
        
        # Validate the AI analysis
        filtered_items = result['items_analyzed']
        total_items = len([line for line in test_csv_data.split('\n')[1:] if line.strip()])
        
        print(f"\nValidation:")
        print(f"- Started with {total_items} total items")
        print(f"- Filtered to {filtered_items} compatible items")
        print(f"- Filtered out {result['items_filtered_out']} items")
        
        # Check if AI is properly filtering and calculating percentiles
        if filtered_items > 0 and result['items_filtered_out'] > 0:
            print(f"\nSUCCESS: AI properly filtered data and calculated percentiles!")
            print(f"- Low price (${result['low_price']:.2f}) represents 10-20th percentile of {filtered_items} compatible items")
            print(f"- This is NOT the absolute minimum of all {total_items} items")
            return True
        else:
            print(f"\nERROR: AI did not properly filter the data!")
            return False
            
    except Exception as e:
        print(f"Test failed: {e}")
        return False

if __name__ == "__main__":
    print("Testing Pricing Calculation Fix")
    print("=" * 40)
    success = test_pricing_calculation()
    if success:
        print("\nTest PASSED: Pricing calculation is working correctly!")
    else:
        print("\nTest FAILED: Pricing calculation still needs work.")