import os

import mysql.connector
from dotenv import load_dotenv

load_dotenv()


def main():
    conexao = None
    cursor = None
    try:
        conexao = mysql.connector.connect(
            host="localhost",
            user="root",
            password=os.getenv("DB_PASSWORD"),
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
                print(
                    f"Produto: {linha[0]} | Mercado: {linha[1]} | "
                    f"Preço: R$ {linha[2]}"
                )

    except mysql.connector.Error as erro:
        print(f"Erro ao conectar ou consultar: {erro}")
    finally:
        if cursor is not None:
            cursor.close()
        if conexao is not None and conexao.is_connected():
            conexao.close()
            print("\nConexão encerrada.")


if __name__ == "__main__":
    main()
