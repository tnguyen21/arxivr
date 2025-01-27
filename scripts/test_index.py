import pickle
import torch
from transformers import AutoProcessor, AutoModel
import sqlite3

processor = AutoProcessor.from_pretrained("google/siglip-base-patch16-224")
model = AutoModel.from_pretrained("google/siglip-base-patch16-224")

with open('index.pkl', 'rb') as f:
    index = pickle.load(f)

prompt = "neuroscience"

inputs = processor(
    text=prompt,
    return_tensors="pt",
    padding=True,
    truncation=True
)

with torch.no_grad():
    text_embeds = model.get_text_features(**inputs)
    text_embeds = text_embeds / text_embeds.norm(p=2, dim=-1, keepdim=True)

ids, dists = index.knn_query(text_embeds.squeeze().cpu().numpy(), k=10)

conn = sqlite3.connect('papers.db')
cursor = conn.cursor()
cursor.execute(f"SELECT title, summary FROM papers WHERE id IN ({','.join(map(str, ids[0]))})")
abstracts = cursor.fetchall()

for id, dist, abstract in zip(ids[0], dists[0], abstracts):
    print(f"ID: {id}, Distance: {dist}\nTitle: {abstract[0]}\nAbstract: {abstract[1][:300]}...\n\n")
