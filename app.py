import json
import os
from datetime import date
from decimal import Decimal
from html import escape

import mysql.connector
from dotenv import load_dotenv
from flask import Flask, redirect, render_template_string, request, send_from_directory, url_for

load_dotenv()

app = Flask(__name__)

DB = {
    "host": "localhost",
    "user": "root",
    "password": os.getenv("DB_PASSWORD"),
    "database": "controle_mercado",
}

NAV = """
<nav class="navbar navbar-expand-lg navbar-dark bg-success mb-4">
  <div class="container">
    <a class="navbar-brand" href="/">Controle de Mercado</a>
    <div class="navbar-nav ms-auto">
      <a class="nav-link" href="/">Dashboard</a>
      <a class="nav-link" href="/precos">Preços</a>
      <a class="nav-link" href="/mercados">Mercados</a>
      <a class="nav-link" href="/lista">Lista de compras</a>
    </div>
  </div>
</nav>
"""

BASE = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <link rel="manifest" href="/static/manifest.json">
  <link rel="icon" type="image/png" href="/static/favicon.png">
  <link rel="apple-touch-icon" href="/static/icon-192.png">
  <meta name="theme-color" content="#198754">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <title>{{ titulo }}</title>
  <style>
    body.bg-light {
      background-image:
        linear-gradient(rgba(0, 0, 0, 0.5), rgba(0, 0, 0, 0.5)),
        url("/static/fundo-escritorio.jpg");
      background-size: cover;
      background-position: center;
      background-attachment: fixed;
      background-repeat: no-repeat;
    }

    h1, h2 {
      color: #ffffff !important;
      text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.8);
      font-weight: bold;
    }
  </style>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
</head>
<body class="bg-light">
  """ + NAV + """
  <main class="container pb-5">
    {{ conteudo|safe }}
  </main>
  <script>
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.register('/service-worker.js')
        .catch(error => console.error('Falha ao registrar o service worker:', error));
    }
  </script>
