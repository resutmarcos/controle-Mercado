import mysql.connector

try:
    conexao = mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="controle_mercado",
    )

    if conexao.is_connected():
        print("Conectado ao banco de dados com sucesso!")

        cursor = conexao.cursor()
        query = """
        SELECT p.nome AS Produto, m.nome AS Mercado, pr.preco AS Preco
        FROM precos pr
        JOIN produtos p ON pr.produto_id = p.id
        JOIN mercados m ON pr.mercado_id = m.id
        """

        cursor.execute(query)
        resultados = cursor.fetchall()

        print("\n--- Lista de Preços ---")
        for linha in resultados:
            print(f"Produto: {linha[0]} | Mercado: {linha[1]} | Preço: R$ {linha[2]}")

except mysql.connector.Error as erro:
    print(f"Erro ao conectar ou consultar: {erro}")
finally:
    if "conexao" in locals() and conexao.is_connected():
        cursor.close()
        conexao.close()
        print("\nConexão encerrada.")
