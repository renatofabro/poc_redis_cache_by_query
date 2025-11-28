"""
MySQL Redis Cache Module
Módulo para cache de queries SELECT do MySQL usando Redis como camada de cache.

Este módulo intercepta queries SELECT, cria um hash da query sanitizada,
e armazena/recupera resultados do Redis para melhorar performance.
"""

import hashlib
import json
import re
from typing import Any, Dict, List, Optional, Tuple, Union
from datetime import datetime
import mysql.connector
from mysql.connector import Error as MySQLError
import redis
from redis.exceptions import RedisError


class MySQLRedisCache:
    """
    Classe que implementa cache Redis para queries MySQL SELECT.

    Attributes:
        mysql_config (dict): Configuração do MySQL
        redis_config (dict): Configuração do Redis
        default_ttl (int): TTL padrão para cache em segundos
        cache_enabled (bool): Flag para habilitar/desabilitar cache
    """

    def __init__(
        self,
        mysql_config: Dict[str, Any],
        redis_config: Optional[Dict[str, Any]] = None,
        default_ttl: int = 3600,
        cache_enabled: bool = True
    ):
        """
        Inicializa o MySQLRedisCache.

        Args:
            mysql_config: Dicionário com configurações do MySQL
                         (host, user, password, database, etc)
            redis_config: Dicionário com configurações do Redis
                         (host, port, db, password, etc)
            default_ttl: Tempo de vida padrão do cache em segundos (padrão: 3600)
            cache_enabled: Se o cache está habilitado (padrão: True)
        """
        self.mysql_config = mysql_config
        self.redis_config = redis_config or {
            'host': 'localhost',
            'port': 6379,
            'db': 0,
            'decode_responses': False  # Para trabalhar com bytes
        }
        self.default_ttl = default_ttl
        self.cache_enabled = cache_enabled

        # Inicializa conexões
        self._mysql_conn = None
        self._redis_client = None

        # Prefixo para chaves do Redis
        self.cache_prefix = "mysql_cache:"
        self.table_map_prefix = "table_map:"  # Prefixo para mapeamento tabela->hashes

    def _get_mysql_connection(self) -> mysql.connector.MySQLConnection:
        """
        Obtém ou cria uma conexão MySQL.

        Returns:
            Conexão MySQL
        """
        if self._mysql_conn is None or not self._mysql_conn.is_connected():
            self._mysql_conn = mysql.connector.connect(**self.mysql_config)
        return self._mysql_conn

    def _get_redis_client(self) -> Optional[redis.Redis]:
        """
        Obtém ou cria um cliente Redis.

        Returns:
            Cliente Redis ou None se cache desabilitado
        """
        if not self.cache_enabled:
            return None

        if self._redis_client is None:
            try:
                self._redis_client = redis.Redis(**self.redis_config)
                # Testa conexão
                self._redis_client.ping()
            except (RedisError, Exception) as e:
                print(f"[AVISO] Falha ao conectar ao Redis: {e}")
                print("[AVISO] Continuando sem cache...")
                return None
        return self._redis_client

    def _sanitize_query(self, query: str) -> str:
        """
        Sanitiza a query removendo espaços extras e normalizando.

        Args:
            query: Query SQL original

        Returns:
            Query sanitizada
        """
        # Remove espaços extras
        query = re.sub(r'\s+', ' ', query.strip())
        # Converte para minúsculas para normalização
        query = query.lower()
        return query

    def _generate_hash(self, query: str) -> str:
        """
        Gera hash SHA256 da query sanitizada.

        Args:
            query: Query SQL

        Returns:
            Hash hexadecimal da query
        """
        sanitized = self._sanitize_query(query)
        return hashlib.sha256(sanitized.encode('utf-8')).hexdigest()

    def _is_select_query(self, query: str) -> bool:
        """
        Verifica se a query é do tipo SELECT.

        Args:
            query: Query SQL

        Returns:
            True se for SELECT, False caso contrário
        """
        sanitized = self._sanitize_query(query)
        return sanitized.startswith('select')

    def _get_query_type(self, query: str) -> str:
        """
        Identifica o tipo da query (SELECT, INSERT, UPDATE, DELETE, etc).

        Args:
            query: Query SQL

        Returns:
            Tipo da query em maiúsculas
        """
        sanitized = self._sanitize_query(query)
        if sanitized.startswith('select'):
            return 'SELECT'
        elif sanitized.startswith('insert'):
            return 'INSERT'
        elif sanitized.startswith('update'):
            return 'UPDATE'
        elif sanitized.startswith('delete'):
            return 'DELETE'
        else:
            return 'OTHER'

    def _extract_tables_from_query(self, query: str) -> List[str]:
        """
        Extrai nomes de tabelas de uma query SQL.

        Suporta: FROM, JOIN, INTO, UPDATE

        Args:
            query: Query SQL

        Returns:
            Lista de nomes de tabelas (sem duplicatas)
        """
        sanitized = self._sanitize_query(query)
        tables = set()

        # Padrões para encontrar tabelas
        patterns = [
            # FROM tabela
            r'\bfrom\s+`?(\w+)`?',
            # JOIN tabela
            r'\bjoin\s+`?(\w+)`?',
            # INTO tabela (INSERT)
            r'\binto\s+`?(\w+)`?',
            # UPDATE tabela
            r'\bupdate\s+`?(\w+)`?',
        ]

        for pattern in patterns:
            matches = re.finditer(pattern, sanitized)
            for match in matches:
                table_name = match.group(1)
                # Ignora palavras-chave SQL comuns
                if table_name not in ['select', 'where', 'values', 'set']:
                    tables.add(table_name)

        # Também captura aliases (ex: FROM usuarios u, usuarios AS u)
        # Padrão: FROM tabela alias ou FROM tabela AS alias
        alias_patterns = [
            r'\bfrom\s+`?(\w+)`?\s+(?:as\s+)?\w+',
            r'\bjoin\s+`?(\w+)`?\s+(?:as\s+)?\w+',
        ]

        for pattern in alias_patterns:
            matches = re.finditer(pattern, sanitized)
            for match in matches:
                table_name = match.group(1)
                if table_name not in ['select', 'where', 'values', 'set']:
                    tables.add(table_name)

        return list(tables)

    def _get_table_map_key(self, table_name: str) -> str:
        """
        Gera chave do Redis para o mapeamento de tabela.

        Args:
            table_name: Nome da tabela

        Returns:
            Chave completa do Redis
        """
        return f"{self.table_map_prefix}{table_name}"

    def _register_query_in_tables(
        self,
        query: str,
        query_hash: str,
        tables: List[str]
    ) -> None:
        """
        Registra o hash da query em todas as tabelas envolvidas.

        Cria um SET no Redis para cada tabela contendo os hashes
        de todas as queries que usam essa tabela.

        Args:
            query: Query SQL original
            query_hash: Hash da query
            tables: Lista de tabelas envolvidas
        """
        redis_client = self._get_redis_client()
        if not redis_client or not tables:
            return

        try:
            for table in tables:
                table_key = self._get_table_map_key(table)
                # Adiciona o hash ao SET da tabela
                redis_client.sadd(table_key, query_hash)
                # Define TTL para o mapeamento (maior que o cache)
                redis_client.expire(table_key, self.default_ttl * 2)
        except RedisError as e:
            print(f"[AVISO] Erro ao registrar query nas tabelas: {e}")

    def _invalidate_tables_cache(self, tables: List[str]) -> int:
        """
        Invalida todos os caches relacionados às tabelas especificadas.

        Args:
            tables: Lista de nomes de tabelas

        Returns:
            Número total de caches invalidados
        """
        redis_client = self._get_redis_client()
        if not redis_client or not tables:
            return 0

        total_deleted = 0

        try:
            for table in tables:
                table_key = self._get_table_map_key(table)

                # Obtém todos os hashes de queries que usam esta tabela
                query_hashes = redis_client.smembers(table_key)

                if query_hashes:
                    # Invalida cada cache
                    for query_hash_bytes in query_hashes:
                        query_hash = query_hash_bytes.decode('utf-8') if isinstance(query_hash_bytes, bytes) else query_hash_bytes
                        cache_key = self._get_cache_key(query_hash)
                        deleted = redis_client.delete(cache_key)
                        total_deleted += deleted

                    # Remove o mapeamento da tabela
                    redis_client.delete(table_key)

                    print(f"[INFO] Invalidados {len(query_hashes)} cache(s) da tabela '{table}'")

            return total_deleted
        except RedisError as e:
            print(f"[ERRO] Falha ao invalidar caches de tabelas: {e}")
            return 0

    def _serialize_result(
        self,
        rows: List[Tuple],
        columns: List[str],
        query: str
    ) -> bytes:
        """
        Serializa o resultado da query para armazenar no Redis.

        Args:
            rows: Linhas retornadas pela query
            columns: Nomes das colunas
            query: Query original

        Returns:
            Dados serializados em JSON (bytes)
        """
        data = {
            'columns': columns,
            'rows': [list(row) for row in rows],
            'query': query,
            'cached_at': datetime.now().isoformat(),
            'row_count': len(rows)
        }
        return json.dumps(data, default=str).encode('utf-8')

    def _deserialize_result(self, cached_data: bytes) -> Dict[str, Any]:
        """
        Deserializa resultado do Redis.

        Args:
            cached_data: Dados em bytes do Redis

        Returns:
            Dicionário com dados deserializados
        """
        return json.loads(cached_data.decode('utf-8'))

    def _get_cache_key(self, query_hash: str) -> str:
        """
        Gera chave do Redis para a query.

        Args:
            query_hash: Hash da query

        Returns:
            Chave completa do Redis
        """
        return f"{self.cache_prefix}{query_hash}"

    def _execute_mysql_query(
        self,
        query: str,
        params: Optional[Tuple] = None
    ) -> Tuple[List[Tuple], List[str]]:
        """
        Executa query no MySQL.

        Args:
            query: Query SQL
            params: Parâmetros da query (opcional)

        Returns:
            Tupla com (linhas, colunas)
        """
        conn = self._get_mysql_connection()
        cursor = conn.cursor()

        try:
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)

            rows = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description] if cursor.description else []

            return rows, columns
        finally:
            cursor.close()

    def execute(
        self,
        query: str,
        params: Optional[Tuple] = None,
        use_cache: Optional[bool] = None
    ) -> 'MySQLCacheResult':
        """
        Executa uma query com cache Redis (se for SELECT).

        Para queries INSERT/UPDATE/DELETE, invalida automaticamente
        os caches das tabelas afetadas.

        Args:
            query: Query SQL
            params: Parâmetros da query (opcional)
            use_cache: Sobrescreve configuração de cache (opcional)

        Returns:
            MySQLCacheResult com os dados e metadados
        """
        # Identifica tipo da query
        query_type = self._get_query_type(query)

        # Se for INSERT/UPDATE/DELETE, invalida caches das tabelas afetadas
        if query_type in ['INSERT', 'UPDATE', 'DELETE']:
            tables = self._extract_tables_from_query(query)
            if tables:
                invalidated = self._invalidate_tables_cache(tables)
                if invalidated > 0:
                    print(f"[INFO] Cache invalidado automaticamente: {invalidated} entrada(s) "
                          f"das tabelas {tables}")

            # Executa a query de modificação no MySQL
            rows, columns = self._execute_mysql_query(query, params)
            result_data = {
                'query': query,
                'from_cache': False,
                'cache_hit': False,
                'rows': rows,
                'columns': columns,
                'row_count': len(rows),
                'cached_at': None
            }
            return MySQLCacheResult(result_data)

        # Determina se deve usar cache (apenas para SELECT)
        should_cache = (
            (use_cache if use_cache is not None else self.cache_enabled)
            and self._is_select_query(query)
            and params is None  # Não cacheia queries parametrizadas por segurança
        )

        result_data = {
            'query': query,
            'from_cache': False,
            'cache_hit': False,
            'rows': [],
            'columns': [],
            'row_count': 0,
            'cached_at': None
        }

        # Se não for SELECT ou cache desabilitado, executa direto no MySQL
        if not should_cache:
            rows, columns = self._execute_mysql_query(query, params)
            result_data.update({
                'rows': rows,
                'columns': columns,
                'row_count': len(rows)
            })
            return MySQLCacheResult(result_data)

        # Gera hash da query
        query_hash = self._generate_hash(query)
        cache_key = self._get_cache_key(query_hash)

        # Tenta obter do cache
        redis_client = self._get_redis_client()
        cached_data = None

        if redis_client:
            try:
                cached_data = redis_client.get(cache_key)
            except RedisError as e:
                print(f"[AVISO] Erro ao buscar no Redis: {e}")
                print("[AVISO] Executando query no MySQL...")

        # Se encontrou no cache
        if cached_data:
            try:
                data = self._deserialize_result(cached_data)
                result_data.update({
                    'from_cache': True,
                    'cache_hit': True,
                    'rows': [tuple(row) for row in data['rows']],
                    'columns': data['columns'],
                    'row_count': data['row_count'],
                    'cached_at': data.get('cached_at')
                })
                return MySQLCacheResult(result_data)
            except Exception as e:
                print(f"[AVISO] Erro ao deserializar cache: {e}")
                print("[AVISO] Executando query no MySQL...")

        # Cache miss - executa no MySQL
        rows, columns = self._execute_mysql_query(query, params)
        result_data.update({
            'rows': rows,
            'columns': columns,
            'row_count': len(rows)
        })

        # Extrai tabelas da query para rastreamento
        tables = self._extract_tables_from_query(query)

        # Armazena no cache e registra nas tabelas
        if redis_client:
            try:
                serialized = self._serialize_result(rows, columns, query)
                redis_client.setex(
                    cache_key,
                    self.default_ttl,
                    serialized
                )

                # Registra o hash desta query em todas as tabelas envolvidas
                if tables:
                    self._register_query_in_tables(query, query_hash, tables)

            except RedisError as e:
                print(f"[AVISO] Erro ao armazenar no Redis: {e}")

        return MySQLCacheResult(result_data)

    def invalidate_cache(self, query: Optional[str] = None) -> int:
        """
        Invalida cache de uma query específica ou padrão.

        Args:
            query: Query para invalidar (None para invalidar por padrão)

        Returns:
            Número de chaves removidas
        """
        redis_client = self._get_redis_client()
        if not redis_client:
            print("[AVISO] Redis não disponível para invalidar cache")
            return 0

        try:
            if query:
                # Invalida cache de query específica
                query_hash = self._generate_hash(query)
                cache_key = self._get_cache_key(query_hash)
                deleted = redis_client.delete(cache_key)
                return deleted
            else:
                # Invalida todos os caches com o prefixo
                pattern = f"{self.cache_prefix}*"
                keys = list(redis_client.scan_iter(match=pattern))

                # Também remove todos os mapeamentos de tabelas
                table_pattern = f"{self.table_map_prefix}*"
                table_keys = list(redis_client.scan_iter(match=table_pattern))

                all_keys = keys + table_keys
                if all_keys:
                    deleted = redis_client.delete(*all_keys)
                    return deleted
                return 0
        except RedisError as e:
            print(f"[ERRO] Falha ao invalidar cache: {e}")
            return 0

    def invalidate_cache_by_table(self, table_name: str) -> int:
        """
        Invalida todos os caches relacionados a uma tabela específica.

        Args:
            table_name: Nome da tabela

        Returns:
            Número de caches invalidados
        """
        return self._invalidate_tables_cache([table_name])

    def set_ttl(self, query: str, ttl: int) -> bool:
        """
        Ajusta o TTL de uma query específica no cache.

        Args:
            query: Query SQL
            ttl: Novo TTL em segundos

        Returns:
            True se bem-sucedido, False caso contrário
        """
        redis_client = self._get_redis_client()
        if not redis_client:
            print("[AVISO] Redis não disponível para ajustar TTL")
            return False

        try:
            query_hash = self._generate_hash(query)
            cache_key = self._get_cache_key(query_hash)
            return redis_client.expire(cache_key, ttl)
        except RedisError as e:
            print(f"[ERRO] Falha ao ajustar TTL: {e}")
            return False

    def flush_all(self) -> bool:
        """
        Remove todos os dados do Redis (FLUSHALL).

        ATENÇÃO: Esta operação remove TODOS os dados do Redis,
        não apenas os caches deste módulo.

        Returns:
            True se bem-sucedido, False caso contrário
        """
        redis_client = self._get_redis_client()
        if not redis_client:
            print("[AVISO] Redis não disponível para flush")
            return False

        try:
            redis_client.flushall()
            print("[INFO] Redis FLUSHALL executado com sucesso")
            return True
        except RedisError as e:
            print(f"[ERRO] Falha ao executar FLUSHALL: {e}")
            return False

    def enable_cache(self) -> None:
        """Habilita o sistema de cache."""
        self.cache_enabled = True
        print("[INFO] Cache habilitado")

    def disable_cache(self) -> None:
        """Desabilita o sistema de cache."""
        self.cache_enabled = False
        print("[INFO] Cache desabilitado")

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Obtém estatísticas do cache.

        Returns:
            Dicionário com estatísticas incluindo mapeamento de tabelas
        """
        redis_client = self._get_redis_client()
        if not redis_client:
            return {
                'cache_enabled': self.cache_enabled,
                'redis_available': False
            }

        try:
            # Conta caches de queries
            pattern = f"{self.cache_prefix}*"
            cache_keys = list(redis_client.scan_iter(match=pattern))

            # Conta mapeamentos de tabelas
            table_pattern = f"{self.table_map_prefix}*"
            table_keys = list(redis_client.scan_iter(match=table_pattern))

            # Detalhes de tabelas rastreadas
            table_details = {}
            for table_key in table_keys:
                table_name = table_key.decode('utf-8').replace(self.table_map_prefix, '')
                query_count = redis_client.scard(table_key)
                table_details[table_name] = query_count

            return {
                'cache_enabled': self.cache_enabled,
                'redis_available': True,
                'total_cached_queries': len(cache_keys),
                'total_tracked_tables': len(table_keys),
                'tracked_tables': table_details,
                'default_ttl': self.default_ttl,
                'cache_prefix': self.cache_prefix,
                'table_map_prefix': self.table_map_prefix
            }
        except RedisError as e:
            print(f"[ERRO] Falha ao obter estatísticas: {e}")
            return {
                'cache_enabled': self.cache_enabled,
                'redis_available': False,
                'error': str(e)
            }

    def get_table_queries(self, table_name: str) -> List[str]:
        """
        Retorna lista de hashes de queries que usam uma tabela específica.

        Args:
            table_name: Nome da tabela

        Returns:
            Lista de hashes de queries
        """
        redis_client = self._get_redis_client()
        if not redis_client:
            return []

        try:
            table_key = self._get_table_map_key(table_name)
            query_hashes = redis_client.smembers(table_key)
            return [
                qh.decode('utf-8') if isinstance(qh, bytes) else qh
                for qh in query_hashes
            ]
        except RedisError as e:
            print(f"[ERRO] Falha ao obter queries da tabela: {e}")
            return []

    def close(self) -> None:
        """Fecha conexões MySQL e Redis."""
        if self._mysql_conn and self._mysql_conn.is_connected():
            self._mysql_conn.close()
            print("[INFO] Conexão MySQL fechada")

        if self._redis_client:
            self._redis_client.close()
            print("[INFO] Conexão Redis fechada")


class MySQLCacheResult:
    """
    Classe que encapsula o resultado de uma query com informações de cache.
    Simula a estrutura de resultado do mysql.connector.
    """

    def __init__(self, data: Dict[str, Any]):
        """
        Inicializa o resultado.

        Args:
            data: Dicionário com dados do resultado
        """
        self._data = data
        self._current_row = 0

    @property
    def rows(self) -> List[Tuple]:
        """Retorna todas as linhas."""
        return self._data['rows']

    @property
    def columns(self) -> List[str]:
        """Retorna nomes das colunas."""
        return self._data['columns']

    @property
    def row_count(self) -> int:
        """Retorna número de linhas."""
        return self._data['row_count']

    @property
    def from_cache(self) -> bool:
        """Indica se veio do cache."""
        return self._data['from_cache']

    @property
    def cache_hit(self) -> bool:
        """Indica se houve cache hit."""
        return self._data['cache_hit']

    @property
    def cached_at(self) -> Optional[str]:
        """Retorna timestamp do cache."""
        return self._data.get('cached_at')

    @property
    def query(self) -> str:
        """Retorna a query executada."""
        return self._data['query']

    def fetchall(self) -> List[Tuple]:
        """Retorna todas as linhas (compatível com mysql.connector)."""
        return self.rows

    def fetchone(self) -> Optional[Tuple]:
        """Retorna próxima linha (compatível com mysql.connector)."""
        if self._current_row < len(self.rows):
            row = self.rows[self._current_row]
            self._current_row += 1
            return row
        return None

    def fetchmany(self, size: int = 1) -> List[Tuple]:
        """Retorna múltiplas linhas (compatível com mysql.connector)."""
        result = []
        for _ in range(size):
            row = self.fetchone()
            if row is None:
                break
            result.append(row)
        return result

    def as_dict(self) -> List[Dict[str, Any]]:
        """
        Retorna resultado como lista de dicionários.

        Returns:
            Lista de dicionários, cada um representando uma linha
        """
        return [
            dict(zip(self.columns, row))
            for row in self.rows
        ]

    def __iter__(self):
        """Permite iteração sobre as linhas."""
        return iter(self.rows)

    def __len__(self) -> int:
        """Retorna número de linhas."""
        return self.row_count

    def __repr__(self) -> str:
        """Representação string do resultado."""
        cache_status = "CACHE HIT" if self.from_cache else "MYSQL"
        return (
            f"<MySQLCacheResult rows={self.row_count} "
            f"source={cache_status}>"
        )
