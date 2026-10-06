"""
Supply Chain Analytics Visualizations
Portfolio project demonstrating data visualization skills
Generates publication-quality charts for supply chain KPIs
"""

import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os
from pathlib import Path

# Set style for professional-looking charts
sns.set_style("whitegrid")
plt.rcParams['figure.figsize'] = (12, 6)
plt.rcParams['font.size'] = 10

# Connect to database
db_path = Path(__file__).parent.parent / 'supply_chain.db'
conn = sqlite3.connect(str(db_path))

# Create visualizations folder
viz_folder = Path(__file__).parent.parent / 'visualizations'
viz_folder.mkdir(exist_ok=True)

print("📊 Generating Supply Chain Visualizations...\n")

# ============================================================================
# VISUALIZATION 1: SUPPLIER PERFORMANCE SCORECARD
# ============================================================================
print("📈 Creating Supplier Performance Dashboard...")

query1 = """
SELECT
    s.supplier_name,
    COUNT(DISTINCT o.order_id) as total_orders,
    -- On-time measured against the ORDER promise date, over delivered shipments only.
    ROUND(SUM(CASE WHEN sh.actual_arrival_date IS NOT NULL AND sh.actual_arrival_date <= o.expected_delivery_date THEN 1 ELSE 0 END) * 100.0 / NULLIF(COUNT(sh.actual_arrival_date), 0), 2) as on_time_rate_pct,
    ROUND(SUM(o.order_cost), 2) as total_spend,
    s.quality_score,
    s.lead_time_days
FROM suppliers s
LEFT JOIN orders o ON s.supplier_id = o.supplier_id
LEFT JOIN shipments sh ON o.order_id = sh.order_id
GROUP BY s.supplier_id, s.supplier_name, s.quality_score, s.lead_time_days
ORDER BY on_time_rate_pct DESC
"""

df_supplier = pd.read_sql_query(query1, conn)

fig, axes = plt.subplots(2, 2, figsize=(15, 10))
fig.suptitle('Supplier Performance Scorecard', fontsize=16, fontweight='bold', y=0.995)

# On-Time Rate by Supplier
ax1 = axes[0, 0]
df_sorted = df_supplier.sort_values('on_time_rate_pct', ascending=True)
colors = ['#2ecc71' if x >= 80 else '#e74c3c' if x < 50 else '#f39c12' for x in df_sorted['on_time_rate_pct']]
ax1.barh(df_sorted['supplier_name'], df_sorted['on_time_rate_pct'], color=colors)
ax1.set_xlabel('On-Time Delivery Rate (%)')
ax1.set_title('On-Time Delivery Performance')
ax1.axvline(x=80, color='green', linestyle='--', alpha=0.5, label='Target: 80%')
ax1.legend()

# Total Spend by Supplier
ax2 = axes[0, 1]
df_spend = df_supplier.sort_values('total_spend', ascending=True)
ax2.barh(df_spend['supplier_name'], df_spend['total_spend'], color='#3498db')
ax2.set_xlabel('Total Spend ($)')
ax2.set_title('Total Procurement Spend by Supplier')
ax2.ticklabel_format(style='plain', axis='x')

# Quality Score vs On-Time Rate
ax3 = axes[1, 0]
scatter = ax3.scatter(df_supplier['quality_score'], df_supplier['on_time_rate_pct'],
                     s=df_supplier['total_spend']/100, alpha=0.6, c=df_supplier['on_time_rate_pct'],
                     cmap='RdYlGn', edgecolors='black', linewidth=1)
ax3.set_xlabel('Quality Score')
ax3.set_ylabel('On-Time Rate (%)')
ax3.set_title('Quality vs Delivery Performance (Size = Spend)')
ax3.grid(True, alpha=0.3)
for idx, row in df_supplier.iterrows():
    ax3.annotate(row['supplier_name'], (row['quality_score'], row['on_time_rate_pct']),
                fontsize=8, alpha=0.7)

# Orders per Supplier
ax4 = axes[1, 1]
df_orders = df_supplier.sort_values('total_orders', ascending=True)
ax4.barh(df_orders['supplier_name'], df_orders['total_orders'], color='#9b59b6')
ax4.set_xlabel('Number of Orders')
ax4.set_title('Order Volume by Supplier')