</body>
</html>
"""


def get_conexao():
    return mysql.connector.connect(**DB)


def init_db():
    conexao = get_conexao()
    cursor = conexao.cursor()
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = 'mercados'
          AND COLUMN_NAME = 'ocultar_dashboard'
        """
    )
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            """
            ALTER TABLE mercados
            ADD COLUMN ocultar_dashboard TINYINT(1) NOT NULL DEFAULT 0
            """
        )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS lista_compras (
            id INT AUTO_INCREMENT PRIMARY KEY,
            produto_id INT NOT NULL,
            quantidade DECIMAL(10,2) NOT NULL DEFAULT 1,
            comprado TINYINT(1) NOT NULL DEFAULT 0,
            FOREIGN KEY (produto_id) REFERENCES produtos(id)
        )
        """
    )
    cursor.execute("SELECT COUNT(*) FROM lista_compras")
    if cursor.fetchone()[0] == 0:
        cursor.executemany(
            "INSERT INTO lista_compras (produto_id, quantidade, comprado) VALUES (%s, %s, %s)",
            [(1, 1, 0), (2, 2, 0), (3, 1, 0)],
        )
    conexao.commit()
    cursor.close()
    conexao.close()


def pagina(titulo, conteudo):
    return render_template_string(BASE, titulo=titulo, conteudo=conteudo)


@app.route("/static/manifest.json")
def manifest():
    return send_from_directory("static", "manifest.json")


@app.route("/service-worker.js")
def service_worker():
    return send_from_directory("static", "service-worker.js")


@app.route("/")
def dashboard():
    conexao = get_conexao()
    cursor = conexao.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT SUM(
            (SELECT MIN(preco) FROM precos WHERE produto_id = lc.produto_id)
            * lc.quantidade
        ) AS total_estimado
        FROM lista_compras lc
        WHERE lc.comprado = 0
        """
    )
    resultado_total = cursor.fetchone()
    total_estimado = resultado_total["total_estimado"] or 0

    cursor.execute(
        """
        SELECT m.id AS mercado_id, m.nome AS mercado,
               SUM(COALESCE(precos_produto.preco_min, 0) * lc.quantidade)
                   AS total_mercado
        FROM mercados m
        LEFT JOIN (
            SELECT mercado_id, produto_id, MIN(preco) AS preco_min
            FROM precos
            GROUP BY mercado_id, produto_id
        ) precos_produto ON precos_produto.mercado_id = m.id
        LEFT JOIN lista_compras lc
            ON lc.produto_id = precos_produto.produto_id
           AND lc.comprado = 0
        WHERE m.ocultar_dashboard = 0
        GROUP BY m.id, m.nome
        HAVING total_mercado > 0
        ORDER BY total_mercado ASC
        """
    )
    resumo_mercados = cursor.fetchall()

    labels_grafico = json.dumps(
        [r["mercado"] for r in resumo_mercados], ensure_ascii=False
    ).replace("<", "\\u003c")
    dados_grafico = json.dumps(
        [float(r["total_mercado"]) for r in resumo_mercados]
    )
    cores_grafico = json.dumps(
        ["#198754", "#fd7e14", "#0dcaf0", "#d63384", "#6f42c1"]
    )

    cursor.execute("SELECT id, nome FROM mercados ORDER BY nome")
    todos_mercados = cursor.fetchall()

    cursor.execute(
        """
        SELECT lc.id AS item_id, p.id AS produto_id, p.nome AS produto,
               lc.quantidade
        FROM lista_compras lc
        JOIN produtos p ON p.id = lc.produto_id
        WHERE lc.comprado = 0
        ORDER BY p.nome, lc.id
        """
    )
    itens_lista = cursor.fetchall()

    cursor.execute(
        """
        SELECT produto_id, mercado_id, MIN(preco) AS menor_preco
        FROM precos
        GROUP BY produto_id, mercado_id
        """
    )
    precos_mercados = cursor.fetchall()

    cursor.close()
    conexao.close()

    precos_por_produto = {}
    for preco in precos_mercados:
        precos_por_produto[(preco["produto_id"], preco["mercado_id"])] = (
            preco["menor_preco"]
        )

    th_mercados = "".join(
        f"<th>{escape(mercado['nome'])}</th>" for mercado in todos_mercados
    )
    linhas_tabela = []
    for item in itens_lista:
        celulas_precos = []
        precos_produto = [
            preco
            for (produto_id, _), preco in precos_por_produto.items()
            if produto_id == item["produto_id"] and preco is not None
        ]
        menor_preco_geral = min(precos_produto) if precos_produto else None

        for mercado in todos_mercados:
            preco = precos_por_produto.get((item["produto_id"], mercado["id"]))
            if preco is None:
                celulas_precos.append('<td class="text-muted">-</td>')
            elif preco == menor_preco_geral:
                celulas_precos.append(
                    f'<td class="table-success fw-bold text-success">'
                    f"R$ {float(preco):.2f}</td>"
                )
            else:
                celulas_precos.append(f"<td>R$ {float(preco):.2f}</td>")
        linhas_tabela.append(
            f"<tr><td class='text-start fw-bold'>{escape(item['produto'])}</td>"
            f"<td class='text-center'>{float(item['quantidade']):g}</td>"
            f"{''.join(celulas_precos)}</tr>"
        )

    if not linhas_tabela:
        linhas_tabela.append(
            '<tr><td colspan="100" class="text-center">'
            "Nenhum item na lista ou nenhum preço cadastrado.</td></tr>"
        )
    elif not todos_mercados:
        linhas_tabela = [
            '<tr><td colspan="2">Cadastre mercados para comparar os preços.</td></tr>'
        ]

    mensagem_grafico = (
        ""
        if resumo_mercados
        else '<p class="text-muted text-center">Nenhum mercado desmarcado com preços para comparar.</p>'
    )

    conteudo = f"""
    <h1 class="mb-4">Dashboard</h1>

    <div class="row mb-4">
      <div class="col-md-4 mb-3 mb-md-0">
        <div class="card shadow-sm border-0 h-100">
          <div class="card-body d-flex flex-column justify-content-center">
            <h5 class="text-muted mb-2">Total estimado da lista</h5>
            <h1 class="text-success fw-bold mb-0">R$ {total_estimado:.2f}</h1>
            <p class="text-muted small mt-2 mb-0">Itens ainda não comprados (quantidade × menor preço).</p>
          </div>
        </div>
      </div>

      <div class="col-md-8">
        <div class="card shadow-sm border-0 h-100">
          <div class="card-body">
            <h5 class="card-title mb-3">Onde você gasta menos (lista inteira)</h5>
            {mensagem_grafico}
            <div style="height: 200px;">
              <canvas id="graficoMercados"></canvas>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="card shadow-sm border-0">
      <div class="card-body">
        <h5 class="card-title mb-3">Comparativo de Preços (Apenas Itens da Lista)</h5>
        <div class="table-responsive">
          <table class="table table-hover align-middle mb-0">
            <thead class="table-dark">
              <tr>
                <th class="text-start">Produto</th>
                <th class="text-center">Qtd</th>
                {th_mercados}
              </tr>
            </thead>
            <tbody>
              {''.join(linhas_tabela)}
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <script>
        const ctx = document.getElementById('graficoMercados').getContext('2d');
        new Chart(ctx, {{
            type: 'bar',
            data: {{
                labels: {labels_grafico},
                datasets: [{{
                    label: 'Custo Total no Mercado (R$)',
                    data: {dados_grafico},
                    backgroundColor: {cores_grafico},
                    borderColor: '#333',
                    borderWidth: 1,
                    borderRadius: 6
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{ display: false }}
                }},
                scales: {{
                    y: {{
                        beginAtZero: true,
                        title: {{ display: true, text: 'Preço (R$)' }}
                    }}
                }}
            }}
        }});
    </script>
    """
    return pagina("Dashboard", conteudo)


