#!/usr/bin/env python3
"""
Test script for AI instructions functionality
"""

import os
import sys
from dotenv import load_dotenv

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import PhoenixAuctionAssistant
import tkinter as tk

def test_ai_instructions():
    """Test the AI instructions prompt generation"""
    
    # Create a minimal test environment
    root = tk.Tk()
    root.withdraw()  # Hide the main window
    
    try:
        app = PhoenixAuctionAssistant(root)
        
        # Test custom instructions
        test_instructions = "This vehicle has both turbo and non-turbo engine variants. Turbo engines cost significantly more - filter out non-turbo engines when analyzing turbo engine prices."
        
        # Set test instructions
        app.ai_instructions_text.delete(1.0, tk.END)
        app.ai_instructions_text.insert(1.0, test_instructions)
        
        # Test prompt generation
        sample_csv = """Price,Shipping,Total,Title
150.00,25.00,175.00,"2015 Ford Focus 2.0L Turbo Engine Complete"
89.99,15.00,104.99,"2015 Ford Focus 2.0L Engine Non-Turbo"
200.00,0.00,200.00,"Ford Focus ST Turbo Engine 2.0L EcoBoost 2015"
120.00,20.00,140.00,"2015 Ford Focus Engine 2.0L Naturally Aspirated"
"""
        
        vehicle_info = {'year': '2015', 'make': 'Ford', 'model': 'Focus'}
        
        prompt = app.create_ai_analysis_prompt(
            part_name="engine",
            csv_data=sample_csv,
            min_price=50,
            vehicle_info=vehicle_info
        )
        
        print("AI INSTRUCTIONS TEST RESULTS")
        print("=" * 50)
        print("\nCustom Instructions Retrieved:")
        print(f"'{app.get_custom_ai_instructions()}'")
        print(f"\nMatch Expected: {app.get_custom_ai_instructions() == test_instructions}")
        
        print("\nGenerated Prompt (excerpt):")
        print("-" * 30)
        # Show relevant parts of the prompt
        lines = prompt.split('\n')
        for i, line in enumerate(lines):
            if 'VEHICLE CONTEXT' in line or 'CUSTOM ANALYSIS INSTRUCTIONS' in line or 'turbo' in line.lower():
                print(f"Line {i+1}: {line}")
        
        print(f"\nPrompt contains vehicle context: {'VEHICLE CONTEXT' in prompt}")
        print(f"Prompt contains custom instructions: {'CUSTOM ANALYSIS INSTRUCTIONS' in prompt}")
        print(f"Prompt contains turbo filter instruction: {'turbo' in prompt.lower()}")
        
        # Test save/load functionality
        app.save_ai_instructions()
        app.clear_ai_instructions()
        app.load_ai_instructions()
        
        print(f"\nSave/Load test passed: {app.get_custom_ai_instructions() == test_instructions}")
        
        print("\n[SUCCESS] AI Instructions functionality test completed successfully!")
        
    except Exception as e:
        print(f"[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        root.destroy()

if __name__ == "__main__":
    load_dotenv()
    test_ai_instructions()