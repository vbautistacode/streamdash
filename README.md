# Streamdash

Aplicação de BI em Streamlit para integração com múltiplos ERPs.

## Estrutura
- `app/` → aplicação principal (dashboards, inputs, autenticação)
- `etl/` → pipelines de ETL (load, transform, write)
- `db/` → conexão e modelos de banco
- `tests/` → testes unitários

## Como rodar
```bash
pip install -r requirements.txt
streamlit run app/main.py