plt.tight_layout()
plt.savefig(viz_folder / '01_supplier_performance.png', dpi=300, bbox_inches='tight')
print("✅ Saved: 01_supplier_performance.png")
plt.close()

# ============================================================================
# VISUALIZATION 2: INVENTORY STATUS & REORDER ANALYSIS
# ============================================================================
print("📦 Creating Inventory Analysis...")

query2 = """
SELECT
    p.product_name,
    i.quantity_on_hand,
    i.quantity_reserved,
    (i.quantity_on_hand - i.quantity_reserved) as available_quantity,
    p.reorder_point,
    ROUND((i.quantity_on_hand - i.quantity_reserved) / p.reorder_point, 2) as coverage_ratio,
    CASE
        WHEN (i.quantity_on_hand - i.quantity_reserved) < p.reorder_point THEN 'REORDER URGENT'
        WHEN (i.quantity_on_hand - i.quantity_reserved) < p.reorder_point * 1.5 THEN 'REORDER SOON'
        ELSE 'OK'
    END as reorder_status
FROM products p
JOIN inventory i ON p.product_id = i.product_id
ORDER BY coverage_ratio ASC
"""

df_inventory = pd.read_sql_query(query2, conn)

fig, axes = plt.subplots(1, 2, figsize=(15, 6))
fig.suptitle('Inventory Optimization Analysis', fontsize=16, fontweight='bold')

# Reorder Status Distribution
ax1 = axes[0]
status_counts = df_inventory['reorder_status'].value_counts()
colors_status = {'REORDER URGENT': '#e74c3c', 'REORDER SOON': '#f39c12', 'OK': '#2ecc71'}
colors = [colors_status.get(status, '#95a5a6') for status in status_counts.index]
wedges, texts, autotexts = ax1.pie(status_counts.values, labels=status_counts.index, autopct='%1.1f%%',
                                     colors=colors, startangle=90)
ax1.set_title('Inventory Status Distribution')
for autotext in autotexts:
    autotext.set_color('white')
    autotext.set_fontweight('bold')

# Coverage Ratio by Product
ax2 = axes[1]
df_coverage = df_inventory.sort_values('coverage_ratio')
colors_coverage = ['#e74c3c' if x < 1 else '#f39c12' if x < 1.5 else '#2ecc71'
                   for x in df_coverage['coverage_ratio']]
ax2.barh(df_coverage['product_name'], df_coverage['coverage_ratio'], color=colors_coverage)
ax2.axvline(x=1, color='red', linestyle='--', alpha=0.5, label='Reorder Point')
ax2.axvline(x=1.5, color='orange', linestyle='--', alpha=0.5, label='Reorder Soon')
ax2.set_xlabel('Coverage Ratio (Available / Reorder Point)')
ax2.set_title('Inventory Coverage by Product')
ax2.legend()

plt.tight_layout()
plt.savefig(viz_folder / '02_inventory_analysis.png', dpi=300, bbox_inches='tight')
print("✅ Saved: 02_inventory_analysis.png")
plt.close()

# ============================================================================
# VISUALIZATION 3: SHIPPING MODE PERFORMANCE
# ============================================================================
print("🚚 Creating Shipping Performance Analysis...")

query3 = """
SELECT
    sh.shipping_mode,
    COUNT(sh.shipment_id) as total_shipments,
    ROUND(AVG(JULIANDAY(sh.actual_arrival_date) - JULIANDAY(sh.shipment_date)), 1) as avg_days_in_transit,
    ROUND(AVG(sh.shipping_cost), 2) as avg_shipping_cost,
    ROUND(SUM(sh.shipping_cost), 2) as total_shipping_spend,
    SUM(CASE WHEN sh.actual_arrival_date <= o.expected_delivery_date THEN 1 ELSE 0 END) as on_time_count,
    ROUND(SUM(CASE WHEN sh.actual_arrival_date <= o.expected_delivery_date THEN 1 ELSE 0 END) * 100.0 / COUNT(sh.shipment_id), 2) as on_time_pct
FROM shipments sh
JOIN orders o ON sh.order_id = o.order_id
WHERE sh.actual_arrival_date IS NOT NULL
GROUP BY sh.shipping_mode
ORDER BY on_time_pct DESC
"""

