"""
Exemplo de uso do MySQLRedisCache

Este exemplo demonstra todas as funcionalidades do módulo de cache.
"""

from mysql_redis_cache import MySQLRedisCache
import time


def main():
    """Função principal com exemplos de uso."""

    # ========================================
    # 1. CONFIGURAÇÃO
    # ========================================
    print("=" * 60)
    print("CONFIGURAÇÃO DO MYSQL REDIS CACHE")
    print("=" * 60)

    # Configuração do MySQL
    mysql_config = {
        'host': 'localhost',
        'user': 'root',
        'password': 'senha123',
        'database': 'teste_db',
        'port': 3306
    }

    # Configuração do Redis
    redis_config = {
        'host': 'localhost',
        'port': 6379,
        'db': 0,
        'decode_responses': False
    }

    # Inicializa o cache com TTL de 1 hora (3600 segundos)
    cache = MySQLRedisCache(
        mysql_config=mysql_config,
        redis_config=redis_config,
        default_ttl=3600,
        cache_enabled=True
    )

    print("✓ MySQLRedisCache inicializado\n")

    # ========================================
    # 2. EXECUTAR QUERY SELECT (PRIMEIRA VEZ - MYSQL)
    # ========================================
    print("=" * 60)
    print("EXEMPLO 1: PRIMEIRA EXECUÇÃO (BUSCA NO MYSQL)")
    print("=" * 60)

    query1 = "SELECT * FROM usuarios WHERE status = 'ativo' LIMIT 10"

    print(f"Query: {query1}")
    print("Executando pela primeira vez...\n")

    start = time.time()
    result1 = cache.execute(query1)
    elapsed = time.time() - start

    print(f"✓ Resultado: {result1}")
    print(f"  - Linhas retornadas: {result1.row_count}")
    print(f"  - Veio do cache? {result1.from_cache}")
    print(f"  - Tempo de execução: {elapsed:.4f}s")
    print(f"  - Colunas: {result1.columns}\n")

    # Exibir primeiras 3 linhas
    if result1.row_count > 0:
        print("Primeiras linhas:")
        for i, row in enumerate(result1.rows[:3]):
            print(f"  {i+1}. {row}")
        print()

    # ========================================
    # 3. EXECUTAR MESMA QUERY (CACHE HIT - REDIS)
    # ========================================
    print("=" * 60)
    print("EXEMPLO 2: SEGUNDA EXECUÇÃO (BUSCA NO REDIS)")
    print("=" * 60)

    print(f"Query: {query1}")
    print("Executando novamente (deve vir do cache)...\n")

    start = time.time()
    result2 = cache.execute(query1)
    elapsed = time.time() - start

    print(f"✓ Resultado: {result2}")
    print(f"  - Linhas retornadas: {result2.row_count}")
    print(f"  - Veio do cache? {result2.from_cache}")
    print(f"  - Cache hit? {result2.cache_hit}")
    print(f"  - Tempo de execução: {elapsed:.4f}s (muito mais rápido!)")
    print(f"  - Cached at: {result2.cached_at}\n")

    # ========================================
    # 4. USAR MÉTODOS DE ITERAÇÃO
    # ========================================
    print("=" * 60)
    print("EXEMPLO 3: MÉTODOS DE ITERAÇÃO")
    print("=" * 60)

    query2 = "SELECT id, nome, email FROM usuarios LIMIT 5"
    result3 = cache.execute(query2)

    print("Usando fetchone():")
    result3._current_row = 0  # Reset iterator
    row = result3.fetchone()
    if row:
        print(f"  Primeira linha: {row}\n")

    print("Usando fetchmany(2):")
    result3._current_row = 0  # Reset iterator
    rows = result3.fetchmany(2)
    for row in rows:
        print(f"  {row}")
    print()

    print("Usando fetchall():")
    all_rows = result3.fetchall()
    print(f"  Total de linhas: {len(all_rows)}\n")

    print("Usando as_dict():")
    dict_rows = result3.as_dict()
    if dict_rows:
        print(f"  Primeira linha como dict: {dict_rows[0]}\n")

    print("Iterando diretamente:")
    for i, row in enumerate(result3):
        print(f"  {i+1}. {row}")
    print()

    # ========================================
    # 5. QUERY NÃO-SELECT (NÃO CACHEIA)
    # ========================================
    print("=" * 60)
    print("EXEMPLO 4: QUERIES NÃO-SELECT (SEM CACHE)")
    print("=" * 60)

    # INSERT não será cacheado
    query_insert = "INSERT INTO usuarios (nome, email) VALUES ('João', 'joao@email.com')"
    print(f"Query INSERT: {query_insert}")
    print("  → INSERTs não são cacheados (esperado)\n")

    # UPDATE não será cacheado
    query_update = "UPDATE usuarios SET status = 'inativo' WHERE id = 1"
    print(f"Query UPDATE: {query_update}")
    print("  → UPDATEs não são cacheados (esperado)\n")

    # ========================================
    # 6. INVALIDAR CACHE
    # ========================================
    print("=" * 60)
    print("EXEMPLO 5: INVALIDAR CACHE")
    print("=" * 60)

    # Invalidar cache de query específica
    print(f"Invalidando cache da query: {query1}")
    deleted = cache.invalidate_cache(query1)
    print(f"✓ {deleted} entrada(s) removida(s) do cache\n")

    # Executar novamente - agora buscará do MySQL
    result4 = cache.execute(query1)
    print(f"Executando query novamente após invalidação:")
    print(f"  - Veio do cache? {result4.from_cache} (False = veio do MySQL)")
    print()

    # Invalidar TODOS os caches
    print("Invalidando TODOS os caches...")
    deleted = cache.invalidate_cache()
    print(f"✓ {deleted} entrada(s) removida(s) do cache\n")

    # ========================================
    # 7. AJUSTAR TTL
    # ========================================
    print("=" * 60)
    print("EXEMPLO 6: AJUSTAR TTL")
    print("=" * 60)

    # Executar query para cachear
    result5 = cache.execute(query2)
    print(f"Query executada e cacheada: {query2}")
    print(f"  - TTL padrão: {cache.default_ttl}s\n")

    # Ajustar TTL para 60 segundos
    new_ttl = 60
    success = cache.set_ttl(query2, new_ttl)
    print(f"Ajustando TTL para {new_ttl}s: {'✓ Sucesso' if success else '✗ Falha'}\n")

    # ========================================
    # 8. ESTATÍSTICAS DO CACHE
    # ========================================
    print("=" * 60)
    print("EXEMPLO 7: ESTATÍSTICAS DO CACHE")
    print("=" * 60)

    stats = cache.get_cache_stats()
    print("Estatísticas atuais do cache:")
    for key, value in stats.items():
        print(f"  - {key}: {value}")
    print()

    # ========================================
    # 9. DESABILITAR/HABILITAR CACHE
    # ========================================
    print("=" * 60)
    print("EXEMPLO 8: DESABILITAR/HABILITAR CACHE")
    print("=" * 60)

    # Desabilitar cache
    print("Desabilitando cache...")
    cache.disable_cache()
    result6 = cache.execute(query1)
    print(f"  - Cache habilitado? {cache.cache_enabled}")
    print(f"  - Veio do cache? {result6.from_cache}\n")

    # Habilitar cache novamente
    print("Habilitando cache...")
    cache.enable_cache()
    result7 = cache.execute(query1)
    print(f"  - Cache habilitado? {cache.cache_enabled}")
    print(f"  - Veio do cache? {result7.from_cache}\n")

    # ========================================
    # 10. FLUSH ALL (CUIDADO!)
    # ========================================
    print("=" * 60)
    print("EXEMPLO 9: FLUSH ALL (REMOVE TUDO DO REDIS)")
    print("=" * 60)

    print("ATENÇÃO: flush_all() remove TODOS os dados do Redis!")
    print("Descomente a linha abaixo para executar:\n")
    # cache.flush_all()
    print("# cache.flush_all()  # ← Descomente para executar\n")

    # ========================================
    # 11. TRATAMENTO DE ERROS DO REDIS
    # ========================================
    print("=" * 60)
    print("EXEMPLO 10: RESILIÊNCIA A FALHAS DO REDIS")
    print("=" * 60)

    print("Se o Redis falhar, o módulo continua funcionando normalmente")
    print("executando queries diretamente no MySQL.\n")
    print("Teste: Desligue o Redis e execute uma query.")
    print("Resultado: A query será executada no MySQL sem erros.\n")

    # ========================================
    # FECHAR CONEXÕES
    # ========================================
    print("=" * 60)
    print("FINALIZANDO")
    print("=" * 60)

    cache.close()
    print("✓ Conexões fechadas com sucesso\n")


