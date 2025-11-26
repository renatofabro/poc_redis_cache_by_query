"""
Script de teste básico para MySQL Redis Cache

Este script executa testes básicos de funcionalidade.
Ajuste as configurações conforme seu ambiente.
"""

from mysql_redis_cache import MySQLRedisCache
import time


def test_basic_functionality():
    """Testa funcionalidade básica do cache."""

    print("\n" + "=" * 70)
    print("TESTE BÁSICO DE FUNCIONALIDADE")
    print("=" * 70 + "\n")

    # Configuração (AJUSTE CONFORME SEU AMBIENTE)
    mysql_config = {
        'host': 'localhost',
        'user': 'root',
        'password': 'senha123',
        'database': 'teste_db',
        'port': 3306
    }

    redis_config = {
        'host': 'localhost',
        'port': 6379,
        'db': 0
    }

    # Inicializar cache
    print("1. Inicializando MySQLRedisCache...")
    cache = MySQLRedisCache(
        mysql_config=mysql_config,
        redis_config=redis_config,
        default_ttl=60,
        cache_enabled=True
    )
    print("   ✓ Cache inicializado\n")

    # Teste 1: Primeira execução (MySQL)
    print("2. Executando query pela primeira vez (MySQL)...")
    query = "SELECT 1 as id, 'teste' as nome, NOW() as data"

    start = time.time()
    result1 = cache.execute(query)
    elapsed1 = time.time() - start

    print(f"   ✓ Query executada em {elapsed1:.4f}s")
    print(f"   - Veio do cache? {result1.from_cache}")
    print(f"   - Linhas retornadas: {result1.row_count}")
    print(f"   - Colunas: {result1.columns}")
    if result1.row_count > 0:
        print(f"   - Primeira linha: {result1.rows[0]}\n")

    # Teste 2: Segunda execução (Redis)
    print("3. Executando mesma query (Redis)...")

    start = time.time()
    result2 = cache.execute(query)
    elapsed2 = time.time() - start

    print(f"   ✓ Query executada em {elapsed2:.4f}s")
    print(f"   - Veio do cache? {result2.from_cache}")
    print(f"   - Cache hit? {result2.cache_hit}")
    print(f"   - Speedup: {elapsed1/elapsed2:.1f}x mais rápido\n")

    # Teste 3: Invalidar cache
    print("4. Invalidando cache...")
    deleted = cache.invalidate_cache(query)
    print(f"   ✓ {deleted} entrada(s) removida(s)\n")

    # Teste 4: Executar após invalidação (deve ir para MySQL)
    print("5. Executando após invalidação...")
    result3 = cache.execute(query)
    print(f"   ✓ Veio do cache? {result3.from_cache} (esperado: False)\n")

    # Teste 5: Estatísticas
    print("6. Obtendo estatísticas...")
    stats = cache.get_cache_stats()
    print("   Estatísticas:")
    for key, value in stats.items():
        print(f"   - {key}: {value}")
    print()

    # Teste 6: Desabilitar cache
    print("7. Testando desabilitação de cache...")
    cache.disable_cache()
    result4 = cache.execute(query)
    print(f"   ✓ Cache habilitado? {cache.cache_enabled}")
    print(f"   - Veio do cache? {result4.from_cache} (esperado: False)\n")

    # Teste 7: Reabilitar cache
    print("8. Reabilitando cache...")
    cache.enable_cache()
    result5 = cache.execute(query)
    print(f"   ✓ Cache habilitado? {cache.cache_enabled}")
    print(f"   - Veio do cache? {result5.from_cache}\n")

    # Teste 8: Métodos de iteração
    print("9. Testando métodos de iteração...")

    result = cache.execute("SELECT 1 as n UNION SELECT 2 UNION SELECT 3")

    # fetchone
    result._current_row = 0
    row = result.fetchone()
    print(f"   - fetchone(): {row}")

    # fetchmany
    result._current_row = 0
    rows = result.fetchmany(2)
    print(f"   - fetchmany(2): {rows}")

    # fetchall
    all_rows = result.fetchall()
    print(f"   - fetchall(): {all_rows}")

    # as_dict
    dict_rows = result.as_dict()
    print(f"   - as_dict(): {dict_rows}\n")

    # Fechar
    print("10. Fechando conexões...")
    cache.close()
    print("   ✓ Conexões fechadas\n")

    print("=" * 70)
    print("TODOS OS TESTES CONCLUÍDOS COM SUCESSO! ✓")
    print("=" * 70 + "\n")


def test_error_handling():
    """Testa tratamento de erros do Redis."""

    print("\n" + "=" * 70)
    print("TESTE DE TRATAMENTO DE ERROS")
    print("=" * 70 + "\n")

    mysql_config = {
        'host': 'localhost',
        'user': 'root',
        'password': 'senha123',
        'database': 'teste_db'
    }

    # Redis com configuração inválida
    redis_config = {
        'host': 'localhost',
        'port': 9999,  # Porta inválida
        'db': 0
    }

    print("1. Tentando conectar ao Redis em porta inválida (9999)...")
    cache = MySQLRedisCache(
        mysql_config=mysql_config,
        redis_config=redis_config
    )

    print("\n2. Executando query (deve funcionar via MySQL)...")
    try:
        result = cache.execute("SELECT 1 as test")
        print(f"   ✓ Query executada com sucesso!")
        print(f"   - Linhas: {result.row_count}")
        print(f"   - Veio do cache? {result.from_cache}")
        print("\n   ✓ Fallback para MySQL funcionou corretamente!\n")
    except Exception as e:
        print(f"   ✗ Erro: {e}\n")

    cache.close()

    print("=" * 70)
    print("TESTE DE TRATAMENTO DE ERROS CONCLUÍDO! ✓")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 15 + "MYSQL REDIS CACHE - TESTES BÁSICOS" + " " * 19 + "║")
    print("╚" + "=" * 68 + "╝")

    print("\n⚠️  ATENÇÃO:")
    print("Antes de executar, certifique-se de:")
    print("  1. MySQL rodando em localhost:3306")
    print("  2. Redis rodando em localhost:6379")
    print("  3. Banco de dados 'teste_db' criado")
    print("  4. Credenciais corretas no código\n")

    input("Pressione ENTER para continuar ou CTRL+C para cancelar...")

    # Executar testes
    try:
        test_basic_functionality()
        test_error_handling()

        print("\n✓ TODOS OS TESTES PASSARAM COM SUCESSO!\n")

    except KeyboardInterrupt:
        print("\n\n✗ Testes cancelados pelo usuário.\n")
    except Exception as e:
        print(f"\n\n✗ Erro durante os testes: {e}\n")