df_shipping = pd.read_sql_query(query3, conn)

fig, axes = plt.subplots(2, 2, figsize=(15, 10))
fig.suptitle('Shipping Mode Performance Analysis', fontsize=16, fontweight='bold', y=0.995)

# Cost vs Speed comparison
ax1 = axes[0, 0]
ax1.scatter(df_shipping['avg_days_in_transit'], df_shipping['avg_shipping_cost'],
           s=df_shipping['total_shipments']*30, alpha=0.6, c=df_shipping['on_time_pct'],
           cmap='RdYlGn', edgecolors='black', linewidth=2)
for idx, row in df_shipping.iterrows():
    ax1.annotate(row['shipping_mode'], (row['avg_days_in_transit'], row['avg_shipping_cost']),
                fontsize=10, fontweight='bold')
ax1.set_xlabel('Avg Days in Transit')
ax1.set_ylabel('Avg Shipping Cost ($)')
ax1.set_title('Cost vs Speed Trade-off (Size = Volume)')
ax1.grid(True, alpha=0.3)

# On-Time Performance by Mode
ax2 = axes[0, 1]
df_ship_sorted = df_shipping.sort_values('on_time_pct', ascending=True)
colors_ontime = ['#2ecc71' if x >= 80 else '#e74c3c' if x < 50 else '#f39c12'
                 for x in df_ship_sorted['on_time_pct']]
ax2.barh(df_ship_sorted['shipping_mode'], df_ship_sorted['on_time_pct'], color=colors_ontime)
ax2.set_xlabel('On-Time Rate (%)')
ax2.set_title('On-Time Performance by Shipping Mode')
ax2.axvline(x=80, color='green', linestyle='--', alpha=0.5)

# Total Spend by Mode
ax3 = axes[1, 0]
colors_modes = plt.cm.Set3(range(len(df_shipping)))
ax3.bar(df_shipping['shipping_mode'], df_shipping['total_shipping_spend'], color=colors_modes)
ax3.set_ylabel('Total Spend ($)')
ax3.set_title('Total Shipping Spend by Mode')
ax3.ticklabel_format(style='plain', axis='y')

# Shipment Volume by Mode
ax4 = axes[1, 1]
ax4.bar(df_shipping['shipping_mode'], df_shipping['total_shipments'], color=colors_modes)
ax4.set_ylabel('Number of Shipments')
ax4.set_title('Shipment Volume by Shipping Mode')

plt.tight_layout()
plt.savefig(viz_folder / '03_shipping_performance.png', dpi=300, bbox_inches='tight')
print("✅ Saved: 03_shipping_performance.png")
plt.close()

# ============================================================================
# VISUALIZATION 4: COST VARIANCE ANALYSIS
# ============================================================================
print("💰 Creating Cost Variance Analysis...")

query4 = """
SELECT
    s.supplier_name,
    COUNT(DISTINCT o.order_id) as order_count,
    SUM(o.order_cost) as actual_total_spend,
    SUM(o.quantity_ordered * p.unit_cost) as planned_total_cost,
    ROUND(SUM(o.order_cost) - SUM(o.quantity_ordered * p.unit_cost), 2) as cost_variance,
    ROUND((SUM(o.order_cost) - SUM(o.quantity_ordered * p.unit_cost)) / SUM(o.quantity_ordered * p.unit_cost) * 100, 2) as variance_pct
FROM orders o
JOIN suppliers s ON o.supplier_id = s.supplier_id
JOIN products p ON o.product_id = p.product_id
GROUP BY s.supplier_id, s.supplier_name
HAVING COUNT(DISTINCT o.order_id) > 0
ORDER BY variance_pct DESC
"""

df_variance = pd.read_sql_query(query4, conn)

fig, axes = plt.subplots(1, 2, figsize=(15, 6))
fig.suptitle('Cost Variance Analysis (Actual vs Planned)', fontsize=16, fontweight='bold')