@app.route("/precos", methods=["GET", "POST"])
def precos():
    mensagem = ""
    conexao = get_conexao()
    cursor = conexao.cursor(dictionary=True)

    if request.method == "POST":
        produto_id = request.form.get("produto_id")
        mercado_id = request.form.get("mercado_id")
        preco = request.form.get("preco")
        data_coleta = request.form.get("data_coleta") or date.today().isoformat()
        cursor.execute(
            """
            INSERT INTO precos (produto_id, mercado_id, preco, data_coleta)
            VALUES (%s, %s, %s, %s)
            """,
            (produto_id, mercado_id, preco, data_coleta),
        )
        conexao.commit()
        mensagem = '<div class="alert alert-success">Preço cadastrado.</div>'

    cursor.execute(
        """
        SELECT DISTINCT p.id, p.nome
        FROM produtos p
        JOIN lista_compras lc ON p.id = lc.produto_id
        WHERE lc.comprado = 0
        ORDER BY p.nome
        """
    )
    produtos = cursor.fetchall()
    cursor.execute("SELECT id, nome FROM mercados ORDER BY nome")
    mercados = cursor.fetchall()
    cursor.execute(
        """
        SELECT pr.id, p.nome AS produto, m.nome AS mercado, pr.preco, pr.data_coleta
        FROM precos pr
        JOIN produtos p ON p.id = pr.produto_id
        JOIN mercados m ON m.id = pr.mercado_id
        ORDER BY pr.data_coleta DESC, pr.id DESC
        """
    )
    historico = cursor.fetchall()
    cursor.close()
    conexao.close()

    opts_produtos = "".join(f'<option value="{p["id"]}">{p["nome"]}</option>' for p in produtos)
    opts_mercados = "".join(f'<option value="{m["id"]}">{m["nome"]}</option>' for m in mercados)
    linhas = "".join(
        f"<tr><td>{h['produto']}</td><td>{h['mercado']}</td>"
        f"<td>R$ {float(h['preco']):.2f}</td><td>{h['data_coleta']}</td></tr>"
        for h in historico
    ) or '<tr><td colspan="4">Nenhum preço cadastrado.</td></tr>'

    conteudo = f"""
    <h1 class="mb-4">Preços</h1>
    {mensagem}
    <div class="card shadow-sm mb-4">
      <div class="card-body">
        <h5 class="card-title">Cadastrar novo preço</h5>
        <form method="post" class="row g-3">
          <div class="col-md-4">
            <label class="form-label">Produto</label>
            <select name="produto_id" class="form-select" required>{opts_produtos}</select>
          </div>
          <div class="col-md-4">
            <label class="form-label">Mercado</label>
            <select name="mercado_id" class="form-select" required>{opts_mercados}</select>
          </div>
          <div class="col-md-2">
            <label class="form-label">Preço</label>
            <input type="number" step="0.01" min="0" name="preco" class="form-control" required>
          </div>
          <div class="col-md-2">
            <label class="form-label">Data</label>
            <input type="date" name="data_coleta" class="form-control" value="{date.today().isoformat()}">
          </div>
          <div class="col-12">
            <button type="submit" class="btn btn-success">Salvar</button>
          </div>
        </form>
      </div>
    </div>
    <div class="card shadow-sm">
      <div class="card-body">
        <h5 class="card-title">Histórico</h5>
        <table class="table table-striped mb-0">
          <thead><tr><th>Produto</th><th>Mercado</th><th>Preço</th><th>Data</th></tr></thead>
          <tbody>{linhas}</tbody>
        </table>
      </div>
    </div>
    """
    return pagina("Preços", conteudo)

