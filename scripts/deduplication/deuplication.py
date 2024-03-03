import rdflib
import dedupe
import sys

input_file = sys.argv[1]
output_file = sys.argv[2]

print("Starting deduplication for file" + input_file)

# Parse the Turtle content into an RDF graph
graph = rdflib.Graph()
graph.parse(input_file, format="turtle")

data = {}
for i, (s, p, o) in enumerate(graph):
    # Use a unique identifier (e.g., a simple counter) as the key
    data[i] = {"subject": str(s), "predicate": str(p), "object": str(o)}

# Define the fields Dedupe will use
fields = [
    {"field": "subject", "type": "String"},
    {"field": "predicate", "type": "String"},
    {"field": "object", "type": "String"}
]

# Create a new Deduper instance
deduper = dedupe.Dedupe(fields)

# Prepare data for training
deduper.prepare_training(data)

# Active learning loop to train the deduper
print('Starting active labeling...')
dedupe.console_label(deduper)

# Train the deduper
deduper.train()

# Find duplicates
print('Finding duplicates...')
clustered_dupes = deduper.partition(data, threshold=0.5)

# Deduplication - Collect unique identifiers of non-duplicate entities
unique_ids = set()
print("Collecting unique statements")

for (record_ids, _) in clustered_dupes:
    for record_id in record_ids:
        unique_ids.add(record_id)
        break

# Rebuild the graph with non-duplicate entities
cleaned_graph = rdflib.Graph()
for uid in unique_ids:
    s, p, o = data[uid]['subject'], data[uid]['predicate'], data[uid]['object']
    cleaned_graph.add((rdflib.URIRef(s), rdflib.URIRef(p), rdflib.Literal(o)))

print(f"Writing deduplicated graph to {output_file}")
cleaned_graph.serialize(destination=output_file, format='turtle')

