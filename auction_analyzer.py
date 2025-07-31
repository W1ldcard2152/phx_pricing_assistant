#!/usr/bin/env python3

import tkinter as tk
from tkinter import ttk, messagebox
import requests
import csv
import json
import os
import re
import datetime
from typing import Dict, List, Optional
from dotenv import load_dotenv
import google.generativeai as genai

# Load environment variables
load_dotenv()

class PhoenixAuctionAssistant:
    def __init__(self, root):
        self.root = root
        self.root.title("Phoenix Auction Assistant")
        self.root.geometry("1000x700")
        self.root.minsize(1000, 700)  # Prevent window from getting too small
        self.root.resizable(True, True)  # Allow resizing but maintain minimum
        
        # Load eBay API credentials
        self.ebay_client_id = os.getenv('EBAY_CLIENT_ID')
        self.ebay_client_secret = os.getenv('EBAY_CLIENT_SECRET')
        self.ebay_environment = os.getenv('EBAY_ENVIRONMENT', 'SANDBOX')
        self.ebay_access_token = None
        self.ebay_token_expiry = None  # Track token expiration
        
        # Load Gemini API credentials and configure
        self.gemini_api_key = os.getenv('GEMINI_API_KEY')
        self.use_ai_analysis = os.getenv('USE_AI_ANALYSIS', 'true').lower() == 'true'
        
        if self.gemini_api_key and self.use_ai_analysis:
            try:
                genai.configure(api_key=self.gemini_api_key)
                self.gemini_model = genai.GenerativeModel('gemini-2.0-flash-exp')
            except Exception as e:
                print(f"Failed to initialize Gemini model: {e}")
                self.gemini_model = None
        else:
            self.gemini_model = None
        
        self.setup_gui()
        self.load_parts_list()
    
    def setup_gui(self):
        # Configure root window for proper resizing
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Top controls - use a separate frame to keep them stable
        control_frame = ttk.Frame(main_frame)
        control_frame.grid(row=0, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Label(control_frame, text="VIN:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.vin_entry = ttk.Entry(control_frame, width=30)
        self.vin_entry.grid(row=0, column=1, padx=5, pady=5)
        
        self.calculate_btn = ttk.Button(control_frame, text="Calculate Bid", 
                                       command=self.calculate_bid)
        self.calculate_btn.grid(row=0, column=2, padx=5, pady=5)
        
        # Create notebook for tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights for proper resizing
        main_frame.grid_rowconfigure(1, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)
        control_frame.grid_columnconfigure(1, weight=1)
        
        # Tab 1: Final Output (Auction Bid Analysis)
        self.final_output_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.final_output_frame, text="Final Output")
        
        self.final_output_text = tk.Text(self.final_output_frame, height=25, width=70, wrap=tk.WORD)
        self.final_output_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        final_scrollbar = ttk.Scrollbar(self.final_output_frame, orient="vertical", command=self.final_output_text.yview)
        final_scrollbar.grid(row=0, column=1, sticky="ns")
        self.final_output_text.configure(yscrollcommand=final_scrollbar.set)
        
        self.final_output_frame.grid_rowconfigure(0, weight=1)
        self.final_output_frame.grid_columnconfigure(0, weight=1)
        
        # Tab 2: Debug/Activity
        self.debug_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.debug_frame, text="Debug/Activity")
        
        self.debug_text = tk.Text(self.debug_frame, height=25, width=70, wrap=tk.WORD)
        self.debug_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        debug_scrollbar = ttk.Scrollbar(self.debug_frame, orient="vertical", command=self.debug_text.yview)
        debug_scrollbar.grid(row=0, column=1, sticky="ns")
        self.debug_text.configure(yscrollcommand=debug_scrollbar.set)
        
        self.debug_frame.grid_rowconfigure(0, weight=1)
        self.debug_frame.grid_columnconfigure(0, weight=1)
        
        # Tab 3: AI Instructions
        self.ai_instructions_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.ai_instructions_frame, text="AI Instructions")
        
        # Create AI instructions interface
        self.setup_ai_instructions_tab()
        
        # Tab 4: Raw Search Results
        self.raw_results_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.raw_results_frame, text="Raw Search Results")
        
        # Create sub-notebook for parts
        self.parts_notebook = ttk.Notebook(self.raw_results_frame)
        self.parts_notebook.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.raw_results_frame.grid_rowconfigure(0, weight=1)
        self.raw_results_frame.grid_columnconfigure(0, weight=1)
        
        # Initialize part tabs (will be populated when search starts)
        self.part_frames = {}
        self.part_tables = {}
        
        # Tab 5: VIN History
        self.vin_history_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.vin_history_frame, text="VIN History")
        self.setup_vin_history_tab()
        
        # Keep reference to old results_text for backward compatibility during refactoring
        self.results_text = self.debug_text
        
        # Initialize storage for raw search results
        self.raw_search_results = {}
        
        # Initialize VIN scan history (max 50 entries)
        self.vin_history = []
        # Use absolute paths to ensure we're working with the right directory
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.vin_history_dir = os.path.join(script_dir, 'vin_history')
        self.vin_history_index_file = os.path.join(self.vin_history_dir, 'index.json')
        self.init_vin_history_directory()
        self.load_vin_history_from_files()
        
        # Ensure history display is updated after loading
        if hasattr(self, 'vin_history_tree') and self.vin_history:
            self.update_vin_history_display()
    
    def setup_vin_history_tab(self):
        """Set up the VIN History tab with table display"""
        # Main frame with padding
        main_frame = ttk.Frame(self.vin_history_frame, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.vin_history_frame.grid_rowconfigure(0, weight=1)
        self.vin_history_frame.grid_columnconfigure(0, weight=1)
        
        # Title and info
        title_label = ttk.Label(main_frame, text="VIN Scan History", 
                               font=('Arial', 12, 'bold'))
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 10), sticky=tk.W)
        
        info_label = ttk.Label(main_frame, text="Shows the most recent 50 VIN scans with bid analysis results. Double-click to view details.")
        info_label.grid(row=1, column=0, columnspan=3, pady=(0, 15), sticky=tk.W)
        
        # Create treeview for history table
        columns = ('Date/Time', 'VIN', 'Vehicle', 'Parts Total', 'Budget Bid', 'Standard Bid', 'Premium Bid', 'Status')
        self.vin_history_tree = ttk.Treeview(main_frame, columns=columns, show='headings', height=20)
        
        # Define column headings and widths
        self.vin_history_tree.heading('Date/Time', text='Date/Time')
        self.vin_history_tree.heading('VIN', text='VIN')
        self.vin_history_tree.heading('Vehicle', text='Vehicle')
        self.vin_history_tree.heading('Parts Total', text='Parts Total')
        self.vin_history_tree.heading('Budget Bid', text='Budget Bid')
        self.vin_history_tree.heading('Standard Bid', text='Standard Bid')
        self.vin_history_tree.heading('Premium Bid', text='Premium Bid')
        self.vin_history_tree.heading('Status', text='Status')
        
        self.vin_history_tree.column('Date/Time', width=120, anchor='w')
        self.vin_history_tree.column('VIN', width=100, anchor='w')
        self.vin_history_tree.column('Vehicle', width=180, anchor='w')
        self.vin_history_tree.column('Parts Total', width=80, anchor='e')
        self.vin_history_tree.column('Budget Bid', width=80, anchor='e')
        self.vin_history_tree.column('Standard Bid', width=80, anchor='e')
        self.vin_history_tree.column('Premium Bid', width=80, anchor='e')
        self.vin_history_tree.column('Status', width=100, anchor='w')
        
        # Add scrollbars
        history_v_scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=self.vin_history_tree.yview)
        history_h_scrollbar = ttk.Scrollbar(main_frame, orient="horizontal", command=self.vin_history_tree.xview)
        self.vin_history_tree.configure(yscrollcommand=history_v_scrollbar.set, xscrollcommand=history_h_scrollbar.set)
        
        # Grid layout
        self.vin_history_tree.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        history_v_scrollbar.grid(row=2, column=1, sticky="ns")
        history_h_scrollbar.grid(row=3, column=0, sticky="ew")
        
        # Configure grid weights
        main_frame.grid_rowconfigure(2, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)
        
        # Bind double-click event to view details
        self.vin_history_tree.bind('<Double-1>', self.on_history_double_click)
        
        # Control buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=4, column=0, columnspan=2, pady=(10, 0), sticky=tk.W)
        
        remove_selected_btn = ttk.Button(button_frame, text="Remove Selected", 
                                        command=self.remove_selected_history)
        remove_selected_btn.grid(row=0, column=0, padx=(0, 10))
        
        clear_history_btn = ttk.Button(button_frame, text="Clear All", 
                                     command=self.clear_vin_history)
        clear_history_btn.grid(row=0, column=1, padx=(0, 10))
        
        export_history_btn = ttk.Button(button_frame, text="Export to CSV", 
                                      command=self.export_vin_history)
        export_history_btn.grid(row=0, column=2)
    
    def add_to_vin_history(self, vin, vehicle_info, parts_prices, bid_analysis):
        """Add a completed VIN scan to the history"""
        import datetime
        
        # Create history entry
        timestamp = datetime.datetime.now()
        
        # Determine overall status based on confidence ratings and failed parts
        failed_parts = []
        low_confidence_parts = []
        
        for part, prices in parts_prices.items():
            if isinstance(prices, dict):
                if prices.get('low', 0) == 0 and prices.get('average', 0) == 0 and prices.get('high', 0) == 0:
                    failed_parts.append(part)
                elif prices.get('confidence_rating', 'yellow') in ['orange', 'red']:
                    low_confidence_parts.append(part)
        
        # Determine status
        if failed_parts:
            status = f"❌ {len(failed_parts)} Failed"
        elif low_confidence_parts:
            status = f"⚠️ {len(low_confidence_parts)} Low Conf"
        else:
            status = "✅ Complete"
        
        # Format vehicle string
        vehicle_str = f"{vehicle_info.get('year', '')} {vehicle_info.get('make', '')} {vehicle_info.get('model', '')}"
        if vehicle_info.get('trim'):
            vehicle_str += f" {vehicle_info['trim']}"
        
        history_entry = {
            'timestamp': timestamp,
            'vin': vin,
            'vehicle_info': vehicle_info.copy(),
            'vehicle_string': vehicle_str.strip(),
            'parts_prices': parts_prices.copy(),
            'bid_analysis': bid_analysis.copy(),
            'status': status,
            'failed_parts': failed_parts,
            'low_confidence_parts': low_confidence_parts,
            'filename': None  # Will be set during save
        }
        
        # Add to beginning of history list
        self.vin_history.insert(0, history_entry)
        
        # Keep only most recent 50 entries
        if len(self.vin_history) > 50:
            self.vin_history = self.vin_history[:50]
        
        # Update the history table display
        self.update_vin_history_display()
        
        # Save to file
        self.save_vin_analysis_to_file(history_entry)
    
    def update_vin_history_display(self):
        """Update the VIN history table display"""
        # Clear existing items
        for item in self.vin_history_tree.get_children():
            self.vin_history_tree.delete(item)
        
        # Add items to table
        for index, entry in enumerate(self.vin_history):
            timestamp_str = entry['timestamp'].strftime("%m/%d/%y %H:%M")
            vin = entry['vin']
            vehicle = entry['vehicle_string']
            
            # Calculate parts total (use budget tier as representative total)
            totals = entry['bid_analysis']['totals']
            parts_total = f"${totals['low']:.2f}"
            
            bids = entry['bid_analysis']['bids']
            budget_bid = f"${bids['low']:.2f}"
            standard_bid = f"${bids['average']:.2f}"
            premium_bid = f"${bids['high']:.2f}"
            
            status = entry['status']
            
            # Store the entry index as a tag for easy removal
            item_id = self.vin_history_tree.insert('', 'end', values=(
                timestamp_str, vin, vehicle, parts_total, budget_bid, standard_bid, premium_bid, status
            ), tags=(str(index),))
    
    def remove_selected_history(self):
        """Remove selected entries from VIN history"""
        selected_items = self.vin_history_tree.selection()
        if not selected_items:
            messagebox.showinfo("No Selection", "Please select one or more entries to remove.")
            return
        
        # Confirm removal
        num_selected = len(selected_items)
        if num_selected == 1:
            message = "Remove the selected entry? This cannot be undone."
        else:
            message = f"Remove {num_selected} selected entries? This cannot be undone."
        
        if messagebox.askyesno("Confirm Removal", message):
            # Get indices of selected items using tags
            indices_to_remove = []
            for item in selected_items:
                # Get the index from the item's tag
                tags = self.vin_history_tree.item(item, 'tags')
                if tags:
                    index = int(tags[0])
                    indices_to_remove.append(index)
            
            # Sort indices in reverse order to remove from the end first
            indices_to_remove.sort(reverse=True)
            
            # Remove entries from history list and delete associated files
            for index in indices_to_remove:
                if 0 <= index < len(self.vin_history):
                    entry = self.vin_history[index]
                    # Delete the associated JSON file if it exists
                    if 'filename' in entry:
                        filepath = os.path.join(self.vin_history_dir, entry['filename'])
                        try:
                            if os.path.exists(filepath):
                                os.remove(filepath)
                        except Exception as e:
                            print(f"Warning: Could not delete file {filepath}: {e}")
                    
                    # Remove from history list
                    del self.vin_history[index]
            
            # Update display and save
            self.update_vin_history_display()
            self.save_history_index()

    def clear_vin_history(self):
        """Clear the VIN history"""
        if messagebox.askyesno("Confirm Clear", "Clear all VIN history? This cannot be undone."):
            self.vin_history.clear()
            self.update_vin_history_display()
            self.save_history_index()  # Update index after clearing
    
    def export_vin_history(self):
        """Export VIN history to CSV file"""
        if not self.vin_history:
            messagebox.showinfo("No Data", "No VIN history to export.")
            return
        
        try:
            import tkinter.filedialog as filedialog
            import datetime
            
            # Get save location
            default_filename = f"vin_history_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                initialname=default_filename
            )
            
            if filename:
                with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    
                    # Write header
                    writer.writerow([
                        'Timestamp', 'VIN', 'Vehicle', 'Parts Total', 'Budget Bid', 'Standard Bid', 'Premium Bid', 
                        'Status', 'Failed Parts', 'Low Confidence Parts'
                    ])
                    
                    # Write data
                    for entry in self.vin_history:
                        writer.writerow([
                            entry['timestamp'].strftime("%m/%d/%Y %H:%M:%S"),
                            entry['vin'],
                            entry['vehicle_string'],
                            f"${entry['bid_analysis']['totals']['low']:.2f}",
                            f"${entry['bid_analysis']['bids']['low']:.2f}",
                            f"${entry['bid_analysis']['bids']['average']:.2f}",
                            f"${entry['bid_analysis']['bids']['high']:.2f}",
                            entry['status'],
                            ', '.join(entry['failed_parts']) if entry['failed_parts'] else '',
                            ', '.join(entry['low_confidence_parts']) if entry['low_confidence_parts'] else ''
                        ])
                
                messagebox.showinfo("Export Complete", f"VIN history exported to {filename}")
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export VIN history: {str(e)}")
    
    def on_history_double_click(self, event):
        """Handle double-click on history entry to show details"""
        selection = self.vin_history_tree.selection()
        if not selection:
            return
        
        # Get the selected item index
        item = selection[0]
        index = self.vin_history_tree.index(item)
        
        if index < len(self.vin_history):
            entry = self.vin_history[index]
            # Load full analysis data if needed
            full_entry = self.load_full_analysis(entry)
            self.show_history_details(full_entry)
    
    def show_history_details(self, entry):
        """Show detailed view of a history entry in a popup window"""
        
        # Create popup window
        detail_window = tk.Toplevel(self.root)
        detail_window.title(f"VIN Details - {entry['vin']}")
        detail_window.geometry("800x600")
        detail_window.resizable(True, True)
        
        # Main frame with padding
        main_frame = ttk.Frame(detail_window, padding="15")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        detail_window.grid_rowconfigure(0, weight=1)
        detail_window.grid_columnconfigure(0, weight=1)
        
        # Header info
        header_text = f"VIN: {entry['vin']}\n"
        header_text += f"Scanned: {entry['timestamp'].strftime('%m/%d/%Y at %H:%M:%S')}\n"
        header_text += f"Vehicle: {entry['vehicle_string']}\n"
        header_text += f"Status: {entry['status']}\n\n"
        
        # Create text widget for details
        detail_text = tk.Text(main_frame, height=30, width=80, wrap=tk.WORD)
        detail_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Add scrollbar
        detail_scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=detail_text.yview)
        detail_scrollbar.grid(row=0, column=1, sticky="ns")
        detail_text.configure(yscrollcommand=detail_scrollbar.set)
        
        main_frame.grid_rowconfigure(0, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)
        
        # Populate with analysis data
        detail_text.insert(tk.END, header_text)
        
        # Recreate the analysis display format
        vehicle_info = entry['vehicle_info']
        parts_prices = entry['parts_prices']
        bid_analysis = entry['bid_analysis']
        
        # Display comprehensive vehicle information
        base_vehicle = f"{vehicle_info['year']} {vehicle_info['make']} {vehicle_info['model']}"
        if vehicle_info.get('trim'):
            detail_text.insert(tk.END, f"Full Vehicle: {base_vehicle} {vehicle_info['trim']}\n")
        else:
            detail_text.insert(tk.END, f"Vehicle: {base_vehicle}\n")
        
        # Add vehicle specifications
        spec_lines = []
        if vehicle_info.get('engine_displacement'):
            try:
                displacement = float(vehicle_info['engine_displacement'])
                engine_info = f"{round(displacement, 1)}L"
            except (ValueError, TypeError):
                engine_info = vehicle_info['engine_displacement']
            if vehicle_info.get('engine_cylinders'):
                engine_info += f" ({vehicle_info['engine_cylinders']} cyl)"
            if vehicle_info.get('engine_designation'):
                engine_info += f" [Code: {vehicle_info['engine_designation']}]"
            spec_lines.append(f"Engine: {engine_info}")
        
        if vehicle_info.get('drive_type'):
            spec_lines.append(f"Drive: {vehicle_info['drive_type']}")
        if vehicle_info.get('fuel_type'):
            spec_lines.append(f"Fuel: {vehicle_info['fuel_type']}")
        if vehicle_info.get('body_class'):
            spec_lines.append(f"Body: {vehicle_info['body_class']}")
        
        if spec_lines:
            detail_text.insert(tk.END, f"Specs: {' | '.join(spec_lines)}\n\n")
        
        # Display parts breakdown with confidence
        confidence_display = {
            'dark_green': '🟢 High',
            'light_green': '🟢 Good', 
            'yellow': '🟡 Medium',
            'orange': '🟠 Low',
            'red': '🔴 Poor'
        }
        
        detail_text.insert(tk.END, f"{'Part':<20} {'Budget':<10} {'Standard':<10} {'Premium':<10} {'Confidence':<15}\n")
        detail_text.insert(tk.END, f"{'Tier':<20} {'Tier':<10} {'Tier':<10} {'Tier':<10} {'Rating':<15}\n")
        detail_text.insert(tk.END, "-" * 80 + "\n")
        
        for part, prices in parts_prices.items():
            if isinstance(prices, dict):
                low = prices.get('low', 0)
                avg = prices.get('average', 0)
                high = prices.get('high', 0)
                confidence = prices.get('confidence_rating', 'yellow')
                confidence_text = confidence_display.get(confidence, '🟡 Unknown')
                detail_text.insert(tk.END, f"{part.capitalize():<20} ${low:<9.2f} ${avg:<9.2f} ${high:<9.2f} {confidence_text:<15}\n")
        
        # Display totals and bids
        totals = bid_analysis['totals']
        bids = bid_analysis['bids']
        
        detail_text.insert(tk.END, "-" * 80 + "\n")
        detail_text.insert(tk.END, f"{'TOTALS:':<20} ${totals['low']:<9.2f} ${totals['average']:<9.2f} ${totals['high']:<9.2f}\n\n")
        
        detail_text.insert(tk.END, "RECOMMENDED AUCTION BIDS (Dynamic Formula):\n")
        detail_text.insert(tk.END, f"Budget-based bid:    ${bids['low']:.2f}  (if you expect lower-grade parts)\n")
        detail_text.insert(tk.END, f"Standard bid:        ${bids['average']:.2f}  (typical market pricing)\n")
        detail_text.insert(tk.END, f"Premium bid:         ${bids['high']:.2f}  (if vehicle is in great condition)\n\n")
        
        # Show confidence warnings if any
        if entry['low_confidence_parts']:
            detail_text.insert(tk.END, "⚠️  CONFIDENCE WARNINGS:\n")
            for part in entry['low_confidence_parts']:
                confidence = parts_prices[part].get('confidence_rating', 'yellow')
                detail_text.insert(tk.END, f"• {part.capitalize()}: {confidence_display.get(confidence, confidence)} confidence\n")
            detail_text.insert(tk.END, "\n")
        
        # Show confidence explanations
        detail_text.insert(tk.END, "AI CONFIDENCE EXPLANATIONS:\n")
        for part, prices in parts_prices.items():
            if isinstance(prices, dict):
                confidence_explanation = prices.get('confidence_explanation', '')
                if confidence_explanation:
                    detail_text.insert(tk.END, f"• {part.capitalize()}: {confidence_explanation}\n")
        
        # Show failed parts if any
        if entry['failed_parts']:
            detail_text.insert(tk.END, f"\nFAILED PARTS: {', '.join(entry['failed_parts'])}\n")
        
        # Make text read-only
        detail_text.configure(state='disabled')
        
        # Close button
        close_btn = ttk.Button(detail_window, text="Close", command=detail_window.destroy)
        close_btn.grid(row=1, column=0, pady=(10, 0))
    
    def init_vin_history_directory(self):
        """Initialize the VIN history directory structure"""
        try:
            if not os.path.exists(self.vin_history_dir):
                os.makedirs(self.vin_history_dir)
        except Exception as e:
            print(f"Failed to create VIN history directory: {e}")
    
    def generate_vehicle_filename(self, vehicle_info):
        """Generate a filename based on vehicle information"""
        try:
            year = vehicle_info.get('year', 'Unknown')
            make = vehicle_info.get('make', 'Unknown')
            model = vehicle_info.get('model', 'Unknown')
            
            # Clean up the strings for filename use
            import re
            year = re.sub(r'[^\w]', '', str(year))
            make = re.sub(r'[^\w]', '', str(make))
            model = re.sub(r'[^\w]', '', str(model))
            
            # Create timestamp for uniqueness
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            
            return f"{year}_{make}_{model}_{timestamp}.json"
        except Exception:
            # Fallback to timestamp-only filename
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            return f"vin_analysis_{timestamp}.json"
    
    def save_vin_analysis_to_file(self, history_entry):
        """Save individual VIN analysis to organized JSON file"""
        try:
            # Generate filename based on vehicle info
            filename = self.generate_vehicle_filename(history_entry['vehicle_info'])
            filepath = os.path.join(self.vin_history_dir, filename)
            
            # Create a deep copy and prepare for JSON serialization
            entry_copy = {}
            for key, value in history_entry.items():
                if key == 'timestamp':
                    entry_copy[key] = value.isoformat()
                elif isinstance(value, dict):
                    entry_copy[key] = dict(value)  # Deep copy dictionaries
                elif isinstance(value, list):
                    entry_copy[key] = list(value)  # Deep copy lists
                else:
                    entry_copy[key] = value
            
            entry_copy['filename'] = filename  # Store filename reference
            
            # Ensure directory exists
            os.makedirs(self.vin_history_dir, exist_ok=True)
            
            # Save individual analysis file
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(entry_copy, f, indent=2, ensure_ascii=False)
            
            # Update the original entry with filename
            history_entry['filename'] = filename
            
            # Update the history index
            self.save_history_index()
                
        except Exception as e:
            print(f"Failed to save VIN analysis to {filepath}: {e}")
            import traceback
            traceback.print_exc()
    
    def save_history_index(self):
        """Save the history index (lightweight file with just basic info)"""
        try:
            index_data = []
            for entry in self.vin_history:
                # Create safe copies of nested data
                bids_copy = dict(entry['bid_analysis']['bids']) if 'bid_analysis' in entry and 'bids' in entry['bid_analysis'] else {}
                totals_copy = dict(entry['bid_analysis']['totals']) if 'bid_analysis' in entry and 'totals' in entry['bid_analysis'] else {}
                
                index_entry = {
                    'timestamp': entry['timestamp'].isoformat(),
                    'vin': entry['vin'],
                    'vehicle_string': entry['vehicle_string'],
                    'filename': entry.get('filename', None),
                    'status': entry['status'],
                    'bids': bids_copy,
                    'totals': totals_copy
                }
                index_data.append(index_entry)
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.vin_history_index_file), exist_ok=True)
            
            with open(self.vin_history_index_file, 'w', encoding='utf-8') as f:
                json.dump(index_data, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            print(f"Failed to save history index: {e}")
            import traceback
            traceback.print_exc()
    
    def load_vin_history_from_files(self):
        """Load VIN history from organized JSON files"""
        try:
            if os.path.exists(self.vin_history_index_file):
                # Load from index file
                with open(self.vin_history_index_file, 'r', encoding='utf-8') as f:
                    index_data = json.load(f)
                
                self.vin_history = []
                for index_entry in index_data:
                    # Create lightweight entry for display
                    entry = {
                        'timestamp': datetime.datetime.fromisoformat(index_entry['timestamp']),
                        'vin': index_entry['vin'],
                        'vehicle_string': index_entry['vehicle_string'],
                        'filename': index_entry.get('filename'),
                        'status': index_entry['status'],
                        'bid_analysis': {
                            'bids': index_entry['bids'],
                            'totals': index_entry['totals']
                        },
                        # Mark as lightweight entry
                        'is_lightweight': True
                    }
                    self.vin_history.append(entry)
                
                # Ensure we don't exceed 50 entries
                if len(self.vin_history) > 50:
                    self.vin_history = self.vin_history[:50]
                    self.save_history_index()
                
                # Update the display if the tab is set up
                if hasattr(self, 'vin_history_tree'):
                    self.update_vin_history_display()
            else:
                # No index file exists, scan directory for existing files
                self.scan_existing_files()
                    
        except Exception as e:
            print(f"Failed to load VIN history: {e}")
            self.vin_history = []
    
    def scan_existing_files(self):
        """Scan existing JSON files and rebuild index (for migration)"""
        try:
            if not os.path.exists(self.vin_history_dir):
                return
            
            self.vin_history = []
            files = [f for f in os.listdir(self.vin_history_dir) if f.endswith('.json') and f != 'index.json']
            
            # Sort by modification time (newest first)
            files.sort(key=lambda x: os.path.getmtime(os.path.join(self.vin_history_dir, x)), reverse=True)
            
            for filename in files[:50]:  # Load max 50 most recent
                filepath = os.path.join(self.vin_history_dir, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        entry_data = json.load(f)
                    
                    # Convert back to runtime format
                    entry_data['timestamp'] = datetime.datetime.fromisoformat(entry_data['timestamp'])
                    entry_data['filename'] = filename
                    self.vin_history.append(entry_data)
                    
                except Exception as e:
                    print(f"Failed to load file {filename}: {e}")
            
            # Save the rebuilt index
            if self.vin_history:
                self.save_history_index()
                
        except Exception as e:
            print(f"Failed to scan existing files: {e}")
            self.vin_history = []
    
    def load_full_analysis(self, entry):
        """Load full analysis data from file when needed (for detail view)"""
        try:
            if entry.get('is_lightweight') and entry.get('filename'):
                filepath = os.path.join(self.vin_history_dir, entry['filename'])
                if os.path.exists(filepath):
                    with open(filepath, 'r', encoding='utf-8') as f:
                        full_data = json.load(f)
                    
                    # Convert timestamp back
                    full_data['timestamp'] = datetime.datetime.fromisoformat(full_data['timestamp'])
                    return full_data
            
            # Return the entry as-is if it's already full or no file available
            return entry
            
        except Exception as e:
            print(f"Failed to load full analysis: {e}")
            return entry
    
    def setup_ai_instructions_tab(self):
        """Set up the AI Instructions tab with enhanced save/edit functionality"""
        # Main frame with padding
        main_frame = ttk.Frame(self.ai_instructions_frame, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.ai_instructions_frame.grid_rowconfigure(0, weight=1)
        self.ai_instructions_frame.grid_columnconfigure(0, weight=1)
        
        # Title
        title_label = ttk.Label(main_frame, text="AI Analysis Custom Instructions", 
                               font=('Arial', 12, 'bold'))
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 10), sticky=tk.W)
        
        # Description
        desc_text = """Use this tab to provide custom instructions to the AI for analyzing your specific vehicle's parts.
Save multiple instruction sets for different vehicle types or scenarios."""
        desc_label = ttk.Label(main_frame, text=desc_text, wraplength=800)
        desc_label.grid(row=1, column=0, columnspan=3, pady=(0, 15), sticky=tk.W)
        
        # Presets section
        presets_frame = ttk.LabelFrame(main_frame, text="Instruction Presets", padding="10")
        presets_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Label(presets_frame, text="Quick Load:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        
        self.preset_var = tk.StringVar()
        self.preset_combo = ttk.Combobox(presets_frame, textvariable=self.preset_var, 
                                        width=30, state="readonly")
        self.preset_combo.grid(row=0, column=1, padx=(0, 10))
        
        load_preset_btn = ttk.Button(presets_frame, text="Load Preset", 
                                   command=self.load_preset)
        load_preset_btn.grid(row=0, column=2, padx=(0, 10))
        
        # Preset name entry and save
        ttk.Label(presets_frame, text="Save as:").grid(row=1, column=0, sticky=tk.W, padx=(0, 10), pady=(10, 0))
        
        self.preset_name_var = tk.StringVar()
        self.preset_name_entry = ttk.Entry(presets_frame, textvariable=self.preset_name_var, width=30)
        self.preset_name_entry.grid(row=1, column=1, padx=(0, 10), pady=(10, 0))
        
        save_preset_btn = ttk.Button(presets_frame, text="Save Preset", 
                                   command=self.save_preset)
        save_preset_btn.grid(row=1, column=2, padx=(0, 10), pady=(10, 0))
        
        delete_preset_btn = ttk.Button(presets_frame, text="Delete Preset", 
                                     command=self.delete_preset)
        delete_preset_btn.grid(row=1, column=3, pady=(10, 0))
        
        # Custom Instructions section
        instructions_label = ttk.Label(main_frame, text="Custom Instructions:", 
                                     font=('Arial', 10, 'bold'))
        instructions_label.grid(row=3, column=0, sticky=tk.W, pady=(10, 5))
        
        # Auto-save indicator
        self.auto_save_label = ttk.Label(main_frame, text="", foreground="green")
        self.auto_save_label.grid(row=3, column=2, sticky=tk.E, pady=(10, 5))
        
        # Text area for custom instructions
        self.ai_instructions_text = tk.Text(main_frame, height=8, width=80, wrap=tk.WORD)
        self.ai_instructions_text.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Bind auto-save on text change
        self.ai_instructions_text.bind('<KeyRelease>', lambda e: self.auto_save_instructions())
        self.ai_instructions_text.bind('<Button-1>', lambda e: self.auto_save_instructions())
        
        # Add scrollbar for instructions
        instructions_scrollbar = ttk.Scrollbar(main_frame, orient="vertical", 
                                             command=self.ai_instructions_text.yview)
        instructions_scrollbar.grid(row=4, column=2, sticky="ns", pady=(0, 10))
        self.ai_instructions_text.configure(yscrollcommand=instructions_scrollbar.set)
        
        # Examples section
        examples_label = ttk.Label(main_frame, text="Example Instructions:", 
                                 font=('Arial', 10, 'bold'))
        examples_label.grid(row=5, column=0, sticky=tk.W, pady=(10, 5))
        
        # Examples text (read-only)
        examples_text = """• "This vehicle has both turbo and non-turbo engine variants. Turbo engines cost significantly more - filter out non-turbo engines when analyzing turbo engine prices."

• "This model year had a mid-year engine redesign. Early production engines (VIN starts with 1-5) are different from late production (VIN starts with 6-9)."

• "This vehicle uses a CVT transmission which is expensive to replace. Regular automatic transmissions from other models should be filtered out."

• "Headlights for this model have adaptive/LED versions that cost 3x more than standard halogen. Focus on halogen versions for junkyard pricing."

• "This engine size (3.5L) was only available in premium trim levels. Lower trim engines (2.4L, 2.0L) should be excluded from analysis."

• "Brake calipers for this model have performance Brembo versions on sport trim. Standard calipers are much cheaper and more appropriate for junkyard analysis."

• "Fuel pumps for this model are known to fail frequently. There are aftermarket high-performance versions that cost more - focus on OEM replacements."

• "This model uses a unique alternator design that's not interchangeable with other years. Only consider parts specifically for this generation (2012-2015)."

• "The manual transmission version of this engine has different accessories and mounts. Focus only on automatic transmission setups."

• "This model had a recall for fuel pump issues, so there are many refurbished/updated versions available at premium prices. Focus on standard used parts."""
        
        self.examples_text = tk.Text(main_frame, height=12, width=80, wrap=tk.WORD)
        self.examples_text.grid(row=6, column=0, columnspan=2, sticky=(tk.W, tk.E))
        self.examples_text.insert(1.0, examples_text)
        self.examples_text.configure(state='disabled')  # Make read-only
        
        # Add scrollbar for examples
        examples_scrollbar = ttk.Scrollbar(main_frame, orient="vertical", 
                                         command=self.examples_text.yview)
        examples_scrollbar.grid(row=6, column=2, sticky="ns")
        self.examples_text.configure(yscrollcommand=examples_scrollbar.set)
        
        # Configure grid weights
        main_frame.grid_rowconfigure(4, weight=1)
        main_frame.grid_rowconfigure(6, weight=2)
        main_frame.grid_columnconfigure(0, weight=1)
        presets_frame.grid_columnconfigure(1, weight=1)
        
        # Manual save/clear buttons (kept for explicit control)
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=7, column=0, columnspan=3, pady=(10, 0), sticky=tk.W)
        
        manual_save_btn = ttk.Button(button_frame, text="Manual Save", 
                                   command=self.save_ai_instructions)
        manual_save_btn.grid(row=0, column=0, padx=(0, 10))
        
        clear_btn = ttk.Button(button_frame, text="Clear All", 
                              command=self.clear_ai_instructions)
        clear_btn.grid(row=0, column=1, padx=(0, 10))
        
        # Initialize preset system and load existing instructions
        self.init_preset_system()
        self.load_ai_instructions()
    
    def init_preset_system(self):
        """Initialize the preset system"""
        import os
        # Create presets directory if it doesn't exist
        self.presets_dir = "ai_instruction_presets"
        if not os.path.exists(self.presets_dir):
            os.makedirs(self.presets_dir)
        
        # Set up auto-save timer
        self.auto_save_timer = None
        
        # Load available presets
        self.refresh_preset_list()
    
    def refresh_preset_list(self):
        """Refresh the preset dropdown list"""
        import os
        presets = []
        if os.path.exists(self.presets_dir):
            for filename in os.listdir(self.presets_dir):
                if filename.endswith('.txt'):
                    preset_name = filename[:-4]  # Remove .txt extension
                    presets.append(preset_name)
        
        presets.sort()
        self.preset_combo['values'] = presets
        
        # Select default preset if available
        if 'default' in presets:
            self.preset_var.set('default')
        elif presets:
            self.preset_var.set(presets[0])
    
    def save_preset(self):
        """Save current instructions as a named preset"""
        preset_name = self.preset_name_var.get().strip()
        if not preset_name:
            messagebox.showerror("Error", "Please enter a name for the preset")
            return
        
        # Sanitize filename
        import re
        safe_name = re.sub(r'[^\w\-_\.]', '_', preset_name)
        
        instructions = self.ai_instructions_text.get(1.0, tk.END).strip()
        
        try:
            preset_file = os.path.join(self.presets_dir, f"{safe_name}.txt")
            with open(preset_file, 'w', encoding='utf-8') as f:
                f.write(instructions)
            
            self.refresh_preset_list()
            self.preset_var.set(safe_name)
            self.preset_name_var.set("")
            
            messagebox.showinfo("Saved", f"Preset '{preset_name}' saved successfully!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save preset: {str(e)}")
    
    def load_preset(self):
        """Load a selected preset"""
        preset_name = self.preset_var.get()
        if not preset_name:
            return
        
        try:
            preset_file = os.path.join(self.presets_dir, f"{preset_name}.txt")
            with open(preset_file, 'r', encoding='utf-8') as f:
                instructions = f.read()
                self.ai_instructions_text.delete(1.0, tk.END)
                self.ai_instructions_text.insert(1.0, instructions)
                
            self.show_auto_save_feedback("Preset loaded")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load preset: {str(e)}")
    
    def delete_preset(self):
        """Delete the selected preset"""
        preset_name = self.preset_var.get()
        if not preset_name:
            return
        
        if messagebox.askyesno("Confirm Delete", f"Delete preset '{preset_name}'?"):
            try:
                import os
                preset_file = os.path.join(self.presets_dir, f"{preset_name}.txt")
                os.remove(preset_file)
                
                self.refresh_preset_list()
                self.preset_var.set("")
                
                messagebox.showinfo("Deleted", f"Preset '{preset_name}' deleted successfully!")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete preset: {str(e)}")
    
    def auto_save_instructions(self):
        """Auto-save instructions with a delay to avoid constant writes"""
        if self.auto_save_timer:
            self.root.after_cancel(self.auto_save_timer)
        
        # Save after 2 seconds of inactivity
        self.auto_save_timer = self.root.after(2000, self._perform_auto_save)
    
    def _perform_auto_save(self):
        """Actually perform the auto-save"""
        instructions = self.ai_instructions_text.get(1.0, tk.END).strip()
        
        try:
            with open('ai_instructions.txt', 'w', encoding='utf-8') as f:
                f.write(instructions)
            
            self.show_auto_save_feedback("Auto-saved")
        except Exception as e:
            self.show_auto_save_feedback("Auto-save failed", error=True)
    
    def show_auto_save_feedback(self, message, error=False):
        """Show auto-save feedback temporarily"""
        color = "red" if error else "green"
        self.auto_save_label.config(text=message, foreground=color)
        
        # Clear the message after 3 seconds
        self.root.after(3000, lambda: self.auto_save_label.config(text=""))
    
    def save_ai_instructions(self):
        """Manual save AI instructions to a file"""
        instructions = self.ai_instructions_text.get(1.0, tk.END).strip()
        try:
            with open('ai_instructions.txt', 'w', encoding='utf-8') as f:
                f.write(instructions)
            messagebox.showinfo("Saved", "AI instructions saved successfully!")
            self.show_auto_save_feedback("Manually saved")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save instructions: {str(e)}")
    
    def clear_ai_instructions(self):
        """Clear the AI instructions text area"""
        if messagebox.askyesno("Confirm Clear", "Clear all instructions? This cannot be undone."):
            self.ai_instructions_text.delete(1.0, tk.END)
            self.show_auto_save_feedback("Cleared")
    
    def load_ai_instructions(self):
        """Load AI instructions from file if it exists"""
        try:
            with open('ai_instructions.txt', 'r', encoding='utf-8') as f:
                instructions = f.read()
                self.ai_instructions_text.delete(1.0, tk.END)
                self.ai_instructions_text.insert(1.0, instructions)
        except FileNotFoundError:
            pass  # File doesn't exist yet, that's fine
        except Exception as e:
            print(f"Error loading AI instructions: {e}")
    
    def get_custom_ai_instructions(self):
        """Get the current custom AI instructions"""
        return self.ai_instructions_text.get(1.0, tk.END).strip()
    
    def create_part_tab(self, part_name):
        """Create a new tab for a specific part in the Raw Search Results section"""
        if part_name in self.part_frames:
            return  # Tab already exists
        
        # Create frame for this part
        part_frame = ttk.Frame(self.parts_notebook)
        self.parts_notebook.add(part_frame, text=part_name.capitalize())
        self.part_frames[part_name] = part_frame
        
        # Create treeview for table display
        columns = ('Price', 'Shipping', 'Total', 'Title')
        tree = ttk.Treeview(part_frame, columns=columns, show='headings', height=20)
        
        # Define column headings and widths
        tree.heading('Price', text='Price')
        tree.heading('Shipping', text='Shipping')
        tree.heading('Total', text='Total')
        tree.heading('Title', text='Title')
        
        tree.column('Price', width=80, anchor='e')
        tree.column('Shipping', width=80, anchor='e')
        tree.column('Total', width=80, anchor='e')
        tree.column('Title', width=500, anchor='w')
        
        # Add scrollbars
        v_scrollbar = ttk.Scrollbar(part_frame, orient="vertical", command=tree.yview)
        h_scrollbar = ttk.Scrollbar(part_frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # Grid layout
        tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        v_scrollbar.grid(row=0, column=1, sticky="ns")
        h_scrollbar.grid(row=1, column=0, sticky="ew")
        
        part_frame.grid_rowconfigure(0, weight=1)
        part_frame.grid_columnconfigure(0, weight=1)
        
        self.part_tables[part_name] = tree
    
    def update_part_table(self, part_name, items):
        """Update the table for a specific part with search results"""
        if part_name not in self.part_tables:
            self.create_part_tab(part_name)
        
        tree = self.part_tables[part_name]
        
        # Clear existing items
        for item in tree.get_children():
            tree.delete(item)
        
        # Sort items by total price (price + shipping)
        sorted_items = sorted(items, key=lambda x: x.get('total_price', x.get('price', 0)))
        
        # Add items to table
        for item in sorted_items:
            price = item.get('price', 0)
            shipping = item.get('shipping', 0)
            total_price = item.get('total_price', price + shipping)
            title = item.get('title', 'No title')
            
            price_str = f"${price:.2f}"
            shipping_str = "FREE" if shipping == 0 else f"${shipping:.2f}"
            total_str = f"${total_price:.2f}"
            
            tree.insert('', 'end', values=(price_str, shipping_str, total_str, title))
    
    def load_parts_list(self):
        try:
            with open('parts_list.csv', 'r') as file:
                reader = csv.DictReader(file)
                self.parts_list = []
                for row in reader:
                    if row['search_query'] and row['category_id']:
                        self.parts_list.append({
                            'search_query': row['search_query'],
                            'category_id': row['category_id'],
                            'min_price': float(row.get('min_price', 0))
                        })
        except FileNotFoundError:
            self.parts_list = [
                {"search_query": "engine", "category_id": "33615"},
                {"search_query": "transmission", "category_id": "33616"},
                {"search_query": "alternator", "category_id": "33555"}
            ]
    
    def decode_vin(self, vin: str) -> Optional[Dict]:
        url = f"https://vpic.nhtsa.dot.gov/api/vehicles/decodevin/{vin}?format=json"
        
        # Try 3 times with increasing timeout
        for attempt in range(3):
            try:
                timeout = 15 + (attempt * 10)  # 15s, 25s, 35s
                self.results_text.insert(tk.END, f"VIN decode attempt {attempt + 1} (timeout: {timeout}s)...\n")
                self.root.update()
                
                response = requests.get(url, timeout=timeout)
                response.raise_for_status()
                
                data = response.json()
                if data.get('Results'):
                    vehicle_info = {}
                    for result in data['Results']:
                        variable = result['Variable']
                        value = result['Value']
                        
                        # Core vehicle identification
                        if variable == 'Make':
                            vehicle_info['make'] = value
                        elif variable == 'Model':
                            vehicle_info['model'] = value
                        elif variable == 'Model Year':
                            vehicle_info['year'] = value
                        elif variable == 'Trim':
                            vehicle_info['trim'] = value
                        
                        # Engine specifications
                        elif variable == 'Displacement (CC)' or variable == 'Displacement (L)':
                            if value and value != 'null':
                                # Convert CC to L if needed and round to nearest 10th
                                try:
                                    if variable == 'Displacement (CC)':
                                        displacement_l = float(value) / 1000
                                        vehicle_info['engine_displacement'] = str(round(displacement_l, 1))
                                    else:
                                        displacement_l = float(value)
                                        vehicle_info['engine_displacement'] = str(round(displacement_l, 1))
                                except (ValueError, TypeError):
                                    vehicle_info['engine_displacement'] = value
                        elif variable == 'Engine Number of Cylinders':
                            if value and value != 'null':
                                vehicle_info['engine_cylinders'] = value
                        elif variable == 'Fuel Type - Primary':
                            if value and value != 'null':
                                vehicle_info['fuel_type'] = value
                        elif variable == 'Engine Configuration':
                            if value and value != 'null':
                                vehicle_info['engine_configuration'] = value
                        
                        # Drive and transmission
                        elif variable == 'Drive Type':
                            if value and value != 'null':
                                vehicle_info['drive_type'] = value
                        elif variable == 'Transmission Style':
                            if value and value != 'null':
                                vehicle_info['transmission_style'] = value
                        elif variable == 'Transmission Speeds':
                            if value and value != 'null':
                                vehicle_info['transmission_speeds'] = value
                        
                        # Body specifications
                        elif variable == 'Body Class':
                            if value and value != 'null':
                                vehicle_info['body_class'] = value
                        elif variable == 'Doors':
                            if value and value != 'null':
                                vehicle_info['doors'] = value
                        elif variable == 'Vehicle Type':
                            if value and value != 'null':
                                vehicle_info['vehicle_type'] = value
                    
                    # Extract engine designation from VIN 8th digit
                    if len(vin) >= 8:
                        vehicle_info['engine_designation'] = vin[7]  # 8th character (0-indexed)
                    
                    # Check if we have the core required fields
                    required_fields = ['make', 'model', 'year']
                    if all(vehicle_info.get(field) for field in required_fields):
                        # Log additional decoded information
                        additional_info = []
                        if vehicle_info.get('engine_displacement'):
                            # Round engine displacement to nearest 10th for logging
                            try:
                                displacement = float(vehicle_info['engine_displacement'])
                                rounded_displacement = round(displacement, 1)
                                additional_info.append(f"Engine: {rounded_displacement}L")
                            except (ValueError, TypeError):
                                additional_info.append(f"Engine: {vehicle_info['engine_displacement']}")
                        if vehicle_info.get('drive_type'):
                            additional_info.append(f"Drive: {vehicle_info['drive_type']}")
                        if vehicle_info.get('fuel_type'):
                            additional_info.append(f"Fuel: {vehicle_info['fuel_type']}")
                        if vehicle_info.get('body_class'):
                            additional_info.append(f"Body: {vehicle_info['body_class']}")
                        if vehicle_info.get('engine_designation'):
                            additional_info.append(f"Engine Code: {vehicle_info['engine_designation']}")
                        
                        self.results_text.insert(tk.END, f"VIN decoded successfully!\n")
                        if additional_info:
                            self.results_text.insert(tk.END, f"Additional specs: {', '.join(additional_info)}\n")
                        self.root.update()
                        return vehicle_info
                        
            except Exception as e:
                self.results_text.insert(tk.END, f"Attempt {attempt + 1} failed: {str(e)}\n")
                self.root.update()
                if attempt == 2:  # Last attempt
                    self.display_error(f"VIN decode failed after 3 attempts: {str(e)}")
                    return None
    
    def get_ebay_access_token(self) -> bool:
        # OPTIMIZATION 5: Check if existing token is still valid
        import datetime
        if (self.ebay_access_token and self.ebay_token_expiry and 
            datetime.datetime.now() < self.ebay_token_expiry):
            return True
        
        self.results_text.insert(tk.END, "Authenticating with eBay...\n")
        self.root.update()
        
        # Reload credentials in case .env was updated
        load_dotenv(override=True)
        self.ebay_client_id = os.getenv('EBAY_CLIENT_ID')
        self.ebay_client_secret = os.getenv('EBAY_CLIENT_SECRET')
        self.ebay_environment = os.getenv('EBAY_ENVIRONMENT', 'SANDBOX')
        
        if not self.ebay_client_id or not self.ebay_client_secret:
            self.display_error("eBay credentials not found in .env file")
            self.display_error(f"Client ID exists: {bool(self.ebay_client_id)}")
            self.display_error(f"Client Secret exists: {bool(self.ebay_client_secret)}")
            return False
        
        try:
            # eBay OAuth endpoint
            if self.ebay_environment == 'PRODUCTION':
                oauth_url = "https://api.ebay.com/identity/v1/oauth2/token"
            else:
                oauth_url = "https://api.sandbox.ebay.com/identity/v1/oauth2/token"
            
            self.results_text.insert(tk.END, f"Using environment: {self.ebay_environment}\n")
            self.results_text.insert(tk.END, f"OAuth URL: {oauth_url}\n")
            self.root.update()
            
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Authorization': f'Basic {self._encode_credentials()}'
            }
            
            data = {
                'grant_type': 'client_credentials',
                'scope': 'https://api.ebay.com/oauth/api_scope'
            }
            
            response = requests.post(oauth_url, headers=headers, data=data, timeout=10)
            
            self.results_text.insert(tk.END, f"eBay OAuth response: {response.status_code}\n")
            self.root.update()
            
            if response.status_code != 200:
                self.results_text.insert(tk.END, f"Response text: {response.text}\n")
                self.root.update()
            
            response.raise_for_status()
            
            token_data = response.json()
            self.results_text.insert(tk.END, f"Token response keys: {list(token_data.keys())}\n")
            self.root.update()
            
            self.ebay_access_token = token_data.get('access_token')
            expires_in = token_data.get('expires_in', 7200)  # Default 2 hours
            
            if self.ebay_access_token:
                # Set token expiry time (subtract 5 minutes for safety margin)
                import datetime
                self.ebay_token_expiry = datetime.datetime.now() + datetime.timedelta(seconds=expires_in - 300)
                self.results_text.insert(tk.END, "eBay authentication successful!\n")
                return True
            else:
                self.display_error("No access token in response")
                self.display_error(f"Full response: {token_data}")
                return False
            
        except Exception as e:
            self.display_error(f"Failed to get eBay access token: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                self.display_error(f"Response status: {e.response.status_code}")
                self.display_error(f"Response text: {e.response.text}")
            return False
    
    def _encode_credentials(self) -> str:
        import base64
        credentials = f"{self.ebay_client_id}:{self.ebay_client_secret}"
        return base64.b64encode(credentials.encode()).decode()
    
    def _analyze_prices_with_ai(self, raw_items: List[Dict], part_name: str, minimum_price: float = 0) -> Dict[str, float]:
        """Use AI to analyze pricing data instead of traditional statistical methods"""
        if not self.gemini_model or not self.use_ai_analysis:
            if not self.use_ai_analysis:
                self.results_text.insert(tk.END, f"AI analysis disabled, using traditional analysis for {part_name}\n")
            else:
                self.results_text.insert(tk.END, f"Gemini API not configured, falling back to traditional analysis for {part_name}\n")
            self.root.update()
            # Fall back to traditional method
            raw_prices = [item.get('total_price', item.get('price', 0)) for item in raw_items]
            raw_titles = [item.get('title', '') for item in raw_items]
            return self._analyze_price_distribution(raw_prices, part_name, raw_titles, minimum_price)
        
        if not raw_items:
            return {"low": 0, "average": 0, "high": 0, "items_analyzed": 0, "items_filtered_out": 0, "reasoning": "No data provided"}
        
        try:
            # Format data for AI analysis
            csv_data = self.format_raw_results_for_ai(part_name, raw_items)
            # We need vehicle_info for context, but it's not passed to this method
            # For now, we'll extract it from the search results or pass None
            prompt = self.create_ai_analysis_prompt(part_name, csv_data, minimum_price, getattr(self, 'current_vehicle_info', None))
            
            self.results_text.insert(tk.END, f"Analyzing {part_name} with AI ({len(raw_items)} items)...\n")
            self.root.update()
            
            # OPTIMIZATION 3: Improved Gemini API settings
            max_retries = 2  # Reduced from 3 to 2
            for attempt in range(max_retries):
                try:
                    response = self.gemini_model.generate_content(
                        prompt,
                        generation_config=genai.types.GenerationConfig(
                            temperature=0.1,  # Low temperature for consistent analysis
                            max_output_tokens=800,  # Reduced from 1000 to 800
                            candidate_count=1  # Ensure single response
                        )
                    )
                    break
                except Exception as api_error:
                    if attempt == max_retries - 1:
                        raise api_error
                    self.results_text.insert(tk.END, f"AI attempt {attempt + 1} failed, retrying...\n")
                    self.root.update()
                    import time
                    time.sleep(0.5)  # Reduced delay from 1s to 0.5s
            
            # Parse JSON response
            response_text = response.text.strip()
            
            # Clean up the response in case it has markdown formatting
            if response_text.startswith('```json'):
                response_text = response_text.replace('```json', '').replace('```', '').strip()
            elif response_text.startswith('```'):
                response_text = response_text.replace('```', '').strip()
            
            result = json.loads(response_text)
            
            # Validate the response structure
            required_keys = ['low_price', 'average_price', 'high_price', 'items_analyzed', 'items_filtered_out', 'reasoning', 'confidence_rating', 'confidence_explanation']
            if not all(key in result for key in required_keys):
                raise ValueError(f"AI response missing required keys: {required_keys}")
            
            # Validate confidence rating
            valid_confidence_levels = ['dark_green', 'light_green', 'yellow', 'orange', 'red']
            confidence_rating = result.get('confidence_rating', '').lower()
            if confidence_rating not in valid_confidence_levels:
                self.results_text.insert(tk.END, f"Invalid confidence rating '{confidence_rating}', defaulting to 'yellow'\n")
                confidence_rating = 'yellow'
            
            # Log AI reasoning for debugging
            self.results_text.insert(tk.END, f"AI Analysis: {result['items_analyzed']} analyzed, {result['items_filtered_out']} filtered\n")
            self.results_text.insert(tk.END, f"Confidence: {confidence_rating.upper()} - {result['confidence_explanation']}\n")
            self.results_text.insert(tk.END, f"Full AI Reasoning for {part_name}:\n{result['reasoning']}\n")
            self.results_text.insert(tk.END, "-"*50 + "\n")
            self.root.update()
            
            return {
                "low": float(result['low_price']),
                "average": float(result['average_price']),
                "high": float(result['high_price']),
                "items_analyzed": result['items_analyzed'],
                "items_filtered_out": result['items_filtered_out'],
                "reasoning": result['reasoning'],
                "confidence_rating": confidence_rating,
                "confidence_explanation": result['confidence_explanation'],
                "cleaned_count": result['items_analyzed'] - result['items_filtered_out'],
                "items_removed": result['items_filtered_out']
            }
            
        except json.JSONDecodeError as e:
            self.results_text.insert(tk.END, f"AI JSON parsing error for {part_name}: {str(e)}\n")
            self.results_text.insert(tk.END, f"Raw AI response: {response.text[:200]}...\n")
            self.root.update()
        except Exception as e:
            self.results_text.insert(tk.END, f"AI analysis error for {part_name}: {str(e)}\n")
            self.root.update()
        
        # Fall back to traditional method on error
        self.results_text.insert(tk.END, f"Falling back to traditional analysis for {part_name}\n")
        self.root.update()
        raw_prices = [item.get('total_price', item.get('price', 0)) for item in raw_items]
        raw_titles = [item.get('title', '') for item in raw_items]
        return self._analyze_price_distribution(raw_prices, part_name, raw_titles, minimum_price)
    
    def _analyze_price_distribution(self, raw_prices: List[float], part_name: str, raw_titles: List[str] = None, minimum_price: float = 0) -> Dict[str, float]:
        """
        Junkyard Parts Pricing Analysis System
        Implements sophisticated data cleaning and percentile-based pricing strategy
        """
        if not raw_prices:
            return {"low": 0, "average": 0, "high": 0, "items_removed": 0, "cleaned_count": 0}
        
        if len(raw_prices) < 3:
            avg = sum(raw_prices) / len(raw_prices)
            return {"low": avg, "average": avg, "high": avg, "items_removed": 0, "cleaned_count": len(raw_prices)}
        
        original_count = len(raw_prices)
        cleaned_prices = []
        removed_items = []
        
        # Step 1: Remove miscategorized items based on suspicious keywords
        suspicious_keywords = {
            'engine': ['oil filter', 'housing', 'gasket', 'seal', 'sensor', 'valve cover', 'dipstick', 'bracket', 'mount', 'belt', 'pulley'],
            'alternator': ['brush', 'pulley', 'wire', 'connector', 'regulator', 'belt'],
            'transmission': ['fluid', 'filter', 'gasket', 'cooler', 'mount', 'line'],
            'starter': ['solenoid', 'brush', 'drive', 'gear', 'bolt'],
            'brake caliper': ['pad', 'rotor', 'disc', 'fluid', 'line', 'hose'],
            'fuel pump': ['filter', 'line', 'hose', 'tank', 'sending unit'],
            'headlight': ['bulb', 'ballast', 'wire', 'connector', 'lens', 'cover']
        }
        
        keywords_to_check = suspicious_keywords.get(part_name.lower(), [])
        
        for i, price in enumerate(raw_prices):
            title = raw_titles[i].lower() if raw_titles and i < len(raw_titles) else ""
            
            # Check for suspicious keywords
            is_suspicious = any(keyword in title for keyword in keywords_to_check)
            
            if is_suspicious:
                removed_items.append(f"${price:.2f} - Miscategorized (contains suspicious keywords)")
                continue
                
            cleaned_prices.append(price)
        
        # Step 2: Apply configurable minimum prices from CSV
        if minimum_price > 0:
            further_cleaned = []
            for price in cleaned_prices:
                if price >= minimum_price:
                    further_cleaned.append(price)
                else:
                    removed_items.append(f"${price:.2f} - Below minimum (${minimum_price})")
            
            cleaned_prices = further_cleaned
        
        # Step 3: Optional IQR outlier detection (for extreme outliers only)
        if len(cleaned_prices) >= 10:
            sorted_prices = sorted(cleaned_prices)
            q1_idx = len(sorted_prices) // 4
            q3_idx = 3 * len(sorted_prices) // 4
            q1 = sorted_prices[q1_idx]
            q3 = sorted_prices[q3_idx]
            iqr = q3 - q1
            
            lower_bound = q1 - 1.5 * iqr
            upper_bound = q3 + 1.5 * iqr
            
            iqr_cleaned = []
            for price in cleaned_prices:
                if price < lower_bound or price > upper_bound:
                    removed_items.append(f"${price:.2f} - Statistical outlier (IQR method)")
                    continue
                iqr_cleaned.append(price)
            
            cleaned_prices = iqr_cleaned
        
        if not cleaned_prices:
            return {"low": 0, "average": 0, "high": 0, "items_removed": original_count, "cleaned_count": 0}
        
        # Calculate percentile-based pricing tiers
        sorted_prices = sorted(cleaned_prices)
        n = len(sorted_prices)
        
        # Calculate percentiles using proper interpolation
        def get_percentile(data, percentile):
            if len(data) == 1:
                return data[0]
            index = (percentile / 100.0) * (len(data) - 1)
            lower_index = int(index)
            upper_index = min(lower_index + 1, len(data) - 1)
            weight = index - lower_index
            return data[lower_index] * (1 - weight) + data[upper_index] * weight
        
        raw_p10 = get_percentile(sorted_prices, 10)
        raw_p30 = get_percentile(sorted_prices, 30)  
        raw_p50 = get_percentile(sorted_prices, 50)
        
        # Smart rounding based on price range
        def smart_round(price):
            if price < 100:
                return round(price / 5) * 5  # Round to nearest $5
            elif price < 500:
                return round(price / 10) * 10  # Round to nearest $10
            else:
                return round(price / 25) * 25  # Round to nearest $25
        
        budget_tier = smart_round(raw_p10)
        standard_tier = smart_round(raw_p30)
        premium_tier = smart_round(raw_p50)
        
        # Handle categories with very few results differently
        if n < 10:
            # For small datasets, use even more aggressive percentiles
            raw_p10 = get_percentile(sorted_prices, 5)   # Very low percentile
            raw_p30 = get_percentile(sorted_prices, 25)
            raw_p50 = get_percentile(sorted_prices, 50)
            
            # Use smaller rounding increments
            def small_round(price):
                if price < 50:
                    return round(price)  # Round to nearest $1
                elif price < 200:
                    return round(price / 5) * 5  # Round to nearest $5
                else:
                    return round(price / 10) * 10  # Round to nearest $10
            
            budget_tier = small_round(raw_p10)
            standard_tier = small_round(raw_p30)
            premium_tier = small_round(raw_p50)
        
        # Ensure tiers are different - if they're the same after rounding, adjust
        if budget_tier == standard_tier == premium_tier and n >= 3:
            # Force some separation
            price_range = max(sorted_prices) - min(sorted_prices)
            if price_range > 10:  # Only if there's meaningful range
                if price_range < 50:
                    step = 5
                elif price_range < 200:
                    step = 10
                else:
                    step = 25
                
                budget_tier = max(budget_tier - step, min(sorted_prices))
                premium_tier = premium_tier + step
        
        return {
            "low": budget_tier,           # 10th percentile (Budget tier)
            "average": standard_tier,     # 30th percentile (Standard tier)  
            "high": premium_tier,         # 50th percentile (Premium tier)
            "raw_p10": raw_p10,
            "raw_p30": raw_p30,
            "raw_p50": raw_p50,
            "items_removed": original_count - len(cleaned_prices),
            "cleaned_count": len(cleaned_prices),
            "removed_details": removed_items[:3],  # First 3 removed items for debugging
            "final_range": max(cleaned_prices) - min(cleaned_prices) if cleaned_prices else 0,
            "minimum_price": minimum_price
        }
    
    def search_ebay_parts(self, vehicle_info: Dict) -> Dict[str, float]:
        self.results_text.insert(tk.END, "Starting eBay parts search...\n")
        self.root.update()
        
        if not self.ebay_access_token and not self.get_ebay_access_token():
            self.results_text.insert(tk.END, "Failed to get eBay token, aborting search\n")
            self.root.update()
            return {}
        
        parts_prices = {}
        
        # eBay Browse API endpoint
        if self.ebay_environment == 'PRODUCTION':
            search_url = "https://api.ebay.com/buy/browse/v1/item_summary/search"
        else:
            search_url = "https://api.sandbox.ebay.com/buy/browse/v1/item_summary/search"
        
        headers = {
            'Authorization': f'Bearer {self.ebay_access_token}',
            'Content-Type': 'application/json'
        }
        
        # DISABLED: Concurrent processing causing freezes, using sequential by default
        use_concurrent = os.getenv('USE_CONCURRENT_SEARCH', 'false').lower() == 'true'
        
        if use_concurrent:
            try:
                import concurrent.futures
                
                def search_single_part_safe(part):
                    try:
                        return self._search_single_part_optimized(part, vehicle_info, search_url, headers)
                    except Exception as e:
                        # Return error result instead of raising
                        return part['search_query'], {
                            'low': 0.0, 'average': 0.0, 'high': 0.0,
                            'error': str(e), 'raw_items': []
                        }
                
                # Execute searches concurrently (reduced to 3 threads for stability)
                self.results_text.insert(tk.END, f"Searching {len(self.parts_list)} parts (3 concurrent)...\n")
                self.root.update()
                
                completed_count = 0
                
                with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                    # Submit all jobs
                    future_to_part = {executor.submit(search_single_part_safe, part): part for part in self.parts_list}
                    
                    # Process results as they complete
                    for future in concurrent.futures.as_completed(future_to_part):
                        part = future_to_part[future]
                        try:
                            part_name, part_result = future.result(timeout=45)  # 45 second timeout per part
                            parts_prices[part_name] = part_result
                            completed_count += 1
                            
                            # Check for errors in result
                            if 'error' in part_result:
                                self.results_text.insert(tk.END, f"✗ {part_name} failed: {part_result['error']}\n")
                            else:
                                self.results_text.insert(tk.END, f"✓ {part_name} completed ({completed_count}/{len(self.parts_list)})\n")
                            self.root.update()
                            
                        except concurrent.futures.TimeoutError:
                            self.results_text.insert(tk.END, f"✗ {part['search_query']} timed out\n")
                            parts_prices[part['search_query']] = {'low': 0.0, 'average': 0.0, 'high': 0.0, 'raw_items': []}
                            self.root.update()
                        except Exception as exc:
                            self.results_text.insert(tk.END, f"✗ {part['search_query']} failed: {str(exc)}\n")
                            parts_prices[part['search_query']] = {'low': 0.0, 'average': 0.0, 'high': 0.0, 'raw_items': []}
                            self.root.update()
                            
            except Exception as concurrent_error:
                self.results_text.insert(tk.END, f"Concurrent processing failed, switching to sequential: {str(concurrent_error)}\n")
                use_concurrent = False
        
        # Sequential processing (default and safer)
        if not use_concurrent:
            self.results_text.insert(tk.END, f"Searching {len(self.parts_list)} parts sequentially (optimized)...\n")
            self.root.update()
            
            for i, part in enumerate(self.parts_list):
                try:
                    self.results_text.insert(tk.END, f"Searching {part['search_query']} ({i+1}/{len(self.parts_list)})...\n")
                    self.root.update()
                    
                    # Call the optimized search function
                    part_name, part_result = self._search_single_part_optimized(part, vehicle_info, search_url, headers)
                    parts_prices[part_name] = part_result
                    
                    # Show completion with confidence if available
                    confidence = part_result.get('confidence_rating', '')
                    confidence_text = f" ({confidence.upper()})" if confidence else ""
                    self.results_text.insert(tk.END, f"✓ {part_name} completed{confidence_text}\n")
                    self.root.update()
                    
                except Exception as e:
                    self.results_text.insert(tk.END, f"✗ {part['search_query']} failed: {str(e)[:100]}\n")
                    parts_prices[part['search_query']] = {'low': 0.0, 'average': 0.0, 'high': 0.0, 'raw_items': []}
                    self.root.update()
        
        # After all searches complete, update the part tables
        self.results_text.insert(tk.END, "Updating search result tables...\n")
        self.root.update()
        
        for part_name, part_data in parts_prices.items():
            if isinstance(part_data, dict) and 'raw_items' in part_data:
                # Extract raw_items from the result and store in raw_search_results
                raw_items = part_data.pop('raw_items')  # Remove from parts_prices
                self.raw_search_results[part_name] = raw_items
                self.update_part_table(part_name, raw_items)
        
        return parts_prices
    
    def _search_single_part_optimized(self, part, vehicle_info, search_url, headers):
        """Optimized single part search with better error handling and timeout"""
        try:
            # Single targeted search: full year only for speed
            year = vehicle_info['year']
            
            # Include engine size for engine searches to improve specificity
            engine_size = ""
            if part['search_query'].lower() == 'engine' and vehicle_info.get('engine_displacement'):
                try:
                    displacement = float(vehicle_info['engine_displacement'])
                    engine_size = f" {round(displacement, 1)}L"
                except (ValueError, TypeError):
                    engine_size = f" {vehicle_info['engine_displacement']}"
            
            # Handle Chrysler 300C and 300S by dropping the suffix letter
            model = vehicle_info['model']
            if vehicle_info['make'].upper() == 'CHRYSLER' and model.upper() in ['300C', '300S']:
                model = '300'
            
            search_query = f"{year} {vehicle_info['make']} {model}{engine_size} {part['search_query']}"
            
            # Match your manual search - just Used condition (3000)
            condition_filter = "conditionIds:{3000}"  # Used only
            buying_filter = "buyingOptions:{FIXED_PRICE}"
            
            # Add price filter if minimum price is specified for this part
            price_filter = ""
            min_price = part.get('min_price', 0)
            if min_price > 0:
                price_filter = f"price:[{min_price}..],priceCurrency:USD"
            
            # Build filter string - combine all filters
            filters = [condition_filter, buying_filter]
            if price_filter:
                filters.append(price_filter)
            
            params = {
                'q': search_query,
                'category_ids': part['category_id'],
                'filter': ','.join(filters),
                'sort': 'price',
                'limit': '200'  # Keep 200 items as requested
            }
            
            # OPTIMIZATION 2: Reduced timeout and better connection settings
            response = requests.get(search_url, headers=headers, params=params, 
                                  timeout=8, stream=False)  # Reduced from 10s to 8s
            
            if response.status_code != 200:
                return part['search_query'], {'low': 0.0, 'average': 0.0, 'high': 0.0}
            
            data = response.json()
            items = data.get('itemSummaries', [])
            
            prices = []
            titles = []
            raw_items = []  # Store raw items for table display
            
            if items:
                for item in items:
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
                            
                            # No price filtering - accept all valid prices
                            prices.append(total_price)
                            titles.append(item.get('title', ''))
                            
                            # Store raw item data for table display
                            raw_items.append({
                                'price': price,
                                'shipping': shipping_cost,
                                'total_price': total_price,
                                'title': item.get('title', 'No title'),
                                'item_id': item.get('itemId', ''),
                                'condition': item.get('condition', ''),
                                'location': item.get('itemLocation', {}).get('country', '')
                            })
                                
                        except (ValueError, TypeError):
                            continue
            
            if prices:
                # AI-Powered Junkyard Parts Pricing Analysis System
                price_analysis = self._analyze_prices_with_ai(raw_items, part['search_query'], part.get('min_price', 0))
                
                # Store all price points and AI analysis metadata
                part_result = {
                    'low': price_analysis["low"],
                    'average': price_analysis["average"], 
                    'high': price_analysis["high"],
                    'reasoning': price_analysis.get("reasoning", ""),
                    'items_analyzed': price_analysis.get("items_analyzed", 0),
                    'items_filtered_out': price_analysis.get("items_filtered_out", 0),
                    'cleaned_count': price_analysis.get("cleaned_count", 0),
                    'confidence_rating': price_analysis.get("confidence_rating", "yellow"),
                    'confidence_explanation': price_analysis.get("confidence_explanation", "No confidence data available"),
                    'raw_items': raw_items  # Store raw items in result for main thread processing
                }
                
                return part['search_query'], part_result
            else:
                return part['search_query'], {
                    'low': 0.0, 'average': 0.0, 'high': 0.0,
                    'raw_items': []  # Empty raw items
                }
                
        except Exception as e:
            error_msg = f"eBay search error for {part['search_query']}: {str(e)}"
            return part['search_query'], {'low': 0.0, 'average': 0.0, 'high': 0.0}
    
    def calculate_recommended_bid(self, parts_prices: Dict[str, dict]) -> Dict[str, float]:
        # Calculate totals for low, average, and high scenarios
        totals = {'low': 0, 'average': 0, 'high': 0}
        
        for part_prices in parts_prices.values():
            if isinstance(part_prices, dict):
                totals['low'] += part_prices.get('low', 0)
                totals['average'] += part_prices.get('average', 0)
                totals['high'] += part_prices.get('high', 0)
            else:
                # Fallback for old format
                totals['low'] += part_prices
                totals['average'] += part_prices
                totals['high'] += part_prices
        
        # Calculate bids using new formula:
        # if Parts_Value <= 3000: Bid = 300
        # else: Excess = Parts_Value - 3000; Percentage = 0.25 + 0.40 × sqrt((Parts_Value - 3000) / 15000); Bid = 300 + Excess × Percentage
        import math
        
        def calculate_bid(parts_value):
            if parts_value <= 0:
                return 0
            elif parts_value <= 3000:
                return 300
            else:
                excess = parts_value - 3000
                percentage = 0.25 + 0.40 * math.sqrt((parts_value - 3000) / 15000)
                return 300 + excess * percentage
        
        bids = {
            'low': calculate_bid(totals['low']),
            'average': calculate_bid(totals['average']),
            'high': calculate_bid(totals['high'])
        }
        
        return {'totals': totals, 'bids': bids}
    
    def format_raw_results_for_ai(self, part_name: str, raw_items: List[Dict]) -> str:
        """Format raw search results into CSV format for AI analysis"""
        csv_lines = []
        csv_lines.append("Price,Shipping,Total,Title")
        
        for item in raw_items:
            price = item.get('price', 0)
            shipping = item.get('shipping', 0)
            total_price = item.get('total_price', price + shipping)
            title = item.get('title', '').replace(',', ';').replace('\n', ' ').strip()
            
            csv_lines.append(f"{price:.2f},{shipping:.2f},{total_price:.2f},\"{title}\"")
        
        return "\n".join(csv_lines)
    
    def create_ai_analysis_prompt(self, part_name: str, csv_data: str, min_price: float = 0, vehicle_info: dict = None) -> str:
        """Create comprehensive prompt for AI analysis of eBay pricing data"""
        # Get custom user instructions
        custom_instructions = self.get_custom_ai_instructions()
        
        # Build comprehensive vehicle context
        vehicle_context = ""
        if vehicle_info:
            base_info = f"{vehicle_info.get('year', 'Unknown')} {vehicle_info.get('make', 'Unknown')} {vehicle_info.get('model', 'Unknown')}"
            vehicle_context = f"\n**VEHICLE CONTEXT:**\nYou are analyzing parts for a {base_info}.\n"
            
            # Add detailed specifications for better parts analysis (limited to key specs)
            detailed_specs = []
            if vehicle_info.get('engine_displacement'):
                # Round engine displacement to nearest 10th
                try:
                    displacement = float(vehicle_info['engine_displacement'])
                    rounded_displacement = round(displacement, 1)
                    detailed_specs.append(f"Engine: {rounded_displacement}L")
                except (ValueError, TypeError):
                    detailed_specs.append(f"Engine: {vehicle_info['engine_displacement']}")
            if vehicle_info.get('drive_type'):
                detailed_specs.append(f"Drive Type: {vehicle_info['drive_type']}")
            if vehicle_info.get('fuel_type'):
                detailed_specs.append(f"Fuel Type: {vehicle_info['fuel_type']}")
            
            if detailed_specs:
                vehicle_context += f"Vehicle Specifications: {', '.join(detailed_specs)}\n"
            
            # Add parts fitment guidance based on vehicle specs
            fitment_guidance = []
            if vehicle_info.get('drive_type'):
                drive_type = vehicle_info['drive_type'].lower()
                if 'awd' in drive_type or 'all-wheel' in drive_type:
                    fitment_guidance.append("AWD systems have unique drivetrain components - exclude FWD/RWD specific parts")
                elif 'fwd' in drive_type or 'front-wheel' in drive_type:
                    fitment_guidance.append("FWD vehicle - exclude RWD/AWD specific drivetrain parts")
                elif 'rwd' in drive_type or 'rear-wheel' in drive_type:
                    fitment_guidance.append("RWD vehicle - exclude FWD/AWD specific drivetrain parts")
            
            if vehicle_info.get('fuel_type'):
                fuel_type = vehicle_info['fuel_type'].lower()
                if 'diesel' in fuel_type:
                    fitment_guidance.append("Diesel engine - fuel system parts differ significantly from gasoline")
                elif 'gasoline' in fuel_type:
                    fitment_guidance.append("Gasoline engine - exclude diesel-specific fuel system parts")
            
            if vehicle_info.get('body_class'):
                body_class = vehicle_info['body_class'].lower()
                if 'coupe' in body_class:
                    fitment_guidance.append("Coupe body - some parts may differ from sedan variants")
                elif 'sedan' in body_class:
                    fitment_guidance.append("Sedan body - some parts may differ from coupe/hatchback variants")
                elif 'suv' in body_class or 'truck' in body_class:
                    fitment_guidance.append("SUV/Truck body - larger/heavier duty components than car variants")
            
            
            if fitment_guidance:
                vehicle_context += f"\n**PARTS FITMENT CONSIDERATIONS:**\n"
                for guidance in fitment_guidance:
                    vehicle_context += f"• {guidance}\n"
        
        # Build custom instructions section
        custom_section = ""
        if custom_instructions:
            custom_section = f"""
**CUSTOM ANALYSIS INSTRUCTIONS:**
The user has provided these specific instructions for analyzing this vehicle's parts:

{custom_instructions}

Please incorporate these instructions into your analysis and filtering decisions.
"""
        
        # OPTIMIZATION 4: Streamlined AI prompt for faster processing
        return f"""Analyze eBay "{part_name}" prices for junkyard business.{vehicle_context}{custom_section}

**DATA:** CSV with Price,Shipping,Total,Title columns:
{csv_data}

**FILTER OUT:**
1. Accessories/small parts (filters, gaskets, bulbs, connectors, etc.)
2. New/aftermarket/premium items
3. Wrong specifications for this vehicle
4. Obvious outliers (damaged cores or overpriced items)
{"5. Items under $" + str(min_price) if min_price > 0 else ""}

**CONFIDENCE RULES:**
- RED if majority of data is wrong engine size/transmission/drivetrain type
- RED if mostly inappropriate listings  
- ORANGE if poor data quality or small sample
- YELLOW if mixed quality
- LIGHT_GREEN if good appropriate data
- DARK_GREEN if excellent high-quality data

**OUTPUT JSON:**
{{
    "low_price": [10-20th percentile, rounded],
    "average_price": [25-40th percentile, rounded], 
    "high_price": [45-60th percentile, rounded],
    "items_analyzed": [total count],
    "items_filtered_out": [removed count],
    "reasoning": "[brief filter logic]",
    "confidence_rating": "[dark_green/light_green/yellow/orange/red]",
    "confidence_explanation": "[brief confidence reason]"
}}

Return only valid JSON."""
    
    def clear_all_tabs(self):
        """Clear all tabs and reset for new calculation"""
        # Clear debug tab
        self.debug_text.delete(1.0, tk.END)
        
        # Clear final output tab
        self.final_output_text.delete(1.0, tk.END)
        
        # Clear raw search results and remove all part tabs
        self.raw_search_results.clear()
        for part_name in list(self.part_frames.keys()):
            self.parts_notebook.forget(self.part_frames[part_name])
        self.part_frames.clear()
        self.part_tables.clear()
    
    def calculate_bid(self):
        vin = self.vin_entry.get().strip().upper()
        
        if not vin or len(vin) != 17:
            messagebox.showerror("Invalid VIN", "Please enter a valid 17-character VIN")
            return
        
        # Store current VIN for history
        self.current_vin = vin
        
        # Clear all tabs for new calculation
        self.clear_all_tabs()
        
        # Start with debug tab selected to show progress
        self.notebook.select(self.debug_frame)
        
        self.results_text.insert(tk.END, "Processing VIN...\n")
        self.root.update()
        
        vehicle_info = self.decode_vin(vin)
        if not vehicle_info:
            self.display_error("Could not decode VIN or retrieve vehicle information")
            return
        
        # Store vehicle info for AI analysis
        self.current_vehicle_info = vehicle_info
        
        self.results_text.insert(tk.END, f"Vehicle: {vehicle_info['year']} {vehicle_info['make']} {vehicle_info['model']}\n")
        self.results_text.insert(tk.END, "Searching for parts prices...\n")
        self.root.update()
        
        parts_prices = self.search_ebay_parts(vehicle_info)
        bid_analysis = self.calculate_recommended_bid(parts_prices)
        
        self.display_results(vehicle_info, parts_prices, bid_analysis)
    
    def display_results(self, vehicle_info: Dict, parts_prices: Dict[str, dict], bid_analysis: Dict):
        # Clear and populate the Final Output tab
        self.final_output_text.delete(1.0, tk.END)
        
        self.final_output_text.insert(tk.END, f"=== AUCTION BID ANALYSIS ===\n\n")
        
        # Display comprehensive vehicle information
        base_vehicle = f"{vehicle_info['year']} {vehicle_info['make']} {vehicle_info['model']}"
        self.final_output_text.insert(tk.END, f"Vehicle: {base_vehicle}")
        if vehicle_info.get('trim'):
            self.final_output_text.insert(tk.END, f" {vehicle_info['trim']}")
        self.final_output_text.insert(tk.END, f"\n")
        
        # Add vehicle specifications that affect parts compatibility
        spec_lines = []
        if vehicle_info.get('engine_displacement'):
            # Round engine displacement to nearest 10th for display
            try:
                displacement = float(vehicle_info['engine_displacement'])
                engine_info = f"{round(displacement, 1)}L"
            except (ValueError, TypeError):
                engine_info = vehicle_info['engine_displacement']
            if vehicle_info.get('engine_cylinders'):
                engine_info += f" ({vehicle_info['engine_cylinders']} cyl)"
            if vehicle_info.get('engine_designation'):
                engine_info += f" [Code: {vehicle_info['engine_designation']}]"
            spec_lines.append(f"Engine: {engine_info}")
        
        drive_line = ""
        if vehicle_info.get('drive_type'):
            drive_line = f"Drive: {vehicle_info['drive_type']}"
        
        fuel_body_line = ""
        fuel_body_parts = []
        if vehicle_info.get('fuel_type'):
            fuel_body_parts.append(f"Fuel: {vehicle_info['fuel_type']}")
        if vehicle_info.get('body_class'):
            fuel_body_parts.append(f"Body: {vehicle_info['body_class']}")
        if fuel_body_parts:
            fuel_body_line = " | ".join(fuel_body_parts)
        
        if spec_lines:
            specs_text = f"Specs: {' | '.join(spec_lines)}"
            if drive_line:
                specs_text += f" | {drive_line}"
            self.final_output_text.insert(tk.END, f"{specs_text}\n")
            if fuel_body_line:
                self.final_output_text.insert(tk.END, f"{fuel_body_line}\n")
        
        self.final_output_text.insert(tk.END, f"\n")
        
        # Display parts breakdown with pricing tiers and confidence
        self.final_output_text.insert(tk.END, f"{'Part':<20} {'Budget':<10} {'Standard':<10} {'Premium':<10} {'Confidence':<15}\n")
        self.final_output_text.insert(tk.END, f"{'Tier':<20} {'Tier':<10} {'Tier':<10} {'Tier':<10} {'Rating':<15}\n")
        self.final_output_text.insert(tk.END, "-" * 80 + "\n")
        
        # Define confidence display mapping
        confidence_display = {
            'dark_green': '🟢 High',
            'light_green': '🟢 Good', 
            'yellow': '🟡 Medium',
            'orange': '🟠 Low',
            'red': '🔴 Poor'
        }
        
        for part, prices in parts_prices.items():
            if isinstance(prices, dict):
                low = prices.get('low', 0)
                avg = prices.get('average', 0)
                high = prices.get('high', 0)
                confidence = prices.get('confidence_rating', 'yellow')
                confidence_text = confidence_display.get(confidence, '🟡 Unknown')
                self.final_output_text.insert(tk.END, f"{part.capitalize():<20} ${low:<9.2f} ${avg:<9.2f} ${high:<9.2f} {confidence_text:<15}\n")
            else:
                # Fallback for old format
                self.final_output_text.insert(tk.END, f"{part.capitalize():<20} ${prices:<9.2f} ${prices:<9.2f} ${prices:<9.2f} {'🟡 Legacy':<15}\n")
        
        # Display totals
        totals = bid_analysis['totals']
        bids = bid_analysis['bids']
        
        self.final_output_text.insert(tk.END, "-" * 80 + "\n")
        self.final_output_text.insert(tk.END, f"{'TOTALS:':<20} ${totals['low']:<9.2f} ${totals['average']:<9.2f} ${totals['high']:<9.2f}\n\n")
        
        # Display recommended bids based on pricing tiers
        self.final_output_text.insert(tk.END, "RECOMMENDED AUCTION BIDS (Dynamic Formula):\n")
        self.final_output_text.insert(tk.END, f"Budget-based bid:    ${bids['low']:.2f}  (if you expect lower-grade parts)\n")
        self.final_output_text.insert(tk.END, f"Standard bid:        ${bids['average']:.2f}  (typical market pricing)\n")
        self.final_output_text.insert(tk.END, f"Premium bid:         ${bids['high']:.2f}  (if vehicle is in great condition)\n\n")
        
        # Show confidence warnings and explanations
        confidence_warnings = []
        confidence_explanations = []
        
        for part, prices in parts_prices.items():
            if isinstance(prices, dict):
                confidence = prices.get('confidence_rating', 'yellow')
                confidence_explanation = prices.get('confidence_explanation', '')
                items_analyzed = prices.get('items_analyzed', 0)
                items_filtered = prices.get('items_filtered_out', 0)
                
                if confidence in ['orange', 'red']:
                    confidence_warnings.append(f"• {part.capitalize()}: {confidence_display.get(confidence, confidence)} confidence")
                
                if confidence_explanation and items_analyzed > 0:
                    confidence_explanations.append(f"• {part.capitalize()}: {confidence_explanation}")
        
        if confidence_warnings:
            self.final_output_text.insert(tk.END, "⚠️  CONFIDENCE WARNINGS:\n")
            for warning in confidence_warnings:
                self.final_output_text.insert(tk.END, f"{warning}\n")
            self.final_output_text.insert(tk.END, "\n")
        
        if confidence_explanations:
            self.final_output_text.insert(tk.END, "AI CONFIDENCE EXPLANATIONS:\n")
            for explanation in confidence_explanations:
                self.final_output_text.insert(tk.END, f"{explanation}\n")
            self.final_output_text.insert(tk.END, "\n")
        
        # Show which parts failed and why
        failed_parts = []
        for part, prices in parts_prices.items():
            if isinstance(prices, dict):
                if prices['low'] == 0 and prices['average'] == 0 and prices['high'] == 0:
                    failed_parts.append(part)
            elif prices == 0:
                failed_parts.append(part)
        
        if failed_parts:
            self.final_output_text.insert(tk.END, f"FAILED PARTS: {', '.join(failed_parts)}\n")
            self.final_output_text.insert(tk.END, "Check search terms or category IDs for these parts.\n\n")
        
        # Auto-scroll to top to show the final analysis
        self.final_output_text.see(1.0)
        
        # Also add debug info to the debug tab
        self.results_text.insert(tk.END, "\n" + "="*80 + "\n")
        self.results_text.insert(tk.END, f"=== PROCESSING COMPLETE ===\n")
        self.results_text.insert(tk.END, f"Found {len(parts_prices)} parts\n")
        self.results_text.insert(tk.END, f"eBay token exists: {bool(self.ebay_access_token)}\n")
        self.results_text.insert(tk.END, f"Client ID loaded: {bool(self.ebay_client_id)}\n")
        self.results_text.insert(tk.END, f"Client Secret loaded: {bool(self.ebay_client_secret)}\n")
        if failed_parts:
            self.results_text.insert(tk.END, f"FAILED PARTS: {', '.join(failed_parts)}\n")
        self.results_text.insert(tk.END, f"Results displayed in Final Output tab.\n")
        self.results_text.see(tk.END)
        
        # Save to VIN history
        self.add_to_vin_history(getattr(self, 'current_vin', ''), vehicle_info, parts_prices, bid_analysis)
        
        # Switch to the Final Output tab to show the results
        self.notebook.select(self.final_output_frame)
    
    def display_error(self, message: str):
        self.results_text.insert(tk.END, f"ERROR: {message}\n")

def main():
    root = tk.Tk()
    app = PhoenixAuctionAssistant(root)
    root.mainloop()

if __name__ == "__main__":
    main()