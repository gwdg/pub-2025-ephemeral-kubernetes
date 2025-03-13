import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import matplotlib.ticker as ticker

# Read the CSV file
df = pd.read_csv('deployment_times.csv')

# Calculate the average, median, and standard deviation for each stage
stages = ['Stage 1', 'Stage 2', 'Stage 3', 'Stage 4', 'Stage 5', 'Aggregated']
for stage in stages:
    avg = df[stage].mean()
    median = df[stage].median()
    std_dev = df[stage].std()
    print(f"Stage: {stage}")
    print(f"Average: {avg:.2f} seconds")
    print(f"Median: {median:.2f} seconds")
    print(f"Standard Deviation: {std_dev:.2f} seconds")
    print()

df.columns = ['First Node Booted', 'Leader File Created', 'Kubernetes Endpoint Responsive', 'Leader Ready File Created', 'Cluster Ready', 'Aggregated']

# Generate box diagrams with scatter plot
plt.figure(figsize=(10, 6))
sns.set_style("whitegrid")
sns.boxplot(data=df, showfliers=False)
sns.stripplot(data=df, jitter=True, size=3, edgecolor="black", linewidth=0.5)
#plt.title('Box Diagram of Deployment Times with Scatter Plot')
plt.xlabel('Deployment Stage')
plt.ylabel('Time (seconds)')
plt.xticks(rotation=15, ha='center')
plt.gca().yaxis.set_major_locator(ticker.MultipleLocator(10))  # label every 10 seconds
plt.gca().yaxis.set_minor_locator(ticker.MultipleLocator(5))  # draw a line every 5 seconds
plt.grid(axis='y', which='both', linestyle='-', linewidth=0.5)  # draw grid lines for both major and minor ticks
plt.tight_layout()
plt.savefig('box_diagram.png', bbox_inches='tight')
plt.show()
