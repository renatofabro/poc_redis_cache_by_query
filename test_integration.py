"""
Teste de Integração Ponta a Ponta - MySQLRedisCache

Este teste executa um fluxo completo usando MySQL e Redis REAIS.

REQUISITOS:
- MySQL rodando em localhost:3306
- Redis rodando em localhost:6379
- Permissões para criar/dropar banco de dados

Execute com: python test_integration.py
"""

import sys
import time
import mysql.connector
from mysql_redis_cache import MySQLRedisCache


class IntegrationTest:
    """Teste de integração ponta a ponta."""

    def __init__(self):
        self.mysql_config = {
            'host': 'localhost',
            'user': 'root',
            'password': 'senha123',  # AJUSTE CONFORME SEU AMBIENTE
            'port': 3306
        }
        self.redis_config = {
            'host': 'localhost',
            'port': 6379,
            'db': 0
        }
        self.test_db = 'test_mysql_redis_cache'
        self.cache = None
        self.test_results = []

    def log(self, message, success=True):
        """Log de mensagem."""
        symbol = "✓" if success else "✗"
        print(f"  {symbol} {message}")
        self.test_results.append((message, success))

    def setup_database(self):
        """Cria banco de dados e tabelas de teste."""
        print("\n" + "=" * 70)
        print("SETUP: Criando banco de dados e tabelas")
        print("=" * 70)

        try:
            # Conecta sem database para criar o banco
            conn = mysql.connector.connect(
                host=self.mysql_config['host'],
                user=self.mysql_config['user'],
                password=self.mysql_config['password'],
                port=self.mysql_config['port']
            )
            cursor = conn.cursor()

            # Drop se existir
            cursor.execute(f"DROP DATABASE IF EXISTS {self.test_db}")
            self.log(f"Database {self.test_db} removido (se existia)")

            # Cria database
            cursor.execute(f"CREATE DATABASE {self.test_db}")
            self.log(f"Database {self.test_db} criado")

            cursor.close()
            conn.close()

            # Conecta ao database recém criado
            self.mysql_config['database'] = self.test_db
            conn = mysql.connector.connect(**self.mysql_config)
            cursor = conn.cursor()

            # Cria tabela usuarios
            cursor.execute("""
                CREATE TABLE usuarios (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    nome VARCHAR(100) NOT NULL,
                    email VARCHAR(100) NOT NULL,
                    status VARCHAR(20) DEFAULT 'ativo',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            self.log("Tabela 'usuarios' criada")

            # Cria tabela pedidos
            cursor.execute("""
                CREATE TABLE pedidos (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    total DECIMAL(10, 2) NOT NULL,
                    status VARCHAR(20) DEFAULT 'pendente',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES usuarios(id)
                )
            """)
            self.log("Tabela 'pedidos' criada")

            # Insere dados de teste
            cursor.execute("""
                INSERT INTO usuarios (nome, email, status) VALUES
                ('João Silva', 'joao@email.com', 'ativo'),
                ('Maria Santos', 'maria@email.com', 'ativo'),
                ('José Oliveira', 'jose@email.com', 'inativo'),
                ('Ana Costa', 'ana@email.com', 'ativo'),
                ('Pedro Souza', 'pedro@email.com', 'ativo')
            """)
            self.log("5 usuários inseridos")

            cursor.execute("""
                INSERT INTO pedidos (user_id, total, status) VALUES
                (1, 150.00, 'pago'),
                (1, 200.50, 'pendente'),
                (2, 75.00, 'pago'),
                (4, 300.00, 'pendente'),
                (5, 50.00, 'pago')
            """)
            self.log("5 pedidos inseridos")

            conn.commit()
            cursor.close()
            conn.close()

            self.log("Setup completo!", True)
            return True

        except Exception as e:
            self.log(f"Erro no setup: {e}", False)
            return False

    def teardown_database(self):
        """Remove banco de dados de teste."""
        print("\n" + "=" * 70)
        print("TEARDOWN: Removendo banco de dados de teste")
        print("=" * 70)

        try:
            conn = mysql.connector.connect(
                host=self.mysql_config['host'],
                user=self.mysql_config['user'],
                password=self.mysql_config['password'],
                port=self.mysql_config['port']
            )
            cursor = conn.cursor()
            cursor.execute(f"DROP DATABASE IF EXISTS {self.test_db}")
            self.log(f"Database {self.test_db} removido")
            cursor.close()
            conn.close()
            return True
        except Exception as e:
            self.log(f"Erro no teardown: {e}", False)
            return False

    def test_01_basic_select_cache(self):
        """Teste 1: Cache básico de SELECT."""
        print("\n" + "=" * 70)
        print("TESTE 1: Cache Básico de SELECT")
        print("=" * 70)

        try:
            query = "SELECT * FROM usuarios WHERE status = 'ativo'"

            # 1ª execução (MySQL)
            start = time.time()
            result1 = self.cache.execute(query)
            time1 = time.time() - start

            self.log(f"1ª execução: {result1.row_count} linhas em {time1:.4f}s")
            self.log(f"Veio do cache: {result1.from_cache} (esperado: False)", result1.from_cache is False)

            # 2ª execução (Redis)
            start = time.time()
            result2 = self.cache.execute(query)
            time2 = time.time() - start

            self.log(f"2ª execução: {result2.row_count} linhas em {time2:.4f}s")
            self.log(f"Veio do cache: {result2.from_cache} (esperado: True)", result2.from_cache is True)

            speedup = time1 / time2 if time2 > 0 else 0
            self.log(f"Speedup: {speedup:.1f}x mais rápido")

            return True
        except Exception as e:
            self.log(f"Erro: {e}", False)
            return False

    def test_02_table_tracking(self):
        """Teste 2: Rastreamento de Tabelas."""
        print("\n" + "=" * 70)
        print("TESTE 2: Rastreamento de Tabelas")
        print("=" * 70)

        try:
            # Executa queries em diferentes tabelas
            self.cache.execute("SELECT * FROM usuarios")
            self.cache.execute("SELECT * FROM pedidos")
            self.cache.execute("SELECT COUNT(*) FROM usuarios WHERE status = 'ativo'")

            # Verifica estatísticas
            stats = self.cache.get_cache_stats()

            self.log(f"Queries cacheadas: {stats['total_cached_queries']}")
            self.log(f"Tabelas rastreadas: {stats['total_tracked_tables']}")

            has_usuarios = 'usuarios' in stats.get('tracked_tables', {})
            has_pedidos = 'pedidos' in stats.get('tracked_tables', {})

            self.log(f"Tabela 'usuarios' rastreada: {has_usuarios}", has_usuarios)
            self.log(f"Tabela 'pedidos' rastreada: {has_pedidos}", has_pedidos)

            # Verifica queries de uma tabela
            usuario_queries = self.cache.get_table_queries('usuarios')
            self.log(f"Queries que usam 'usuarios': {len(usuario_queries)}")

            return True
        except Exception as e:
            self.log(f"Erro: {e}", False)
            return False

    def test_03_join_queries(self):
        """Teste 3: Queries com JOIN."""
        print("\n" + "=" * 70)
        print("TESTE 3: Queries com JOIN")
        print("=" * 70)

        try:
            query_join = """
                SELECT u.nome, u.email, p.total, p.status
                FROM usuarios u
                INNER JOIN pedidos p ON u.id = p.user_id
                WHERE u.status = 'ativo'
            """

            # 1ª execução
            result1 = self.cache.execute(query_join)
            self.log(f"Query JOIN executada: {result1.row_count} linhas")
            self.log(f"Veio do cache: {result1.from_cache} (esperado: False)", result1.from_cache is False)

            # 2ª execução (deve vir do cache)
            result2 = self.cache.execute(query_join)
            self.log(f"Query JOIN re-executada: {result2.row_count} linhas")
            self.log(f"Veio do cache: {result2.from_cache} (esperado: True)", result2.from_cache is True)

            # Verifica rastreamento de ambas as tabelas
            stats = self.cache.get_cache_stats()
            tracked = stats.get('tracked_tables', {})

            usuarios_tracked = 'usuarios' in tracked
            pedidos_tracked = 'pedidos' in tracked

            self.log(f"Tabela 'usuarios' rastreada: {usuarios_tracked}", usuarios_tracked)
            self.log(f"Tabela 'pedidos' rastreada: {pedidos_tracked}", pedidos_tracked)

            return True
        except Exception as e:
            self.log(f"Erro: {e}", False)
            return False

    def test_04_auto_invalidation_insert(self):
        """Teste 4: Invalidação Automática com INSERT."""
        print("\n" + "=" * 70)
        print("TESTE 4: Invalidação Automática - INSERT")
        print("=" * 70)

        try:
            # Cacheia query
            query = "SELECT * FROM usuarios WHERE status = 'ativo'"
            result1 = self.cache.execute(query)
            self.log(f"Query cacheada: {result1.row_count} linhas")

            # Verifica que está em cache
            result2 = self.cache.execute(query)
            self.log(f"Veio do cache: {result2.from_cache} (esperado: True)", result2.from_cache is True)

            # INSERT deve invalidar automaticamente
            insert_query = "INSERT INTO usuarios (nome, email, status) VALUES ('Novo User', 'novo@email.com', 'ativo')"
            self.cache.execute(insert_query)
            self.log("INSERT executado")

            # Próxima execução deve ir para MySQL
            result3 = self.cache.execute(query)
            self.log(f"Após INSERT - Veio do cache: {result3.from_cache} (esperado: False)", result3.from_cache is False)
            self.log(f"Dados atualizados: {result3.row_count} linhas (esperado: {result1.row_count + 1})",
                    result3.row_count == result1.row_count + 1)

            return True
        except Exception as e:
            self.log(f"Erro: {e}", False)
            return False

    def test_05_auto_invalidation_update(self):
        """Teste 5: Invalidação Automática com UPDATE."""
        print("\n" + "=" * 70)
        print("TESTE 5: Invalidação Automática - UPDATE")
        print("=" * 70)

        try:
            # Cacheia query
            query = "SELECT * FROM pedidos WHERE status = 'pendente'"
            result1 = self.cache.execute(query)
            self.log(f"Query cacheada: {result1.row_count} linhas pendentes")

            # Verifica cache
            result2 = self.cache.execute(query)
            self.log(f"Veio do cache: {result2.from_cache} (esperado: True)", result2.from_cache is True)

            # UPDATE deve invalidar
            update_query = "UPDATE pedidos SET status = 'pago' WHERE id = 2"
            self.cache.execute(update_query)
            self.log("UPDATE executado")

            # Deve buscar dados atualizados
            result3 = self.cache.execute(query)
            self.log(f"Após UPDATE - Veio do cache: {result3.from_cache} (esperado: False)", result3.from_cache is False)
            self.log(f"Dados atualizados: {result3.row_count} linhas (esperado: {result1.row_count - 1})",
                    result3.row_count == result1.row_count - 1)

            return True
        except Exception as e:
            self.log(f"Erro: {e}", False)
            return False

    def test_06_auto_invalidation_delete(self):
        """Teste 6: Invalidação Automática com DELETE."""
        print("\n" + "=" * 70)
        print("TESTE 6: Invalidação Automática - DELETE")
        print("=" * 70)

        try:
            # Cacheia query
            query = "SELECT * FROM usuarios WHERE status = 'inativo'"
            result1 = self.cache.execute(query)
            initial_count = result1.row_count
            self.log(f"Query cacheada: {initial_count} usuários inativos")

            # Verifica cache
            result2 = self.cache.execute(query)
            self.log(f"Veio do cache: {result2.from_cache} (esperado: True)", result2.from_cache is True)

            # DELETE deve invalidar
            delete_query = "DELETE FROM usuarios WHERE status = 'inativo' LIMIT 1"
            self.cache.execute(delete_query)
            self.log("DELETE executado")

            # Deve buscar dados atualizados
            result3 = self.cache.execute(query)
            self.log(f"Após DELETE - Veio do cache: {result3.from_cache} (esperado: False)", result3.from_cache is False)

            return True
        except Exception as e:
            self.log(f"Erro: {e}", False)
            return False

    def test_07_join_invalidation(self):
        """Teste 7: Invalidação de JOIN quando tabela é modificada."""
        print("\n" + "=" * 70)
        print("TESTE 7: Invalidação de JOIN")
        print("=" * 70)

        try:
            # Query JOIN
            query_join = """
                SELECT u.nome, COUNT(p.id) as total_pedidos
                FROM usuarios u
                LEFT JOIN pedidos p ON u.id = p.user_id
                GROUP BY u.id, u.nome
            """

            # Cacheia JOIN
            result1 = self.cache.execute(query_join)
            self.log(f"Query JOIN cacheada: {result1.row_count} linhas")

            # Verifica cache
            result2 = self.cache.execute(query_join)
            self.log(f"Veio do cache: {result2.from_cache} (esperado: True)", result2.from_cache is True)

            # UPDATE em uma das tabelas do JOIN
            self.cache.execute("UPDATE usuarios SET nome = 'Nome Atualizado' WHERE id = 1")
            self.log("UPDATE em tabela do JOIN executado")

            # JOIN deve ser invalidado
            result3 = self.cache.execute(query_join)
            self.log(f"Após UPDATE - Veio do cache: {result3.from_cache} (esperado: False)", result3.from_cache is False)

            return True
        except Exception as e:
            self.log(f"Erro: {e}", False)
            return False

    def test_08_manual_invalidation_by_table(self):
        """Teste 8: Invalidação Manual por Tabela."""
        print("\n" + "=" * 70)
        print("TESTE 8: Invalidação Manual por Tabela")
        print("=" * 70)

        try:
            # Cacheia múltiplas queries
            self.cache.execute("SELECT * FROM usuarios")
            self.cache.execute("SELECT * FROM pedidos")
            self.cache.execute("SELECT COUNT(*) FROM usuarios")

            stats_before = self.cache.get_cache_stats()
            self.log(f"Queries cacheadas antes: {stats_before['total_cached_queries']}")

            # Invalida apenas caches de 'usuarios'
            deleted = self.cache.invalidate_cache_by_table('usuarios')
            self.log(f"Caches de 'usuarios' invalidados: {deleted}")

            # Verifica que query de pedidos ainda está em cache
            result_pedidos = self.cache.execute("SELECT * FROM pedidos")
            self.log(f"Query de pedidos veio do cache: {result_pedidos.from_cache} (esperado: True)",
                    result_pedidos.from_cache is True)

            # Verifica que query de usuarios NÃO está em cache
            result_usuarios = self.cache.execute("SELECT * FROM usuarios")
            self.log(f"Query de usuarios veio do cache: {result_usuarios.from_cache} (esperado: False)",
                    result_usuarios.from_cache is False)

            return True
        except Exception as e:
            self.log(f"Erro: {e}", False)
            return False

    def test_09_result_methods(self):
        """Teste 9: Métodos de MySQLCacheResult."""
        print("\n" + "=" * 70)
        print("TESTE 9: Métodos de MySQLCacheResult")
        print("=" * 70)

        try:
            query = "SELECT id, nome, email FROM usuarios LIMIT 3"
            result = self.cache.execute(query)

            # fetchone
            result._current_row = 0
            row1 = result.fetchone()
            self.log(f"fetchone() retornou: {row1 is not None}", row1 is not None)

            # fetchmany
            result._current_row = 0
            rows = result.fetchmany(2)
            self.log(f"fetchmany(2) retornou 2 linhas: {len(rows) == 2}", len(rows) == 2)

            # fetchall
            all_rows = result.fetchall()
            self.log(f"fetchall() retornou {len(all_rows)} linhas: {len(all_rows) > 0}", len(all_rows) > 0)

            # as_dict
            dict_rows = result.as_dict()
            self.log(f"as_dict() retornou dicionários: {isinstance(dict_rows[0], dict)}", isinstance(dict_rows[0], dict))
            self.log(f"as_dict() tem chaves corretas: {'nome' in dict_rows[0]}", 'nome' in dict_rows[0])

            # Iteração
            count = 0
            for row in result:
                count += 1
            self.log(f"Iteração funcionou: {count == len(result)}", count == len(result))

            return True
        except Exception as e:
            self.log(f"Erro: {e}", False)
            return False

    def test_10_performance_comparison(self):
        """Teste 10: Comparação de Performance."""
        print("\n" + "=" * 70)
        print("TESTE 10: Comparação de Performance")
        print("=" * 70)

        try:
            # Query complexa
            query = """
                SELECT
                    u.id,
                    u.nome,
                    u.email,
                    COUNT(p.id) as total_pedidos,
                    SUM(p.total) as total_gasto
                FROM usuarios u
                LEFT JOIN pedidos p ON u.id = p.user_id
                GROUP BY u.id, u.nome, u.email
                ORDER BY total_gasto DESC
            """

            # 1ª execução (MySQL)
            start = time.time()
            result1 = self.cache.execute(query)
            time_mysql = time.time() - start

            self.log(f"Tempo MySQL: {time_mysql:.4f}s")

            # 2ª execução (Redis)
            start = time.time()
            result2 = self.cache.execute(query)
            time_redis = time.time() - start

            self.log(f"Tempo Redis: {time_redis:.4f}s")

            speedup = time_mysql / time_redis if time_redis > 0 else 0
            self.log(f"Speedup: {speedup:.1f}x mais rápido com cache")

            performance_improved = speedup > 1
            self.log(f"Cache melhorou performance: {performance_improved}", performance_improved)

            return True
        except Exception as e:
            self.log(f"Erro: {e}", False)
            return False

    def run_all_tests(self):
        """Executa todos os testes."""
        print("\n")
        print("╔" + "=" * 68 + "╗")
        print("║" + " " * 15 + "TESTE DE INTEGRAÇÃO PONTA A PONTA" + " " * 20 + "║")
        print("╚" + "=" * 68 + "╝")

        # Setup
        if not self.setup_database():
            print("\n✗ Falha no setup. Abortando testes.")
            return False

        # Inicializa cache
        try:
            self.cache = MySQLRedisCache(
                mysql_config=self.mysql_config,
                redis_config=self.redis_config,
                default_ttl=60
            )
            self.log("\nMySQLRedisCache inicializado")
        except Exception as e:
            print(f"\n✗ Erro ao inicializar cache: {e}")
            self.teardown_database()
            return False

        # Executa testes
        tests = [
            self.test_01_basic_select_cache,
            self.test_02_table_tracking,
            self.test_03_join_queries,
            self.test_04_auto_invalidation_insert,
            self.test_05_auto_invalidation_update,
            self.test_06_auto_invalidation_delete,
            self.test_07_join_invalidation,
            self.test_08_manual_invalidation_by_table,
            self.test_09_result_methods,
            self.test_10_performance_comparison,
        ]

        passed = 0
        failed = 0

        for test in tests:
            try:
                if test():
                    passed += 1
                else:
                    failed += 1
            except Exception as e:
                print(f"\n✗ Exceção no teste {test.__name__}: {e}")
                failed += 1

        # Teardown
        self.cache.close()
        self.teardown_database()

        # Resumo
        print("\n" + "=" * 70)
        print("RESUMO DOS TESTES")
        print("=" * 70)
        print(f"Total de testes: {len(tests)}")
        print(f"Passaram: {passed} ✓")
        print(f"Falharam: {failed} ✗")

        if failed == 0:
            print("\n🎉 TODOS OS TESTES PASSARAM COM SUCESSO! 🎉")
            return True
        else:
            print(f"\n⚠️  {failed} teste(s) falharam")
            return False


def main():
    """Função principal."""
    print("\n⚠️  ATENÇÃO:")
    print("Este teste requer:")
    print("  1. MySQL rodando em localhost:3306")
    print("  2. Redis rodando em localhost:6379")
    print("  3. Usuário 'root' com senha 'senha123' (ou ajuste no código)")
    print("  4. Permissões para criar/dropar banco de dados")
    print()

    response = input("Continuar? (s/N): ").strip().lower()
    if response != 's':
        print("Teste cancelado.")
        sys.exit(0)

    test = IntegrationTest()
    success = test.run_all_tests()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
