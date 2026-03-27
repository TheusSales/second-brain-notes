---
titulo: "Introdução ao FastAPI"
resumo: "FastAPI é um framework moderno e de alta performance para construção de APIs com Python, baseado em type hints padrão do Python 3.6+."
tags:
  - python
  - api
  - web-development
flashcards:
  - q: "O que diferencia o FastAPI de outros frameworks Python?"
    a: "Validação automática via Pydantic, geração de docs OpenAPI e alto desempenho com Starlette/ASGI."
  - q: "Qual decorator é usado para criar uma rota POST no FastAPI?"
    a: "@app.post('/rota')"
  - q: "O que é Pydantic no contexto do FastAPI?"
    a: "Biblioteca de validação de dados que usa type hints para definir schemas e validar entradas automaticamente."
fonte: "https://fastapi.tiangolo.com"
date: 2026-03-26
---

# Introdução ao FastAPI

## O que é

**FastAPI** é um framework web moderno para construção de APIs com Python, criado por Sebastián Ramírez. Combina alta performance com uma excelente experiência de desenvolvimento.

## Características principais

- **Validação automática** — usa Pydantic para validar dados de entrada e saída com base em type hints
- **Documentação gerada** — gera automaticamente documentação interativa (Swagger UI e ReDoc)
- **Alta performance** — baseado em Starlette (ASGI) e Uvicorn, comparável ao Node.js e Go
- **Type hints** — aproveita os type hints do Python 3.6+ para inferência e validação

## Exemplo básico

```python
from fastapi import FastAPI

app = FastAPI()

@app.get("/items/{item_id}")
def read_item(item_id: int, q: str | None = None):
    return {"item_id": item_id, "q": q}
```

## Conexões com outras ideias

- Relacionado ao **Pydantic** para validação de dados
- Usa **Uvicorn** como servidor ASGI de produção
- Alternativa ao **Flask** e **Django REST Framework**