@app.route("/lista", methods=["GET", "POST"])
def lista():
    conexao = get_conexao()
    cursor = conexao.cursor(dictionary=True)

    if request.method == "POST":
        item_id = request.form.get("item_id")
        comprado = 1 if request.form.get("comprado") == "on" else 0
        cursor.execute(
            "UPDATE lista_compras SET comprado = %s WHERE id = %s",
            (comprado, item_id),
        )
        conexao.commit()
        cursor.close()
        conexao.close()
        return redirect(url_for("lista"))

    cursor.execute(
        """
        SELECT lc.id, p.nome AS produto, lc.quantidade, lc.comprado,
               menor.preco_min,
               menor.preco_min * lc.quantidade AS subtotal
        FROM lista_compras lc
        JOIN produtos p ON p.id = lc.produto_id
        LEFT JOIN (
            SELECT produto_id, MIN(preco) AS preco_min
            FROM precos
            GROUP BY produto_id
        ) menor ON menor.produto_id = lc.produto_id
        ORDER BY lc.comprado, p.nome
        """
    )
    itens = cursor.fetchall()
    cursor.close()
    conexao.close()

    linhas = []
    for item in itens:
        checked = "checked" if item["comprado"] else ""
        if item["preco_min"] is not None:
            preco = (
                f"<strong>R$ {float(item['subtotal']):.2f}</strong>"
                f"<br><small class=\"text-muted\">"
                f"({float(item['quantidade']):g} x "
                f"R$ {float(item['preco_min']):.2f})</small>"
            )
        else:
            preco = "-"
        estilo = ' class="text-decoration-line-through text-muted"' if item["comprado"] else ""
        
        linhas.append(
            f"""
            <tr{estilo}>
              <td>
                <form method="post" class="m-0">
                  <input type="hidden" name="item_id" value="{item['id']}">
                  <input class="form-check-input" type="checkbox" name="comprado"
                         {checked} onchange="this.form.submit()">
                </form>
              </td>
              <td>{item['produto']}</td>
              <td>{float(item['quantidade']):g}</td>
              <td>{preco}</td>
              <td>
                <a href="/editar_item/{item['id']}" class="btn btn-sm btn-warning">✏️</a>
              </td>
            </tr>
            """
        )

    conteudo = f"""
    <div class="d-flex justify-content-between align-items-center mb-4">
        <h1 class="m-0">Lista de compras</h1>
        <a href="/adicionar_item" class="btn btn-success">+ Adicionar Item</a>
    </div>
    <div class="card shadow-sm">
      <div class="card-body">
        <p class="text-muted">Marque o item como comprado. O total do dashboard considera só o que ainda falta.</p>
        <table class="table align-middle mb-0">
          <thead>
            <tr><th>Comprado</th><th>Produto</th><th>Qtd</th><th>Subtotal (menor preço)</th><th>Ações</th></tr>
          </thead>
          <tbody>{''.join(linhas) or '<tr><td colspan="5">Lista vazia.</td></tr>'}</tbody>
        </table>
      </div>
    </div>
    """
    return pagina("Lista de compras", conteudo)

@app.route("/adicionar_item", methods=["GET", "POST"])
def adicionar_item():
    conexao = get_conexao()
    cursor = conexao.cursor(dictionary=True)

    if request.method == "POST":
        nome_produto = request.form.get("nome_produto", "").strip()
        quantidade = request.form.get("quantidade", 1)
        
        if nome_produto:
            # 1. Verifica se o produto já existe no banco
            cursor.execute("SELECT id FROM produtos WHERE nome = %s", (nome_produto,))
            produto = cursor.fetchone()
            
            if produto:
                produto_id = produto["id"]
            else:
                # 2. Se não existe, cadastra o novo produto e pega o ID gerado
                cursor.execute("INSERT INTO produtos (nome, categoria) VALUES (%s, 'Geral')", (nome_produto,))
                conexao.commit()
                produto_id = cursor.lastrowid

            # 3. Insere o item na lista de compras
            cursor.execute(
                "INSERT INTO lista_compras (produto_id, quantidade, comprado) VALUES (%s, %s, 0)",
                (produto_id, quantidade)
            )
            conexao.commit()
            
        cursor.close()
        conexao.close()
        return redirect(url_for("lista"))

    conteudo = """
    <h2 class="mb-4">Adicionar Item na Lista</h2>
    <div class="card shadow-sm">
      <div class="card-body">
        <form method="post">
          <div class="mb-3">
            <label class="form-label">Nome do Produto:</label>
            <input type="text" name="nome_produto" class="form-control" placeholder="Ex: Arroz 5kg, Sabão em pó..." required>
            <div class="form-text">Se o produto não existir, ele será cadastrado automaticamente.</div>
          </div>
          <div class="mb-3">
            <label class="form-label">Quantidade:</label>
            <input type="number" name="quantidade" class="form-control" value="1" min="1" required>
          </div>
          <button type="submit" class="btn btn-success">Salvar Item</button>
          <a href="/lista" class="btn btn-secondary">Cancelar</a>
        </form>
      </div>
    </div>
    """
    return pagina("Adicionar Item", conteudo)

