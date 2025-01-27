# archivr

## TODO?

- embed all abstracts
  - add ann search (hnswlib)
  - should i use voyageai? or small local text emb model?
- support natural language queries -- vector similarity search on things like "dl on games" or something like that
- search by vector similarity threshold (only cos sim)
- daily paper ingest
- email notifcations of new papers on vectory similarity
  - or category (just API feature around it instaed of manaul email like arxiv)
- save abstracts with notes
  - in email reports of new papers, have LLM summarize new paper/how paper relates to other saved papers?
  - or save off natural language queries and alert on papers that pass similarity threshold on natural lang query
    - again, with small summary on how it might relate to query?

inspired by [arxiv-sanity-lite](https://github.com/karpathy/arxiv-sanity-lite)
