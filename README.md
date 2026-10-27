# 🛒 Controle de Mercado

Um sistema web para controle de preços de supermercado e lista de compras, focado em economia doméstica.

## 🎯 O que o sistema faz?
- Cadastro de mercados e produtos.
- Registro de preços históricos de cada produto em diferentes mercados.
- Lista de compras que mostra o menor preço encontrado para cada item.
- Dashboard com gráficos comparativos para mostrar onde você gasta menos.
- Interface adaptada para celular, com recursos de PWA.

## 🛠️ Tecnologias utilizadas
- **Python (Flask):** backend e rotas.
- **MySQL:** banco de dados relacional.
- **Bootstrap:** estilização e responsividade.
- **Chart.js:** gráficos interativos.
- **Ngrok:** pode ser usado para testes online.

## 🚀 Como rodar o projeto localmente
1. Clone este repositório.
2. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```
3. Crie o banco de dados `controle_mercado` no MySQL e prepare as tabelas `produtos`, `mercados` e `precos`, com as colunas utilizadas pelo aplicativo. O aplicativo cria a tabela `lista_compras` na inicialização.
4. Configure host, usuário, senha e nome do banco no dicionário `DB` em `app.py`. Não envie credenciais para o GitHub.
5. Inicie o aplicativo:
   ```bash
   python app.py
   ```
6. Abra `http://127.0.0.1:5000` no navegador.

## 📸 Screenshots
Adicione aqui uma captura do dashboard quando estiver disponível.

---
Desenvolvido por [Marco](https://github.com/resutmarcos)