@app.route("/editar_item/<int:id>", methods=["GET", "POST"])
def editar_item(id):
    conexao = get_conexao()
    cursor = conexao.cursor(dictionary=True)

    if request.method == "POST":
        quantidade = request.form.get("quantidade")
        acao = request.form.get("acao")
        
        if acao == "excluir":
            cursor.execute("DELETE FROM lista_compras WHERE id = %s", (id,))
        else:
            cursor.execute("UPDATE lista_compras SET quantidade = %s WHERE id = %s", (quantidade, id))
            
        conexao.commit()
        cursor.close()
        conexao.close()
        return redirect(url_for("lista"))

    cursor.execute("""
        SELECT lc.id, lc.quantidade, p.nome AS produto 
        FROM lista_compras lc 
        JOIN produtos p ON p.id = lc.produto_id 
        WHERE lc.id = %s
    """, (id,))
    item = cursor.fetchone()
    cursor.close()
    conexao.close()

    if not item:
        return "Item não encontrado na lista.", 404

    conteudo = f"""
    <h2 class="mb-4">Editar Item: {item['produto']}</h2>
    <div class="card shadow-sm">
      <div class="card-body">
        <form method="post">
          <div class="mb-3">
            <label class="form-label">Quantidade:</label>
            <input type="number" name="quantidade" class="form-control" value="{item['quantidade']}" min="1" required>
          </div>
          
          <button type="submit" name="acao" value="salvar" class="btn btn-primary">Salvar Alterações</button>
          
          <!-- Botão vermelho para excluir o item -->
          <button type="submit" name="acao" value="excluir" class="btn btn-danger" onclick="return confirm('Tem certeza que deseja excluir este item?')">Excluir</button>
          
          <a href="/lista" class="btn btn-secondary">Cancelar</a>
        </form>
      </div>
    </div>
    """
    return pagina(f"Editar {item['produto']}", conteudo)

