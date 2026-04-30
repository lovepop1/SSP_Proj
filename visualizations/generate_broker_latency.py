import matplotlib.pyplot as plt
import numpy as np
import os

# Data from Table Ib in report.latex
labels = ['Kafka (Disk)', 'RabbitMQ (RAM)']
p50 = [1209, 2.72]
p99 = [1756, 11.01]

x = np.arange(len(labels))
width = 0.35

# Modern styling
plt.style.use('ggplot')
fig, ax = plt.subplots(figsize=(8, 5))

rects1 = ax.bar(x - width/2, p50, width, label='P50 Latency', color='#3498db')
rects2 = ax.bar(x + width/2, p99, width, label='P99 Latency', color='#2ecc71')

ax.set_ylabel('Latency (ms) - Log Scale')
ax.set_title('Asynchronous Broker Latency Comparison')
ax.set_xticks(x)
ax.set_xticklabels(labels)
ax.legend()

# Use log scale to handle the 1000ms vs 2ms gap
ax.set_yscale('log')

def autolabel(rects):
    for rect in rects:
        height = rect.get_height()
        ax.annotate(f'{height}ms',
                    xy=(rect.get_x() + rect.get_width() / 2, height),
                    xytext=(0, 3), 
                    textcoords="offset points",
                    ha='center', va='bottom')

autolabel(rects1)
autolabel(rects2)

fig.tight_layout()

# Ensure figures directory exists
if not os.path.exists('figures'):
    os.makedirs('figures')

plt.savefig('figures/fig6_broker_latency.png', dpi=300)
print("Figure saved to figures/fig6_broker_latency.png")
