"""
Exemplo de Rastreamento de Tabelas e Invalidação Automática

Este exemplo demonstra como o sistema rastreia tabelas e invalida
automaticamente caches quando há INSERT/UPDATE/DELETE,
especialmente importante para queries com JOINs.
"""

from mysql_redis_cache import MySQLRedisCache
import time


def main():
    """Demonstração de rastreamento de tabelas e invalidação automática."""

    print("\n" + "=" * 70)
    print("RASTREAMENTO DE TABELAS E INVALIDAÇÃO AUTOMÁTICA")
    print("=" * 70 + "\n")

    # Configuração
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

    cache = MySQLRedisCache(
        mysql_config=mysql_config,
        redis_config=redis_config,
        default_ttl=3600
    )

    print("✓ MySQLRedisCache inicializado\n")

    # ========================================
    # CENÁRIO 1: QUERY COM JOIN
    # ========================================
    print("=" * 70)
    print("CENÁRIO 1: QUERY COM JOIN (MÚLTIPLAS TABELAS)")
    print("=" * 70 + "\n")

    # Query com JOIN envolvendo 'usuarios' e 'pedidos'
    query_join = """
        SELECT u.id, u.nome, p.total
        FROM usuarios u
        INNER JOIN pedidos p ON u.id = p.user_id
        WHERE u.status = 'ativo'
        LIMIT 10
    """

    print("Executando query com JOIN:")
    print(f"  {query_join.strip()}\n")

    result1 = cache.execute(query_join)
    print(f"✓ Query executada")
    print(f"  - Veio do cache? {result1.from_cache}")
    print(f"  - Linhas retornadas: {result1.row_count}\n")

    # ========================================
    # CENÁRIO 2: VERIFICAR RASTREAMENTO
    # ========================================
    print("=" * 70)
    print("CENÁRIO 2: VERIFICAR RASTREAMENTO DE TABELAS")
    print("=" * 70 + "\n")

    # Executar mais queries para popular o cache
    query_usuarios = "SELECT * FROM usuarios WHERE status = 'ativo'"
    query_pedidos = "SELECT * FROM pedidos WHERE status = 'pendente'"

    print("Executando mais queries...")
    cache.execute(query_usuarios)
    cache.execute(query_pedidos)
    print("✓ Queries adicionais executadas\n")

    # Obter estatísticas
    print("Estatísticas do cache:")
    stats = cache.get_cache_stats()
    print(f"  - Total de queries cacheadas: {stats['total_cached_queries']}")
    print(f"  - Total de tabelas rastreadas: {stats['total_tracked_tables']}")
    print(f"  - Detalhes das tabelas:")
    for table, count in stats.get('tracked_tables', {}).items():
        print(f"    * {table}: {count} query(ies)")
    print()

    # Obter queries de uma tabela específica
    print("Queries que usam a tabela 'usuarios':")
    usuario_hashes = cache.get_table_queries('usuarios')
    print(f"  - Total: {len(usuario_hashes)} query(ies)")
    for i, hash_val in enumerate(usuario_hashes, 1):
        print(f"    {i}. Hash: {hash_val[:16]}...")
    print()

    # ========================================
    # CENÁRIO 3: INVALIDAÇÃO AUTOMÁTICA
    # ========================================
    print("=" * 70)
    print("CENÁRIO 3: INVALIDAÇÃO AUTOMÁTICA COM UPDATE")
    print("=" * 70 + "\n")

    # Executar query JOIN novamente (deve vir do cache)
    print("Executando query com JOIN novamente...")
    result2 = cache.execute(query_join)
    print(f"  - Veio do cache? {result2.from_cache} (esperado: True)\n")

    # Fazer UPDATE na tabela 'usuarios'
    print("Executando UPDATE na tabela 'usuarios'...")
    update_query = "UPDATE usuarios SET nome = 'João Silva' WHERE id = 1"

    result_update = cache.execute(update_query)
    print(f"✓ UPDATE executado")
    print(f"  - Caches invalidados automaticamente para tabela 'usuarios'\n")

    # Executar query JOIN novamente (deve ir para MySQL agora)
    print("Executando query com JOIN após UPDATE...")
    result3 = cache.execute(query_join)
    print(f"  - Veio do cache? {result3.from_cache} (esperado: False)")
    print(f"  - Cache foi invalidado automaticamente! ✓\n")

    # ========================================
    # CENÁRIO 4: INVALIDAÇÃO COM INSERT
    # ========================================
    print("=" * 70)
    print("CENÁRIO 4: INVALIDAÇÃO AUTOMÁTICA COM INSERT")
    print("=" * 70 + "\n")

    # Cachear query de pedidos
    print("Executando query de pedidos...")
    result4 = cache.execute(query_pedidos)
    print(f"  - Veio do cache? {result4.from_cache}\n")

    result5 = cache.execute(query_pedidos)
    print(f"  - Segunda execução veio do cache? {result5.from_cache} (esperado: True)\n")

    # Fazer INSERT na tabela 'pedidos'
    print("Executando INSERT na tabela 'pedidos'...")
    insert_query = "INSERT INTO pedidos (user_id, total, status) VALUES (1, 99.90, 'pendente')"

    result_insert = cache.execute(insert_query)
    print(f"✓ INSERT executado")
    print(f"  - Caches da tabela 'pedidos' invalidados automaticamente\n")

    # Executar query novamente
    print("Executando query de pedidos após INSERT...")
    result6 = cache.execute(query_pedidos)
    print(f"  - Veio do cache? {result6.from_cache} (esperado: False)")
    print(f"  - Cache foi invalidado automaticamente! ✓\n")

    # ========================================
    # CENÁRIO 5: INVALIDAÇÃO COM DELETE
    # ========================================
    print("=" * 70)
    print("CENÁRIO 5: INVALIDAÇÃO AUTOMÁTICA COM DELETE")
    print("=" * 70 + "\n")

    # Cachear queries
    cache.execute(query_usuarios)
    result7 = cache.execute(query_usuarios)
    print(f"Query de usuários cacheada: {result7.from_cache}\n")

    # DELETE
    print("Executando DELETE na tabela 'usuarios'...")
    delete_query = "DELETE FROM usuarios WHERE id = 999"

    result_delete = cache.execute(delete_query)
    print(f"✓ DELETE executado")
    print(f"  - Caches da tabela 'usuarios' invalidados automaticamente\n")

    result8 = cache.execute(query_usuarios)
    print(f"  - Veio do cache? {result8.from_cache} (esperado: False)\n")

    # ========================================
    # CENÁRIO 6: INVALIDAÇÃO MANUAL POR TABELA
    # ========================================
    print("=" * 70)
    print("CENÁRIO 6: INVALIDAÇÃO MANUAL POR TABELA")
    print("=" * 70 + "\n")

    # Cachear várias queries
    cache.execute(query_usuarios)
    cache.execute(query_pedidos)
    cache.execute(query_join)

    print("Queries cacheadas:")
    print("  - query_usuarios")
    print("  - query_pedidos")
    print("  - query_join (usa usuarios + pedidos)\n")

    # Invalidar apenas caches da tabela 'pedidos'
    print("Invalidando manualmente caches da tabela 'pedidos'...")
    deleted = cache.invalidate_cache_by_table('pedidos')
    print(f"✓ {deleted} cache(s) invalidado(s)\n")

    # Verificar o que ainda está em cache
    print("Verificando caches após invalidação:")
    r1 = cache.execute(query_usuarios)
    r2 = cache.execute(query_pedidos)
    r3 = cache.execute(query_join)

    print(f"  - query_usuarios veio do cache? {r1.from_cache} (pode ser True)")
    print(f"  - query_pedidos veio do cache? {r2.from_cache} (esperado: False)")
    print(f"  - query_join veio do cache? {r3.from_cache} (esperado: False)")
    print()

    # ========================================
    # CENÁRIO 7: COMPARAÇÃO DE PERFORMANCE
    # ========================================
    print("=" * 70)
    print("CENÁRIO 7: IMPACTO DE PERFORMANCE DO RASTREAMENTO")
    print("=" * 70 + "\n")

    # Limpar cache
    cache.invalidate_cache()

    complex_query = """
        SELECT
            u.id, u.nome, u.email,
            COUNT(p.id) as total_pedidos,
            SUM(p.total) as total_gasto
        FROM usuarios u
        LEFT JOIN pedidos p ON u.id = p.user_id
        WHERE u.status = 'ativo'
        GROUP BY u.id, u.nome, u.email
        HAVING total_pedidos > 0
        ORDER BY total_gasto DESC
        LIMIT 100
    """

    print("Query complexa com JOIN e agregações:")
    print(f"  {complex_query.strip()[:80]}...\n")

    # Primeira execução (MySQL)
    print("1ª execução (MySQL + cache + rastreamento):")
    start = time.time()
    result_a = cache.execute(complex_query)
    time_a = time.time() - start
    print(f"  - Tempo: {time_a:.4f}s")
    print(f"  - Do cache? {result_a.from_cache}\n")

    # Segunda execução (Redis)
    print("2ª execução (Redis):")
    start = time.time()
    result_b = cache.execute(complex_query)
    time_b = time.time() - start
    print(f"  - Tempo: {time_b:.4f}s")
    print(f"  - Do cache? {result_b.from_cache}")
    print(f"  - Speedup: {time_a/time_b:.1f}x mais rápido! 🚀\n")

    # ========================================
    # CENÁRIO 8: ESTATÍSTICAS FINAIS
    # ========================================
    print("=" * 70)
    print("ESTATÍSTICAS FINAIS")
    print("=" * 70 + "\n")

    final_stats = cache.get_cache_stats()
    print("Resumo do sistema de cache:")
    print(f"  - Cache habilitado: {final_stats['cache_enabled']}")
    print(f"  - Redis disponível: {final_stats['redis_available']}")
    print(f"  - Queries cacheadas: {final_stats['total_cached_queries']}")
    print(f"  - Tabelas rastreadas: {final_stats['total_tracked_tables']}")
    print(f"  - TTL padrão: {final_stats['default_ttl']}s")
    print()

    if final_stats.get('tracked_tables'):
        print("Detalhamento por tabela:")
        for table, count in final_stats['tracked_tables'].items():
            queries = cache.get_table_queries(table)
            print(f"  📊 {table}: {count} query(ies)")
            for i, qhash in enumerate(queries[:3], 1):
                print(f"      {i}. {qhash[:32]}...")
        print()

    # ========================================
    # FINALIZAR
    # ========================================
    print("=" * 70)
    print("FINALIZANDO")
    print("=" * 70 + "\n")

    cache.close()
    print("✓ Conexões fechadas com sucesso\n")

    print("\n" + "=" * 70)
    print("RESUMO DOS BENEFÍCIOS:")
    print("=" * 70)
    print("""
✓ Rastreamento automático de tabelas em queries
✓ Invalidação automática de caches em INSERT/UPDATE/DELETE
✓ Suporte completo a JOINs com múltiplas tabelas
✓ Invalidação manual por tabela específica
✓ Estatísticas detalhadas de rastreamento
✓ Zero configuração adicional necessária
✓ Fallback automático em caso de falha do Redis

IMPORTANTE:
- Toda query SELECT rastreia automaticamente as tabelas usadas
- INSERT/UPDATE/DELETE invalidam TODOS os caches das tabelas afetadas
- Queries com JOIN são invalidadas se QUALQUER tabela for modificada
- Isso garante consistência de dados sem configuração manual!
    """)


if __name__ == "__main__":
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 8 + "RASTREAMENTO DE TABELAS E INVALIDAÇÃO AUTOMÁTICA" + " " * 12 + "║")
    print("╚" + "=" * 68 + "╝")
    print("\n")

    print("⚠️  ATENÇÃO:")
    print("Este exemplo demonstra a funcionalidade de rastreamento de tabelas.")
    print("Certifique-se de ter MySQL e Redis rodando, e um banco de dados")
    print("'teste_db' com tabelas 'usuarios' e 'pedidos' configuradas.\n")

    input("Pressione ENTER para continuar ou CTRL+C para cancelar...")

    try:
        main()
        print("\n✓ EXEMPLO CONCLUÍDO COM SUCESSO!\n")
    except KeyboardInterrupt:
        print("\n\n✗ Exemplo cancelado pelo usuário.\n")
    except Exception as e:
        print(f"\n\n✗ Erro durante o exemplo: {e}\n")