@app.route("/mercados", methods=["GET", "POST"])
def mercados():
    conexao = get_conexao()
    cursor = conexao.cursor(dictionary=True)

    if request.method == "POST" and request.form.get("acao") == "salvar_comparacao":
        mercados_ocultos = set(request.form.getlist("ocultar_dashboard"))
        cursor.execute("SELECT id FROM mercados")
        ids_mercados = [mercado["id"] for mercado in cursor.fetchall()]
        if ids_mercados:
            cursor.executemany(
                "UPDATE mercados SET ocultar_dashboard = %s WHERE id = %s",
                [
                    (int(str(mercado_id) in mercados_ocultos), mercado_id)
                    for mercado_id in ids_mercados
                ],
            )
        conexao.commit()
        cursor.close()
        conexao.close()
        return redirect(url_for("mercados"))

    # Se o formulário foi enviado (POST), salva o novo mercado
    if request.method == "POST":
        nome_mercado = request.form.get("nome_mercado")
        if nome_mercado: # Evita salvar vazio
            cursor.execute("INSERT INTO mercados (nome) VALUES (%s)", (nome_mercado,))
            conexao.commit()
            cursor.close()
            conexao.close()
            return redirect(url_for("mercados"))

    # Se for GET, apenas mostra a lista de mercados cadastrados
    cursor.execute(
        "SELECT id, nome, ocultar_dashboard FROM mercados ORDER BY nome"
    )
    lista_mercados = cursor.fetchall()
    cursor.close()
    conexao.close()

    # Monta as linhas da tabela
    linhas = "".join(
        f"""
        <tr>
          <td>{m['id']}</td>
          <td>{escape(m['nome'])}</td>
          <td>
            <input class="form-check-input" type="checkbox"
                   name="ocultar_dashboard" value="{m['id']}"
                   aria-label="Ocultar {escape(m['nome'], quote=True)} do Dashboard"
                   onchange="this.form.requestSubmit()"
                   {"checked" if m["ocultar_dashboard"] else ""}>
          </td>
          <td>
            <a href="{url_for('editar_mercado', id=m['id'])}"
               class="btn btn-sm btn-warning" aria-label="Editar {escape(m['nome'], quote=True)}">✏️</a>
          </td>
        </tr>
        """
        for m in lista_mercados
    )

    # Monta o HTML da página
    conteudo = f"""
    <h2 class="mb-4">Gerenciar Mercados</h2>
    
    <div class="card shadow-sm mb-4">
      <div class="card-body">
        <h5 class="card-title">Cadastrar Novo Mercado</h5>
        <form method="post" class="d-flex gap-2">
          <input type="text" name="nome_mercado" class="form-control" placeholder="Ex: Pão de Açúcar, Atacadão..." required>
          <button type="submit" class="btn btn-success">Cadastrar</button>
        </form>
      </div>
    </div>

    <div class="card shadow-sm">
      <div class="card-body">
        <h5 class="card-title">Mercados Cadastrados</h5>
        <p class="text-muted">Mercados desmarcados aparecem no gráfico do Dashboard. A seleção é salva automaticamente.</p>
        <form method="post">
          <input type="hidden" name="acao" value="salvar_comparacao">
          <table class="table table-striped">
            <thead>
              <tr><th>ID</th><th>Nome do Mercado</th><th>Ocultar do Dashboard</th><th>Ações</th></tr>
            </thead>
            <tbody>
              {linhas if linhas else '<tr><td colspan="4">Nenhum mercado cadastrado.</td></tr>'}
            </tbody>
          </table>
        </form>
      </div>
    </div>
    """
    return pagina("Mercados", conteudo)


@app.route("/editar_mercado/<int:id>", methods=["GET", "POST"])
def editar_mercado(id):
    conexao = get_conexao()
    cursor = conexao.cursor(dictionary=True)
    mensagem = ""

    if request.method == "POST":
        acao = request.form.get("acao")
        if acao == "excluir":
            cursor.execute("DELETE FROM precos WHERE mercado_id = %s", (id,))
            cursor.execute("DELETE FROM mercados WHERE id = %s", (id,))
            conexao.commit()
            cursor.close()
            conexao.close()
            return redirect(url_for("mercados"))
        else:
            novo_nome = request.form.get("nome_mercado", "").strip()
            if novo_nome:
                cursor.execute(
                    "UPDATE mercados SET nome = %s WHERE id = %s",
                    (novo_nome, id),
                )
                conexao.commit()
                cursor.close()
                conexao.close()
                return redirect(url_for("mercados"))
            mensagem = (
                '<div class="alert alert-danger">Informe o nome do mercado.</div>'
            )

    cursor.execute("SELECT id, nome FROM mercados WHERE id = %s", (id,))
    mercado = cursor.fetchone()
    cursor.close()
    conexao.close()

    if not mercado:
        return "Mercado não encontrado.", 404

    nome_mercado = escape(mercado["nome"], quote=True)
    conteudo = f"""
    <h2 class="mb-4">Editar Mercado: {escape(mercado['nome'])}</h2>
    {mensagem}
    <div class="card shadow-sm">
      <div class="card-body">
        <form method="post">
          <div class="mb-3">
            <label class="form-label" for="nome_mercado">Nome do Mercado:</label>
            <input id="nome_mercado" type="text" name="nome_mercado"
                   class="form-control" value="{nome_mercado}" required>
          </div>
          <button type="submit" name="acao" value="salvar" class="btn btn-primary">
            Salvar Alterações
          </button>
          <button type="submit" name="acao" value="excluir" class="btn btn-danger"
                  onclick="return confirm('Tem certeza que deseja excluir este mercado?')">
            Excluir
          </button>
          <a href="{url_for('mercados')}" class="btn btn-secondary">Cancelar</a>
        </form>
      </div>
    </div>
    """
    return pagina(f"Editar {mercado['nome']}", conteudo)


init_db()

if __name__ == "__main__":
    app.run(debug=True)