def exemplo_uso_basico():
    """Exemplo minimalista de uso básico."""
    print("\n" + "=" * 60)
    print("EXEMPLO DE USO BÁSICO (MINIMALISTA)")
    print("=" * 60 + "\n")

    # Configuração
    mysql_config = {
        'host': 'localhost',
        'user': 'root',
        'password': 'senha123',
        'database': 'teste_db'
    }

    # Inicializar
    cache = MySQLRedisCache(mysql_config=mysql_config)

    # Executar query
    result = cache.execute("SELECT * FROM usuarios LIMIT 5")

    # Usar resultado
    print(f"Retornado {result.row_count} linhas")
    print(f"Veio do cache? {result.from_cache}")

    for row in result:
        print(row)

    # Fechar
    cache.close()


def exemplo_tratamento_erros():
    """Exemplo de tratamento de erros."""
    print("\n" + "=" * 60)
    print("EXEMPLO DE TRATAMENTO DE ERROS")
    print("=" * 60 + "\n")

    mysql_config = {
        'host': 'localhost',
        'user': 'root',
        'password': 'senha123',
        'database': 'teste_db'
    }

    # Redis com configuração inválida (vai falhar silenciosamente)
    redis_config = {
        'host': 'localhost',
        'port': 9999,  # Porta inválida
        'db': 0
    }

    cache = MySQLRedisCache(
        mysql_config=mysql_config,
        redis_config=redis_config
    )

    print("Tentando conectar ao Redis em porta inválida (9999)...")
    print("O módulo deve continuar funcionando, buscando do MySQL.\n")

    # Mesmo com Redis indisponível, a query funciona
    try:
        result = cache.execute("SELECT * FROM usuarios LIMIT 3")
        print(f"✓ Query executada com sucesso!")
        print(f"  - Linhas: {result.row_count}")
        print(f"  - Veio do cache? {result.from_cache}")
    except Exception as e:
        print(f"✗ Erro: {e}")

    cache.close()


if __name__ == "__main__":
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 10 + "MYSQL REDIS CACHE - EXEMPLOS DE USO" + " " * 13 + "║")
    print("╚" + "=" * 58 + "╝")
    print("\n")

    # Descomente o exemplo que deseja executar:

    # Exemplo completo com todas as funcionalidades
    # main()

    # Exemplo básico
    # exemplo_uso_basico()

    # Exemplo de tratamento de erros
    # exemplo_tratamento_erros()

    print("\n⚠️  ATENÇÃO:")
    print("Para executar os exemplos, descomente a função desejada")
    print("e ajuste as configurações de MySQL e Redis conforme seu ambiente.\n")
    print("Certifique-se de:")
    print("  1. Ter um servidor MySQL rodando")
    print("  2. Ter um servidor Redis rodando")
    print("  3. Ter um banco de dados 'teste_db' criado")
    print("  4. Ter uma tabela 'usuarios' com dados de exemplo\n")