# Variance % by Supplier
ax1 = axes[0]
df_var_sorted = df_variance.sort_values('variance_pct')
colors_var = ['#e74c3c' if x > 0 else '#2ecc71' for x in df_var_sorted['variance_pct']]
ax1.barh(df_var_sorted['supplier_name'], df_var_sorted['variance_pct'], color=colors_var)
ax1.set_xlabel('Cost Variance (%)')
ax1.set_title('Cost Performance vs Plan')
ax1.axvline(x=0, color='black', linestyle='-', alpha=0.3)

# Actual vs Planned Spend
ax2 = axes[1]
x = range(len(df_variance))
width = 0.35
ax2.bar([i - width/2 for i in x], df_variance['planned_total_cost'], width, label='Planned', color='#3498db', alpha=0.8)
ax2.bar([i + width/2 for i in x], df_variance['actual_total_spend'], width, label='Actual', color='#e74c3c', alpha=0.8)
ax2.set_ylabel('Total Spend ($)')
ax2.set_title('Planned vs Actual Spend by Supplier')
ax2.set_xticks(x)
ax2.set_xticklabels(df_variance['supplier_name'], rotation=45, ha='right')
ax2.legend()
ax2.ticklabel_format(style='plain', axis='y')

plt.tight_layout()
plt.savefig(viz_folder / '04_cost_variance.png', dpi=300, bbox_inches='tight')
print("✅ Saved: 04_cost_variance.png")
plt.close()

# ============================================================================
# SUMMARY STATISTICS
# ============================================================================
print("\n" + "="*70)
print("📊 SUPPLY CHAIN ANALYTICS SUMMARY")
print("="*70)

print(f"\n👥 SUPPLIER METRICS:")
print(f"   • Total Suppliers: {len(df_supplier)}")
print(f"   • Avg On-Time Rate (unweighted across suppliers): {df_supplier['on_time_rate_pct'].mean():.1f}%")
print(f"   • Total Procurement Spend: ${df_supplier['total_spend'].sum():,.2f}")
print(f"   • Best Performer: {df_supplier.iloc[0]['supplier_name']} ({df_supplier.iloc[0]['on_time_rate_pct']:.1f}% on-time)")

print(f"\n📦 INVENTORY METRICS:")
urgent = len(df_inventory[df_inventory['reorder_status'] == 'REORDER URGENT'])
soon = len(df_inventory[df_inventory['reorder_status'] == 'REORDER SOON'])
ok = len(df_inventory[df_inventory['reorder_status'] == 'OK'])
print(f"   • Total SKUs: {len(df_inventory)}")
print(f"   • Urgent Reorders: {urgent} items")
print(f"   • Reorder Soon: {soon} items")
print(f"   • Inventory Health: {ok} items OK")

print(f"\n🚚 SHIPPING METRICS:")
print(f"   • Shipping Modes: {len(df_shipping)}")
_tot = df_shipping['total_shipments'].sum()
print(f"   • Overall On-Time (shipment-weighted): {df_shipping['on_time_count'].sum() / _tot * 100:.1f}%")
best_mode = df_shipping.loc[df_shipping['on_time_pct'].idxmax()]
print(f"   • Best Performing Mode: {best_mode['shipping_mode']} ({best_mode['on_time_pct']:.1f}% on-time)")
print(f"   • Total Shipping Spend: ${df_shipping['total_shipping_spend'].sum():,.2f}")
print(f"   • Avg Transit Time: {df_shipping['avg_days_in_transit'].mean():.1f} days")

print(f"\n💰 COST METRICS:")
print(f"   • Total Variance: ${df_variance['cost_variance'].sum():,.2f}")
print(f"   • Avg Variance %: {df_variance['variance_pct'].mean():.2f}%")
best_cost = df_variance.loc[df_variance['variance_pct'].idxmin()]
worst_cost = df_variance.loc[df_variance['variance_pct'].idxmax()]
print(f"   • Best Cost Control: {best_cost['supplier_name']} ({best_cost['variance_pct']:.2f}%)")
print(f"   • Highest Variance: {worst_cost['supplier_name']} ({worst_cost['variance_pct']:.2f}%)")

print("\n" + "="*70)
print("✅ All visualizations created successfully!")
print(f"📁 Visualizations saved to: {viz_folder}")
print("="*70 + "\n")

conn.close()
