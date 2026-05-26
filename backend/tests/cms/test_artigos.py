import pytest

@pytest.mark.asyncio
async def test_criar_e_obter_artigo(client_admin):
    resp = await client_admin.post("/artigo", json= {
        "titulo": "Como calcular sua média",
        "conteudo": "descrição do processo...",
        "secao_id": 1,
        "status": "publicado",
    })
    assert resp.status_code == 201
    slug = resp.json()["slug"]

    resp = await client_admin.get(f"/artigos/{slug}")
    assert resp.status_code == 200
    assert resp.json()["titulo"] == "Como calcular sua média"