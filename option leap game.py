import tkinter as tk
from tkinter import messagebox, ttk
import datetime
import math
import numpy as np
import pandas as pd
from scipy.stats import norm
import yfinance as yf

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

# ---------------------------------------------------------
# BLACK-SCHOLES OPTIONS ENGINE
# ---------------------------------------------------------
def black_scholes_call(S, K, T, r, sigma):
    if T <= 0:
        return max(0.0, S - K)
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    call_price = S * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)
    return max(0.01, call_price)

# ---------------------------------------------------------
# APPLICATION CLASS
# ---------------------------------------------------------
class LeapGameGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("30-Year LEAPs Trading Simulator (with Margin & Physical Exercise)")
        self.root.geometry("1250x850")
        
        # Game Constants
        self.IV = 0.30
        self.R_FREE = 0.0
        
        # Game State Variables
        self.df = None
        self.ticker_symbol = ""
        self.current_wk_idx = 200  
        self.cash = 100000.0       # Can go negative if Margin Loan is utilized
        self.shares_owned = 0
        self.leaps_owned = []      # List of dicts: {'strike': K, 'qty': N, 'expiry_wk_idx': idx}
        
        self.setup_ticker_screen()

    def setup_ticker_screen(self):
        self.clear_screen()
        frame = ttk.Frame(self.root, padding=40)
        frame.pack(expand=True)
        
        ttk.Label(frame, text="Advanced LEAP Options Simulator", font=("Helvetica", 18, "bold")).pack(pady=10)
        ttk.Label(frame, text="Enter a stock ticker symbol (e.g., SPY, AAPL, QQQ):").pack(pady=5)
        
        self.ticker_entry = ttk.Entry(frame, font=("Helvetica", 12))
        self.ticker_entry.insert(0, "SPY")
        self.ticker_entry.pack(pady=5)
        self.ticker_entry.focus()
        
        btn = ttk.Button(frame, text="Load 30-Year Historical Data", command=self.load_data)
        btn.pack(pady=15)

    def load_data(self):
        self.ticker_symbol = self.ticker_entry.get().upper().strip()
        if not self.ticker_symbol:
            return
            
        try:
            ticker = yf.Ticker(self.ticker_symbol)
            daily_df = ticker.history(period="30y")
            if daily_df.empty:
                raise ValueError("No data returned from yfinance.")
                
            self.df = daily_df.resample('W-FRI').agg({
                'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'
            }).dropna()
            
            self.df['200W_MA'] = self.df['Close'].rolling(window=200).mean()
            
            self.current_wk_idx = 200
            if len(self.df) <= self.current_wk_idx + 104:
                messagebox.showerror("Error", "Ticker doesn't have enough history for a 30-year weekly game.")
                return
                
            self.setup_game_screen()
            
        except Exception as e:
            messagebox.showerror("Data Error", f"Could not retrieve data for {self.ticker_symbol}.\nError: {e}")

    def setup_game_screen(self):
        self.clear_screen()
        
        main_layout = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_layout.pack(fill=tk.BOTH, expand=True)
        
        left_panel = ttk.Frame(main_layout, padding=10, width=450)
        right_panel = ttk.Frame(main_layout, padding=10)
        
        main_layout.add(left_panel, weight=1)
        main_layout.add(right_panel, weight=2)
        
        # --- ACCOUNTS OVERVIEW ---
        self.lbl_date = ttk.Label(left_panel, font=("Helvetica", 12, "bold"))
        self.lbl_date.pack(anchor=tk.W, pady=2)
        self.lbl_spot = ttk.Label(left_panel, font=("Helvetica", 12, "bold"), foreground="green")
        self.lbl_spot.pack(anchor=tk.W, pady=2)
        
        ttk.Separator(left_panel, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=8)
        
        self.lbl_cash = ttk.Label(left_panel, text="Cash Balance: $100,000.00", font=("Helvetica", 11))
        self.lbl_cash.pack(anchor=tk.W, pady=1)
        self.lbl_margin = ttk.Label(left_panel, text="Margin Loan Utilized: $0.00", font=("Helvetica", 11, "italic"), foreground="orange")
        self.lbl_margin.pack(anchor=tk.W, pady=1)
        self.lbl_shares = ttk.Label(left_panel, text="Stock Value: 0 ($0.00)", font=("Helvetica", 11))
        self.lbl_shares.pack(anchor=tk.W, pady=1)
        self.lbl_options = ttk.Label(left_panel, text="Options Value: $0.00", font=("Helvetica", 11))
        self.lbl_options.pack(anchor=tk.W, pady=1)
        self.lbl_networth = ttk.Label(left_panel, text="Net Worth: $100,000.00", font=("Helvetica", 12, "bold"))
        self.lbl_networth.pack(anchor=tk.W, pady=4)
        
        ttk.Separator(left_panel, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=8)
        
        # --- ORDER BUY MANAGEMENT ---
        ttk.Label(left_panel, text="BUY / LONG TRANSACTIONS", font=("Helvetica", 11, "bold"), foreground="blue").pack(anchor=tk.W, pady=2)
        
        share_frame = ttk.Frame(left_panel)
        share_frame.pack(fill=tk.X, pady=3)
        ttk.Label(share_frame, text="Buy Shares:").pack(side=tk.LEFT)
        self.ent_stock_qty = ttk.Entry(share_frame, width=8)
        self.ent_stock_qty.insert(0, "0")
        self.ent_stock_qty.pack(side=tk.LEFT, padx=5)
        ttk.Button(share_frame, text="Execute Buy", command=self.buy_stock).pack(side=tk.LEFT)
        
        ttk.Label(left_panel, text="Select Strike Option (2-Yr LEAP):", font=("Helvetica", 9, "bold")).pack(anchor=tk.W, pady=(5, 1))
        self.strike_var = tk.StringVar(value="100%")
        self.strike_menu = ttk.Combobox(left_panel, textvariable=self.strike_var, values=["100%", "125%", "150%", "200%"], state="readonly")
        self.strike_menu.pack(fill=tk.X, pady=1)
        self.strike_menu.bind("<<ComboboxSelected>>", lambda e: self.update_order_pricing())
        
        self.lbl_option_cost = ttk.Label(left_panel, text="Premium: $0.00", font=("Helvetica", 9, "italic"))
        self.lbl_option_cost.pack(anchor=tk.W, pady=1)
        
        opt_qty_frame = ttk.Frame(left_panel)
        opt_qty_frame.pack(fill=tk.X, pady=3)
        ttk.Label(opt_qty_frame, text="Buy Contracts:").pack(side=tk.LEFT)
        self.ent_opt_qty = ttk.Entry(opt_qty_frame, width=8)
        self.ent_opt_qty.insert(0, "0")
        self.ent_opt_qty.pack(side=tk.LEFT, padx=5)
        ttk.Button(opt_qty_frame, text="Execute Buy", command=self.buy_options).pack(side=tk.LEFT)
        
        ttk.Separator(left_panel, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=8)
        
        # --- ORDER SELL MANAGEMENT ---
        ttk.Label(left_panel, text="SELL / LIQUIDATE TRANSACTIONS", font=("Helvetica", 11, "bold"), foreground="red").pack(anchor=tk.W, pady=2)
        
        sell_share_frame = ttk.Frame(left_panel)
        sell_share_frame.pack(fill=tk.X, pady=3)
        ttk.Label(sell_share_frame, text="Sell Shares:").pack(side=tk.LEFT)
        self.ent_sell_stock_qty = ttk.Entry(sell_share_frame, width=8)
        self.ent_sell_stock_qty.insert(0, "0")
        self.ent_sell_stock_qty.pack(side=tk.LEFT, padx=5)
        ttk.Button(sell_share_frame, text="Execute Sell", command=self.sell_stock).pack(side=tk.LEFT)
        
        sell_opt_frame = ttk.Frame(left_panel)
        sell_opt_frame.pack(fill=tk.X, pady=3)
        ttk.Label(sell_opt_frame, text="Sell Option Contracts (Oldest First):").pack(side=tk.LEFT)
        self.ent_sell_opt_qty = ttk.Entry(sell_opt_frame, width=6)
        self.ent_sell_opt_qty.insert(0, "0")
        self.ent_sell_opt_qty.pack(side=tk.LEFT, padx=5)
        ttk.Button(sell_opt_frame, text="Liquidate", command=self.sell_options).pack(side=tk.LEFT)
        
        ttk.Separator(left_panel, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=8)
        
        # --- POSITIONS INVENTORY ---
        ttk.Label(left_panel, text="Active Option Chains Inventory:", font=("Helvetica", 10, "bold")).pack(anchor=tk.W)
        self.txt_inventory = tk.Text(left_panel, height=6, width=50, font=("Courier", 9))
        self.txt_inventory.pack(fill=tk.BOTH, expand=True, pady=3)
        
        # --- TIME STEP BUTTON CONTROL ---
        btn_next = ttk.Button(left_panel, text="Advance 1 Month (4 Weeks) ➡️", command=self.advance_month)
        btn_next.pack(fill=tk.X, pady=8, ipady=4)
        
        # --- CHART PANEL ---
        self.fig = Figure(figsize=(7, 5), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=right_panel)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        self.update_ui()

    def get_market_context(self):
        row = self.df.iloc[self.current_wk_idx]
        return row['Close'], self.df.index[self.current_wk_idx]

    def get_selected_strike(self, spot):
        mult_map = {"100%": 1.0, "125%": 1.25, "150%": 1.50, "200%": 2.0}
        return spot * mult_map.get(self.strike_var.get(), 1.0)

    def update_order_pricing(self):
        spot, _ = self.get_market_context()
        strike = self.get_selected_strike(spot)
        premium = black_scholes_call(spot, strike, 2.0, self.R_FREE, self.IV)
        self.lbl_option_cost.config(text=f"Strike Target: ${strike:.2f} | Premium: ${premium:.2f}/contract value")

    def update_ui(self):
        spot, date_val = self.get_market_context()
        
        self.lbl_date.config(text=f"Current Date: {date_val.strftime('%Y-%m-%d')}")
        self.lbl_spot.config(text=f"{self.ticker_symbol} Spot Valuation: ${spot:.2f}")
        
        options_market_value = 0.0
        active_leaps = []
        
        self.txt_inventory.delete("1.0", tk.END)
        self.txt_inventory.insert(tk.END, f"{'Strike':<11}{'Qty':<6}{'TimeLeft':<12}{'Value':<12}\n")
        self.txt_inventory.insert(tk.END, "-"*41 + "\n")
        
        for leap in self.leaps_owned:
            remaining_weeks = leap['expiry_wk_idx'] - self.current_wk_idx
            T_remaining = max(0.0, remaining_weeks / 52.0)
            
            if T_remaining <= 0:
                # OPTION EXPIRED: PHYSICAL ASSIGNMENT TRIGGER
                if spot > leap['strike']:
                    exercise_cost = leap['strike'] * 100 * leap['qty']
                    shares_added = 100 * leap['qty']
                    
                    self.cash -= exercise_cost  # Can push cash negative -> Margin
                    self.shares_owned += shares_added
                    
                    msg = f"LEAP Expired ITM! Strike: ${leap['strike']:.2f}\n" \
                          f"Exercised {leap['qty']} contracts into +{shares_added} shares.\n" \
                          f"Cost Accounted: ${exercise_cost:,.2f}"
                    if self.cash < 0:
                        msg += f"\n\n⚠️ Margin utilized! Your cash balance is now negative."
                    messagebox.showinfo("Physical Exercise Assignment", msg)
                else:
                    messagebox.showinfo("Option Expired OTM", f"LEAP Strike ${leap['strike']:.2f} expired worthless out-of-the-money.")
            else:
                premium = black_scholes_call(spot, leap['strike'], T_remaining, self.R_FREE, self.IV)
                valuation = premium * 100 * leap['qty']
                options_market_value += valuation
                
                self.txt_inventory.insert(
                    tk.END, f"${leap['strike']:<10.2f}{leap['qty']:<6}{T_remaining:<12.2f}${valuation:,.2f}\n"
                )
                active_leaps.append(leap)
                
        self.leaps_owned = active_leaps
        
        shares_value = self.shares_owned * spot
        net_worth = self.cash + shares_value + options_market_value
        
        # Display separation between cash and margin lines
        if self.cash < 0:
            self.lbl_cash.config(text="Cash Balance: $0.00", foreground="black")
            self.lbl_margin.config(text=f"Margin Loan Utilized: ${abs(self.cash):,.2f}", foreground="red")
        else:
            self.lbl_cash.config(text=f"Cash Balance: ${self.cash:,.2f}", foreground="black")
            self.lbl_margin.config(text="Margin Loan Utilized: $0.00", foreground="gray")
            
        self.lbl_shares.config(text=f"Stock Shares Matrix: {self.shares_owned} (${shares_value:,.2f})")
        self.lbl_options.config(text=f"Options Valuation Matrix: ${options_market_value:,.2f}")
        self.lbl_networth.config(text=f"Total Portfolio Net Worth: ${net_worth:,.2f}")
        
        self.update_order_pricing()
        self.draw_chart()

    def draw_chart(self):
        self.ax.clear()
        start_idx = max(0, self.current_wk_idx - 104)
        subset_df = self.df.iloc[start_idx:self.current_wk_idx + 1]
        
        self.ax.plot(subset_df.index, subset_df['Close'], label="Weekly Close Price", color="blue")
        if '200W_MA' in subset_df.columns:
            self.ax.plot(subset_df.index, subset_df['200W_MA'], label="200-Week MA", color="crimson", linestyle="--")
            
        self.ax.set_title(f"{self.ticker_symbol} Rolling 2-Year Chart Window")
        self.ax.grid(True, alpha=0.3)
        self.ax.legend(loc="upper left")
        self.fig.autofmt_xdate()
        self.canvas.draw()

    def buy_stock(self):
        try:
            qty = int(self.ent_stock_qty.get() or 0)
            if qty <= 0: return
            spot, _ = self.get_market_context()
            cost = qty * spot
            
            # Note: We can allow buying directly on margin if desired, but here we restrict active cash buying to protect standard gameplay
            if cost > self.cash and self.cash > 0:
                if messagebox.askyesno("Margin Order", "This purchase exceeds liquid cash reserves. Use your Margin Line?"):
                    pass
                else: return
                
            self.cash -= cost
            self.shares_owned += qty
            self.ent_stock_qty.delete(0, tk.END)
            self.ent_stock_qty.insert(0, "0")
            self.update_ui()
        except ValueError:
            messagebox.showerror("Input Error", "Please provide a valid integer quantity.")

    def sell_stock(self):
        try:
            qty = int(self.ent_sell_stock_qty.get() or 0)
            if qty <= 0: return
            if qty > self.shares_owned:
                messagebox.showerror("Order Rejected", f"You only own {self.shares_owned} shares.")
                return
                
            spot, _ = self.get_market_context()
            proceeds = qty * spot
            self.cash += proceeds
            self.shares_owned -= qty
            
            self.ent_sell_stock_qty.delete(0, tk.END)
            self.ent_sell_stock_qty.insert(0, "0")
            self.update_ui()
        except ValueError:
            messagebox.showerror("Input Error", "Please provide a valid integer quantity.")

    def buy_options(self):
        try:
            qty = int(self.ent_opt_qty.get() or 0)
            if qty <= 0: return
            spot, _ = self.get_market_context()
            strike = self.get_selected_strike(spot)
            premium = black_scholes_call(spot, strike, 2.0, self.R_FREE, self.IV)
            total_cost = premium * 100 * qty
            
            if total_cost > self.cash and self.cash > 0:
                if not messagebox.askyesno("Margin Warning", "Use Margin allocation reserves to open this derivative contract?"):
                    return
            
            self.cash -= total_cost
            self.leaps_owned.append({
                'strike': strike, 'qty': qty, 'expiry_wk_idx': self.current_wk_idx + 104
            })
            self.ent_opt_qty.delete(0, tk.END)
            self.ent_opt_qty.insert(0, "0")
            self.update_ui()
        except ValueError:
            messagebox.showerror("Input Error", "Please provide a valid integer quantity.")

    def sell_options(self):
        try:
            qty_to_sell = int(self.ent_sell_opt_qty.get() or 0)
            if qty_to_sell <= 0: return
            
            total_contracts_owned = sum(l['qty'] for l in self.leaps_owned)
            if qty_to_sell > total_contracts_owned:
                messagebox.showerror("Order Rejected", "You don't own that many outstanding contracts.")
                return
                
            spot, _ = self.get_market_context()
            collected_proceeds = 0.0
            
            # FIFO (First In, First Out) Liquidation Process
            while qty_to_sell > 0 and len(self.leaps_owned) > 0:
                oldest_tranche = self.leaps_owned[0]
                remaining_weeks = oldest_tranche['expiry_wk_idx'] - self.current_wk_idx
                T_remaining = max(0.0, remaining_weeks / 52.0)
                premium = black_scholes_call(spot, oldest_tranche['strike'], T_remaining, self.R_FREE, self.IV)
                
                if oldest_tranche['qty'] <= qty_to_sell:
                    # Liquidate full contract position tranche
                    collected_proceeds += oldest_tranche['qty'] * premium * 100
                    qty_to_sell -= oldest_tranche['qty']
                    self.leaps_owned.pop(0)
                else:
                    # Liquidate partial contract position tranche
                    collected_proceeds += qty_to_sell * premium * 100
                    oldest_tranche['qty'] -= qty_to_sell
                    qty_to_sell = 0
                    
            self.cash += collected_proceeds
            self.ent_sell_opt_qty.delete(0, tk.END)
            self.ent_sell_opt_qty.insert(0, "0")
            self.update_ui()
        except ValueError:
            messagebox.showerror("Input Error", "Please provide a valid integer quantity.")

    def advance_month(self):
        if self.current_wk_idx + 4 >= len(self.df):
            messagebox.showinfo("Simulation Complete", "You have successfully traded across the 30-year history data window!")
            return
        self.current_wk_idx += 4
        self.update_ui()

    def clear_screen(self):
        for widget in self.root.winfo_children():
            widget.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = LeapGameGUI(root)
    root.mainloop()