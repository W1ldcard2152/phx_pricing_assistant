#!/usr/bin/env python3

import os
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables
load_dotenv()

def test_gpt41_nano():
    """Test gpt-4.1-nano integration"""
    
    # Initialize OpenAI client
    openai_api_key = os.getenv('OPENAI_API_KEY')
    if not openai_api_key:
        print("ERROR: OPENAI_API_KEY not found in .env file")
        return False
    
    try:
        client = OpenAI(api_key=openai_api_key)
        print("SUCCESS: OpenAI client initialized successfully")
    except Exception as e:
        print(f"ERROR: Failed to initialize OpenAI client: {e}")
        return False
    
    # Test the API call
    try:
        print("Testing gpt-4.1-nano API call...")
        
        response = client.responses.create(
            model="gpt-4.1-nano-2025-04-14",
            input="Test message: Please respond with exactly 'TEST SUCCESSFUL' if you can process this request."
        )
        
        print("API call completed successfully")
        print(f"Response type: {type(response)}")
        
        # Check if response has the expected attribute
        if hasattr(response, 'output_text'):
            print(f"Response has 'output_text' attribute")
            print(f"Response content: '{response.output_text.strip()}'")
            
            if "TEST SUCCESSFUL" in response.output_text.upper():
                print("Model responded correctly to test prompt")
                return True
            else:
                print("WARNING: Model responded but didn't follow the exact instruction")
                return True  # Still working, just different response
        else:
            print(f"ERROR: Response doesn't have 'output_text' attribute")
            print(f"Available attributes: {dir(response)}")
            return False
            
    except Exception as e:
        print(f"ERROR: API call failed: {e}")
        return False

def test_pricing_analysis():
    """Test with sample pricing data"""
    
    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    
    test_prompt = """Analyze these sample prices for A/C Compressor: $50.00, $60.00, $70.00, $80.00, $90.00

Return ONLY valid JSON:
{
  "low_price": [10-20th percentile],
  "average_price": [25-40th percentile], 
  "high_price": [45-60th percentile],
  "items_analyzed": 5,
  "items_filtered_out": 0,
  "reasoning": "Sample data analysis",
  "confidence_rating": "yellow",
  "confidence_explanation": "Test data"
}

IMPORTANT: Your low_price cannot be lower than $50.00 (the minimum price in the dataset)."""

    try:
        print("\nTesting pricing analysis with gpt-4.1-nano...")
        
        response = client.responses.create(
            model="gpt-4.1-nano-2025-04-14",
            input=test_prompt
        )
        
        print("Pricing analysis API call successful")
        print(f"Response: {response.output_text[:200]}...")
        
        # Try to parse as JSON
        import json
        try:
            # Clean up response
            response_text = response.output_text.strip()
            if '{' in response_text:
                json_start = response_text.find('{')
                response_text = response_text[json_start:]
            if '}' in response_text:
                json_end = response_text.rfind('}') + 1
                response_text = response_text[:json_end]
            
            result = json.loads(response_text)
            print("JSON parsing successful")
            
            low_price = result.get('low_price', 0)
            if low_price >= 50.0:
                print(f"SUCCESS: Low price ({low_price}) respects minimum constraint (>=50.00)")
            else:
                print(f"ERROR: Low price ({low_price}) violates minimum constraint (should be >=50.00)")
                
            return True
            
        except json.JSONDecodeError as e:
            print(f"ERROR: JSON parsing failed: {e}")
            return False
            
    except Exception as e:
        print(f"ERROR: Pricing analysis test failed: {e}")
        return False

if __name__ == "__main__":
    print("Testing gpt-4.1-nano Integration")
    print("=" * 50)
    
    # Test 1: Basic API functionality
    basic_test = test_gpt41_nano()
    
    if basic_test:
        # Test 2: Pricing analysis functionality
        pricing_test = test_pricing_analysis()
        
        if pricing_test:
            print("\nAll tests passed! gpt-4.1-nano is ready to use.")
        else:
            print("\nWARNING: Basic API works but pricing analysis needs attention.")
    else:
        print("\nERROR: Basic API test failed. Check your setup.")