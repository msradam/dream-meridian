# generate_tool_embeddings.py - Run once offline
from sentence_transformers import SentenceTransformer
import numpy as np
from spatial_tools_optimized import TOOLS_OPTIMIZED

print("Loading large embedding model (mpnet-base-v2)...")
embedder = SentenceTransformer('all-mpnet-base-v2')

print("Embedding tool descriptions...")
tool_descriptions = [t['function']['description'] for t in TOOLS_OPTIMIZED]
tool_embeddings = embedder.encode(tool_descriptions)

print(f"Embeddings shape: {tool_embeddings.shape}")  # (5, 768)

# Save embeddings
np.save('data/tool_embeddings_mpnet.npy', tool_embeddings)
print("✓ Saved tool embeddings to data/tool_embeddings_mpnet.npy")

# Also save which model was used
with open('data/embedding_model.txt', 'w') as f:
    f.write('all-mpnet-base-v2')

print("\nTool embeddings:")
for i, desc in enumerate(tool_descriptions):
    print(f"{i}: {desc[:60]}...")
