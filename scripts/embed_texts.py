import torch
from transformers import AutoProcessor, AutoModel
from typing import List
import numpy as np
import hnswlib
import pickle
import sqlite3
from tqdm import tqdm
import time

def get_embeddings(abstracts: List[str], device: str = 'cpu') -> np.ndarray:
    """
    Generate normalized embeddings for a list of text abstracts using SigLIP
    
    Args:
        abstracts: List of text paragraphs to embed
        
    Returns:
        Numpy array of shape (num_abstracts, embedding_dim) with L2-normalized embeddings
    """
    embeddings = []
    
    batch_size = 1024  # You can adjust this based on your GPU memory
    for i in tqdm(range(0, len(abstracts), batch_size), desc="Processing batches"):
        batch_abstracts = abstracts[i:i + batch_size]
        
        # Process text (tokenization, padding, truncation)
        inputs = processor(
            text=batch_abstracts,
            return_tensors="pt",
            padding=True,
            truncation=True
        ).to(device)

        with torch.no_grad():
            text_embeds = model.get_text_features(**inputs)
            
            # Normalize embeddings for cosine similarity
            text_embeds = text_embeds / text_embeds.norm(p=2, dim=-1, keepdim=True)
            embeddings.append(text_embeds.cpu().numpy())  # Append directly to embeddings
    return np.vstack(embeddings)


def create_index(data: np.ndarray, ids: List[int]):
    num_elements, dim = data.shape

    # Declaring index
    p = hnswlib.Index(space = 'cosine', dim = dim) # possible options are l2, cosine or ip

    # Initializing index - the maximum number of elements should be known beforehand
    p.init_index(max_elements = num_elements, ef_construction = 200, M = 16)

    # Element insertion (can be called several times):
    print(f"Adding {len(ids)} items to index")
    p.add_items(data, ids)

    # Controlling the recall by setting ef:
    p.set_ef(50) # ef should always be > k

    # Index objects support pickling
    with open('index.pkl', 'wb') as f:
        pickle.dump(p, f)

# Example usage
if __name__ == "__main__":
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f"CUDA available: {torch.cuda.is_available()}, device: {device}")
    
    # Load model and processor
    model_id = "google/siglip-base-patch16-224"  # You can choose different sizes
    processor = AutoProcessor.from_pretrained(model_id)
    model = AutoModel.from_pretrained(model_id).to(device)  # Move model to GPU

    conn = sqlite3.connect('papers.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, summary FROM papers")
    abstracts = cursor.fetchall()

    # time embding generation
    start_time = time.monotonic()
    embeddings = get_embeddings([summary for _, summary in abstracts], device)
    end_time = time.monotonic()
    print(f"Embedding generation time: {end_time - start_time} seconds")

    create_index(embeddings, [id for id, _ in abstracts])

