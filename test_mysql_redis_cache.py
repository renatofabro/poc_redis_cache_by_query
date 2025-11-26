"""
Testes Unitários para MySQLRedisCache

Execute com: pytest test_mysql_redis_cache.py -v
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, call
from mysql_redis_cache import MySQLRedisCache, MySQLCacheResult


class TestMySQLRedisCache:
    """Testes unitários para MySQLRedisCache."""

    @pytest.fixture
    def mysql_config(self):
        """Configuração mock do MySQL."""
        return {
            'host': 'localhost',
            'user': 'test_user',
            'password': 'test_pass',
            'database': 'test_db'
        }

    @pytest.fixture
    def redis_config(self):
        """Configuração mock do Redis."""
        return {
            'host': 'localhost',
            'port': 6379,
            'db': 0
        }

    @pytest.fixture
    def cache_instance(self, mysql_config, redis_config):
        """Instância do cache para testes."""
        with patch('mysql_redis_cache.mysql.connector.connect'), \
             patch('mysql_redis_cache.redis.Redis'):
            cache = MySQLRedisCache(
                mysql_config=mysql_config,
                redis_config=redis_config,
                default_ttl=3600
            )
            yield cache

    # ========================================
    # TESTES DE SANITIZAÇÃO E HASH
    # ========================================

    def test_sanitize_query(self, cache_instance):
        """Testa sanitização de queries."""
        query1 = "SELECT * FROM usuarios WHERE id = 1"
        query2 = "  SELECT   *   FROM   usuarios   WHERE   id = 1  "

        sanitized1 = cache_instance._sanitize_query(query1)
        sanitized2 = cache_instance._sanitize_query(query2)

        assert sanitized1 == sanitized2
        assert sanitized1 == "select * from usuarios where id = 1"

    def test_generate_hash(self, cache_instance):
        """Testa geração de hash."""
        query1 = "SELECT * FROM usuarios"
        query2 = "  SELECT   *   FROM   usuarios  "

        hash1 = cache_instance._generate_hash(query1)
        hash2 = cache_instance._generate_hash(query2)

        # Queries equivalentes devem gerar mesmo hash
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 = 64 chars hex

    def test_is_select_query(self, cache_instance):
        """Testa detecção de queries SELECT."""
        assert cache_instance._is_select_query("SELECT * FROM usuarios") is True
        assert cache_instance._is_select_query("  SELECT * FROM usuarios") is True
        assert cache_instance._is_select_query("INSERT INTO usuarios") is False
        assert cache_instance._is_select_query("UPDATE usuarios") is False
        assert cache_instance._is_select_query("DELETE FROM usuarios") is False

    def test_get_query_type(self, cache_instance):
        """Testa identificação de tipo de query."""
        assert cache_instance._get_query_type("SELECT * FROM usuarios") == 'SELECT'
        assert cache_instance._get_query_type("INSERT INTO usuarios") == 'INSERT'
        assert cache_instance._get_query_type("UPDATE usuarios SET") == 'UPDATE'
        assert cache_instance._get_query_type("DELETE FROM usuarios") == 'DELETE'
        assert cache_instance._get_query_type("CREATE TABLE usuarios") == 'OTHER'

    # ========================================
    # TESTES DE EXTRAÇÃO DE TABELAS
    # ========================================

    def test_extract_tables_simple_select(self, cache_instance):
        """Testa extração de tabelas em SELECT simples."""
        query = "SELECT * FROM usuarios WHERE id = 1"
        tables = cache_instance._extract_tables_from_query(query)

        assert 'usuarios' in tables
        assert len(tables) == 1

    def test_extract_tables_with_join(self, cache_instance):
        """Testa extração de tabelas em queries com JOIN."""
        query = """
            SELECT u.*, p.*
            FROM usuarios u
            INNER JOIN pedidos p ON u.id = p.user_id
        """
        tables = cache_instance._extract_tables_from_query(query)

        assert 'usuarios' in tables
        assert 'pedidos' in tables
        assert len(tables) == 2

    def test_extract_tables_multiple_joins(self, cache_instance):
        """Testa extração com múltiplos JOINs."""
        query = """
            SELECT u.*, p.*, pr.*
            FROM usuarios u
            INNER JOIN pedidos p ON u.id = p.user_id
            LEFT JOIN produtos pr ON p.produto_id = pr.id
        """
        tables = cache_instance._extract_tables_from_query(query)

        assert 'usuarios' in tables
        assert 'pedidos' in tables
        assert 'produtos' in tables
        assert len(tables) == 3

    def test_extract_tables_insert(self, cache_instance):
        """Testa extração em INSERT."""
        query = "INSERT INTO usuarios (nome, email) VALUES ('João', 'joao@email.com')"
        tables = cache_instance._extract_tables_from_query(query)

        assert 'usuarios' in tables

    def test_extract_tables_update(self, cache_instance):
        """Testa extração em UPDATE."""
        query = "UPDATE usuarios SET nome = 'João' WHERE id = 1"
        tables = cache_instance._extract_tables_from_query(query)

        assert 'usuarios' in tables

    def test_extract_tables_with_backticks(self, cache_instance):
        """Testa extração com backticks."""
        query = "SELECT * FROM `usuarios` WHERE id = 1"
        tables = cache_instance._extract_tables_from_query(query)

        assert 'usuarios' in tables

    # ========================================
    # TESTES DE CACHE BÁSICO
    # ========================================

    @patch('mysql_redis_cache.mysql.connector.connect')
    @patch('mysql_redis_cache.redis.Redis')
    def test_execute_select_cache_miss(self, mock_redis_class, mock_mysql_connect, mysql_config):
        """Testa execução de SELECT com cache miss."""
        # Mock MySQL
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [(1, 'João'), (2, 'Maria')]
        mock_cursor.description = [('id',), ('nome',)]

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.is_connected.return_value = True
        mock_mysql_connect.return_value = mock_conn

        # Mock Redis
        mock_redis = MagicMock()
        mock_redis.get.return_value = None  # Cache miss
        mock_redis.ping.return_value = True
        mock_redis_class.return_value = mock_redis

        cache = MySQLRedisCache(mysql_config=mysql_config)
        result = cache.execute("SELECT * FROM usuarios")

        # Verificações
        assert result.row_count == 2
        assert result.from_cache is False
        assert result.columns == ['id', 'nome']
        assert len(result.rows) == 2

        # Verifica que armazenou no Redis
        mock_redis.setex.assert_called_once()

    @patch('mysql_redis_cache.mysql.connector.connect')
    @patch('mysql_redis_cache.redis.Redis')
    def test_execute_select_cache_hit(self, mock_redis_class, mock_mysql_connect, mysql_config):
        """Testa execução de SELECT com cache hit."""
        # Mock Redis com cache hit
        cached_data = {
            'columns': ['id', 'nome'],
            'rows': [[1, 'João'], [2, 'Maria']],
            'query': 'select * from usuarios',
            'cached_at': '2024-01-01T10:00:00',
            'row_count': 2
        }
        import json
        mock_redis = MagicMock()
        mock_redis.get.return_value = json.dumps(cached_data).encode('utf-8')
        mock_redis.ping.return_value = True
        mock_redis_class.return_value = mock_redis

        # Mock MySQL (não deve ser chamado)
        mock_mysql_connect.return_value = MagicMock()

        cache = MySQLRedisCache(mysql_config=mysql_config)
        result = cache.execute("SELECT * FROM usuarios")

        # Verificações
        assert result.row_count == 2
        assert result.from_cache is True
        assert result.cache_hit is True
        assert result.columns == ['id', 'nome']

    # ========================================
    # TESTES DE INVALIDAÇÃO AUTOMÁTICA
    # ========================================

    @patch('mysql_redis_cache.mysql.connector.connect')
    @patch('mysql_redis_cache.redis.Redis')
    def test_insert_invalidates_cache(self, mock_redis_class, mock_mysql_connect, mysql_config):
        """Testa que INSERT invalida caches automaticamente."""
        # Mock Redis
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        mock_redis.smembers.return_value = [b'hash1', b'hash2']
        mock_redis_class.return_value = mock_redis

        # Mock MySQL
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_cursor.description = None

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.is_connected.return_value = True
        mock_mysql_connect.return_value = mock_conn

        cache = MySQLRedisCache(mysql_config=mysql_config)
        result = cache.execute("INSERT INTO usuarios (nome) VALUES ('João')")

        # Verifica que tentou invalidar caches
        mock_redis.smembers.assert_called()

    @patch('mysql_redis_cache.mysql.connector.connect')
    @patch('mysql_redis_cache.redis.Redis')
    def test_update_invalidates_cache(self, mock_redis_class, mock_mysql_connect, mysql_config):
        """Testa que UPDATE invalida caches automaticamente."""
        # Mock Redis
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        mock_redis.smembers.return_value = [b'hash1']
        mock_redis_class.return_value = mock_redis

        # Mock MySQL
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_cursor.description = None

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.is_connected.return_value = True
        mock_mysql_connect.return_value = mock_conn

        cache = MySQLRedisCache(mysql_config=mysql_config)
        cache.execute("UPDATE usuarios SET nome = 'João' WHERE id = 1")

        # Verifica que tentou invalidar
        mock_redis.smembers.assert_called()

    # ========================================
    # TESTES DE RASTREAMENTO DE TABELAS
    # ========================================

    @patch('mysql_redis_cache.redis.Redis')
    def test_register_query_in_tables(self, mock_redis_class, cache_instance):
        """Testa registro de query nas tabelas."""
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        mock_redis_class.return_value = mock_redis
        cache_instance._redis_client = mock_redis

        query_hash = "abc123"
        tables = ['usuarios', 'pedidos']

        cache_instance._register_query_in_tables("SELECT * FROM usuarios", query_hash, tables)

        # Verifica que adicionou aos SETs
        assert mock_redis.sadd.call_count == 2
        assert mock_redis.expire.call_count == 2

    @patch('mysql_redis_cache.redis.Redis')
    def test_get_table_queries(self, mock_redis_class, mysql_config):
        """Testa obtenção de queries de uma tabela."""
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        mock_redis.smembers.return_value = [b'hash1', b'hash2', b'hash3']
        mock_redis_class.return_value = mock_redis

        with patch('mysql_redis_cache.mysql.connector.connect'):
            cache = MySQLRedisCache(mysql_config=mysql_config)
            cache._redis_client = mock_redis

            hashes = cache.get_table_queries('usuarios')

            assert len(hashes) == 3
            assert 'hash1' in hashes
            assert 'hash2' in hashes
            assert 'hash3' in hashes

    @patch('mysql_redis_cache.redis.Redis')
    def test_invalidate_cache_by_table(self, mock_redis_class, mysql_config):
        """Testa invalidação por tabela específica."""
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        mock_redis.smembers.return_value = [b'hash1', b'hash2']
        mock_redis.delete.return_value = 1
        mock_redis_class.return_value = mock_redis

        with patch('mysql_redis_cache.mysql.connector.connect'):
            cache = MySQLRedisCache(mysql_config=mysql_config)
            cache._redis_client = mock_redis

            deleted = cache.invalidate_cache_by_table('usuarios')

            assert deleted == 2  # 2 hashes invalidados
            mock_redis.smembers.assert_called_once()

    # ========================================
    # TESTES DE ESTATÍSTICAS
    # ========================================

    @patch('mysql_redis_cache.redis.Redis')
    def test_get_cache_stats(self, mock_redis_class, mysql_config):
        """Testa obtenção de estatísticas."""
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True

        # Mock scan_iter retornando chaves
        def scan_iter_side_effect(match):
            if 'mysql_cache:' in match:
                return [b'mysql_cache:hash1', b'mysql_cache:hash2']
            elif 'table_map:' in match:
                return [b'table_map:usuarios', b'table_map:pedidos']
            return []

        mock_redis.scan_iter.side_effect = scan_iter_side_effect
        mock_redis.scard.return_value = 2
        mock_redis_class.return_value = mock_redis

        with patch('mysql_redis_cache.mysql.connector.connect'):
            cache = MySQLRedisCache(mysql_config=mysql_config)
            cache._redis_client = mock_redis

            stats = cache.get_cache_stats()

            assert stats['cache_enabled'] is True
            assert stats['redis_available'] is True
            assert stats['total_cached_queries'] == 2
            assert stats['total_tracked_tables'] == 2
            assert 'usuarios' in stats['tracked_tables']
            assert 'pedidos' in stats['tracked_tables']

    # ========================================
    # TESTES DE CONTROLE DE CACHE
    # ========================================

    def test_enable_disable_cache(self, cache_instance):
        """Testa habilitar/desabilitar cache."""
        assert cache_instance.cache_enabled is True

        cache_instance.disable_cache()
        assert cache_instance.cache_enabled is False

        cache_instance.enable_cache()
        assert cache_instance.cache_enabled is True

    # ========================================
    # TESTES DE MySQLCacheResult
    # ========================================

    def test_mysql_cache_result_properties(self):
        """Testa propriedades de MySQLCacheResult."""
        data = {
            'query': 'SELECT * FROM usuarios',
            'from_cache': True,
            'cache_hit': True,
            'rows': [(1, 'João'), (2, 'Maria')],
            'columns': ['id', 'nome'],
            'row_count': 2,
            'cached_at': '2024-01-01T10:00:00'
        }

        result = MySQLCacheResult(data)

        assert result.row_count == 2
        assert result.from_cache is True
        assert result.cache_hit is True
        assert len(result.columns) == 2
        assert len(result.rows) == 2

    def test_mysql_cache_result_fetchone(self):
        """Testa fetchone()."""
        data = {
            'query': 'SELECT * FROM usuarios',
            'from_cache': False,
            'cache_hit': False,
            'rows': [(1, 'João'), (2, 'Maria'), (3, 'José')],
            'columns': ['id', 'nome'],
            'row_count': 3,
            'cached_at': None
        }

        result = MySQLCacheResult(data)

        row1 = result.fetchone()
        assert row1 == (1, 'João')

        row2 = result.fetchone()
        assert row2 == (2, 'Maria')

        row3 = result.fetchone()
        assert row3 == (3, 'José')

        row4 = result.fetchone()
        assert row4 is None

    def test_mysql_cache_result_fetchmany(self):
        """Testa fetchmany()."""
        data = {
            'query': 'SELECT * FROM usuarios',
            'from_cache': False,
            'cache_hit': False,
            'rows': [(1, 'João'), (2, 'Maria'), (3, 'José')],
            'columns': ['id', 'nome'],
            'row_count': 3,
            'cached_at': None
        }

        result = MySQLCacheResult(data)

        rows = result.fetchmany(2)
        assert len(rows) == 2
        assert rows[0] == (1, 'João')
        assert rows[1] == (2, 'Maria')

    def test_mysql_cache_result_fetchall(self):
        """Testa fetchall()."""
        data = {
            'query': 'SELECT * FROM usuarios',
            'from_cache': False,
            'cache_hit': False,
            'rows': [(1, 'João'), (2, 'Maria')],
            'columns': ['id', 'nome'],
            'row_count': 2,
            'cached_at': None
        }

        result = MySQLCacheResult(data)
        all_rows = result.fetchall()

        assert len(all_rows) == 2
        assert all_rows[0] == (1, 'João')
        assert all_rows[1] == (2, 'Maria')

    def test_mysql_cache_result_as_dict(self):
        """Testa as_dict()."""
        data = {
            'query': 'SELECT * FROM usuarios',
            'from_cache': False,
            'cache_hit': False,
            'rows': [(1, 'João'), (2, 'Maria')],
            'columns': ['id', 'nome'],
            'row_count': 2,
            'cached_at': None
        }

        result = MySQLCacheResult(data)
        dict_rows = result.as_dict()

        assert len(dict_rows) == 2
        assert dict_rows[0] == {'id': 1, 'nome': 'João'}
        assert dict_rows[1] == {'id': 2, 'nome': 'Maria'}

    def test_mysql_cache_result_iteration(self):
        """Testa iteração sobre resultado."""
        data = {
            'query': 'SELECT * FROM usuarios',
            'from_cache': False,
            'cache_hit': False,
            'rows': [(1, 'João'), (2, 'Maria')],
            'columns': ['id', 'nome'],
            'row_count': 2,
            'cached_at': None
        }

        result = MySQLCacheResult(data)
        rows = list(result)

        assert len(rows) == 2
        assert rows[0] == (1, 'João')

    def test_mysql_cache_result_len(self):
        """Testa len() do resultado."""
        data = {
            'query': 'SELECT * FROM usuarios',
            'from_cache': False,
            'cache_hit': False,
            'rows': [(1, 'João'), (2, 'Maria'), (3, 'José')],
            'columns': ['id', 'nome'],
            'row_count': 3,
            'cached_at': None
        }

        result = MySQLCacheResult(data)
        assert len(result) == 3

    # ========================================
    # TESTES DE FALLBACK
    # ========================================

    @patch('mysql_redis_cache.mysql.connector.connect')
    @patch('mysql_redis_cache.redis.Redis')
    def test_redis_failure_fallback(self, mock_redis_class, mock_mysql_connect, mysql_config):
        """Testa fallback quando Redis falha."""
        # Mock Redis que falha
        mock_redis_class.side_effect = Exception("Redis connection failed")

        # Mock MySQL
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [(1, 'João')]
        mock_cursor.description = [('id',), ('nome',)]

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.is_connected.return_value = True
        mock_mysql_connect.return_value = mock_conn

        cache = MySQLRedisCache(mysql_config=mysql_config)
        result = cache.execute("SELECT * FROM usuarios")

        # Deve funcionar mesmo com Redis falhando
        assert result.row_count == 1
        assert result.from_cache is False


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
