# MySQL Redis Cache

Sistema de cache Redis transparente para queries MySQL SELECT usando `mysql.connector`.

## 📋 Índice

- [Visão Geral](#visão-geral)
- [Características](#características)
- [Instalação](#instalação)
- [Uso Básico](#uso-básico)
- [Funcionalidades](#funcionalidades)
- [Arquitetura](#arquitetura)
- [API Reference](#api-reference)
- [Exemplos Avançados](#exemplos-avançados)
- [Troubleshooting](#troubleshooting)
- [Performance](#performance)

## 🎯 Visão Geral

Este módulo intercepta queries SQL do tipo `SELECT`, cria um hash da query sanitizada e utiliza Redis como camada de cache para armazenar e recuperar resultados, melhorando significativamente a performance de queries repetidas.

### Fluxo de Funcionamento

```
┌─────────────┐
│   Query     │
│   SELECT    │
└──────┬──────┘
       │
       ├─────► Sanitiza Query
       │
       ├─────► Gera Hash SHA256
       │
       ├─────► Verifica Redis
       │       │
       │       ├─[Cache Hit]──► Retorna do Redis
       │       │                (JSON → MySQLResult)
       │       │
       │       └─[Cache Miss]─► Executa MySQL
       │                        │
       │                        ├─► Armazena Redis
       │                        │
       │                        └─► Retorna Resultado
       │
       └─────► [Falha Redis]──► Executa MySQL
                                (Fallback automático)
```

## ✨ Características

- ✅ **Cache automático** de queries `SELECT`
- ✅ **Hash SHA256** de queries sanitizadas
- ✅ **Rastreamento inteligente de tabelas** com mapeamento automático
- ✅ **Invalidação automática** em INSERT/UPDATE/DELETE
- ✅ **Suporte completo a JOINs** com múltiplas tabelas
- ✅ **Compatibilidade total** com `mysql.connector` API
- ✅ **Fallback automático** em caso de falha do Redis
- ✅ **TTL configurável** por query ou global
- ✅ **Invalidação de cache** individual, por tabela ou em massa
- ✅ **Métricas e estatísticas** de cache e rastreamento
- ✅ **Controle de habilitação** do cache em runtime
- ✅ **Zero dependências extras** além de MySQL e Redis

## 📦 Instalação

### 1. Clone o repositório

```bash
git clone <seu-repositorio>
cd mysql-redis-cache
```

### 2. Instale as dependências

```bash
pip install -r requirements.txt
```

### 3. Configure MySQL e Redis

Certifique-se de ter MySQL e Redis instalados e rodando:

```bash
# Verificar MySQL
mysql --version

# Verificar Redis
redis-cli ping
# Deve retornar: PONG
```

## 🚀 Uso Básico

### Exemplo Mínimo

```python
from mysql_redis_cache import MySQLRedisCache

# Configuração
mysql_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'sua_senha',
    'database': 'seu_banco'
}

# Inicializar
cache = MySQLRedisCache(mysql_config=mysql_config)

# Executar query
result = cache.execute("SELECT * FROM usuarios LIMIT 10")

# Usar resultado
print(f"Retornadas {result.row_count} linhas")
print(f"Veio do cache? {result.from_cache}")

for row in result:
    print(row)

# Fechar conexões
cache.close()
```

### Primeira Execução vs Segunda Execução

```python
import time

query = "SELECT * FROM usuarios WHERE status = 'ativo'"

# Primeira execução - busca no MySQL
start = time.time()
result1 = cache.execute(query)
print(f"Tempo: {time.time() - start:.4f}s")  # Ex: 0.1250s
print(f"Do cache? {result1.from_cache}")     # False

# Segunda execução - busca no Redis
start = time.time()
result2 = cache.execute(query)
print(f"Tempo: {time.time() - start:.4f}s")  # Ex: 0.0023s (50x mais rápido!)
print(f"Do cache? {result2.from_cache}")     # True
```

## 🔄 Rastreamento de Tabelas e Invalidação Automática

### Como Funciona

O sistema mantém um **mapeamento automático** de quais queries usam cada tabela:

```
Redis:
  table_map:usuarios → [hash1, hash2, hash3, ...]
  table_map:pedidos  → [hash1, hash4, hash5, ...]
```

Quando você executa um **INSERT/UPDATE/DELETE**, o sistema:
1. Identifica as tabelas afetadas
2. Busca todos os hashes de queries que usam essas tabelas
3. Invalida automaticamente todos esses caches

### Benefícios para JOINs

```python
# Query com JOIN entre usuarios e pedidos
query = """
    SELECT u.nome, p.total
    FROM usuarios u
    JOIN pedidos p ON u.id = p.user_id
"""

# 1ª execução - cacheia e registra uso de 'usuarios' e 'pedidos'
result = cache.execute(query)  # → MySQL

# 2ª execução - retorna do cache
result = cache.execute(query)  # → Redis (rápido!)

# UPDATE em qualquer tabela relacionada
cache.execute("UPDATE usuarios SET nome = 'João' WHERE id = 1")
# ✓ Cache da query JOIN invalidado AUTOMATICAMENTE!

# Próxima execução busca dados atualizados
result = cache.execute(query)  # → MySQL (dados frescos)
```

### Exemplo Prático

```python
# Cachear queries com JOIN
cache.execute("""
    SELECT u.*, p.*
    FROM usuarios u
    LEFT JOIN pedidos p ON u.id = p.user_id
    WHERE u.status = 'ativo'
""")

# Verificar rastreamento
stats = cache.get_cache_stats()
print(stats['tracked_tables'])
# {'usuarios': 1, 'pedidos': 1}

# UPDATE invalida automaticamente
cache.execute("UPDATE pedidos SET status = 'pago' WHERE id = 123")
# [INFO] Cache invalidado automaticamente: 1 entrada(s) das tabelas ['pedidos']

# Próxima execução busca dados atualizados do MySQL
```

### Invalidação Manual por Tabela

```python
# Invalidar todos os caches que usam a tabela 'usuarios'
deleted = cache.invalidate_cache_by_table('usuarios')
print(f"Invalidados {deleted} cache(s)")

# Ver queries que usam uma tabela
hashes = cache.get_table_queries('usuarios')
print(f"Tabela 'usuarios' é usada por {len(hashes)} query(ies)")
```

## 🛠️ Funcionalidades

### 1. Sanitização e Hash de Queries

```python
# Queries equivalentes geram o mesmo hash
query1 = "SELECT * FROM usuarios WHERE id = 1"
query2 = "  SELECT   *   FROM   usuarios   WHERE   id = 1  "

# Ambas geram o mesmo hash após sanitização
```

### 2. Invalidação de Cache

```python
# Invalidar cache de query específica
cache.invalidate_cache("SELECT * FROM usuarios")

# Invalidar TODOS os caches do módulo
cache.invalidate_cache()
```

### 3. Ajustar TTL

```python
# TTL global (na inicialização)
cache = MySQLRedisCache(
    mysql_config=config,
    default_ttl=7200  # 2 horas
)

# TTL para query específica
query = "SELECT * FROM relatorios"
cache.execute(query)
cache.set_ttl(query, 300)  # 5 minutos
```

### 4. Habilitar/Desabilitar Cache

```python
# Desabilitar cache
cache.disable_cache()
result = cache.execute("SELECT * FROM usuarios")
# Sempre busca do MySQL

# Habilitar cache
cache.enable_cache()
result = cache.execute("SELECT * FROM usuarios")
# Usa cache normalmente

# Ou sobrescrever para query específica
result = cache.execute(
    "SELECT * FROM usuarios",
    use_cache=False  # Força busca no MySQL
)
```

### 5. Estatísticas

```python
stats = cache.get_cache_stats()
print(stats)
# {
#     'cache_enabled': True,
#     'redis_available': True,
#     'total_cached_queries': 15,
#     'default_ttl': 3600,
#     'cache_prefix': 'mysql_cache:'
# }
```

### 6. Flush All (Limpar Redis)

```python
# ⚠️ CUIDADO: Remove TODOS os dados do Redis
cache.flush_all()
```

### 7. Métodos de Iteração (Compatível com mysql.connector)

```python
result = cache.execute("SELECT id, nome FROM usuarios LIMIT 5")

# fetchone() - uma linha por vez
row = result.fetchone()
print(row)  # (1, 'João')

# fetchmany(n) - múltiplas linhas
rows = result.fetchmany(3)
print(rows)  # [(2, 'Maria'), (3, 'José'), (4, 'Ana')]

# fetchall() - todas as linhas
all_rows = result.fetchall()

# as_dict() - como dicionários
dict_rows = result.as_dict()
print(dict_rows[0])  # {'id': 1, 'nome': 'João'}

# Iteração direta
for row in result:
    print(row)
```

## 🏗️ Arquitetura

### Componentes Principais

#### 1. `MySQLRedisCache`

Classe principal que gerencia o cache.

**Responsabilidades:**
- Gerenciar conexões MySQL e Redis
- Sanitizar e hashear queries
- Interceptar queries SELECT
- Armazenar/recuperar do cache
- Tratamento de erros e fallback

#### 2. `MySQLCacheResult`

Encapsula resultados com metadata de cache.

**Propriedades:**
- `rows` - Linhas retornadas
- `columns` - Nomes das colunas
- `row_count` - Número de linhas
- `from_cache` - Se veio do cache
- `cache_hit` - Se houve hit no cache
- `cached_at` - Timestamp do cache

### Estrutura de Dados no Redis

```json
{
  "columns": ["id", "nome", "email"],
  "rows": [
    [1, "João", "joao@email.com"],
    [2, "Maria", "maria@email.com"]
  ],
  "query": "select * from usuarios limit 2",
  "cached_at": "2024-01-15T10:30:45.123456",
  "row_count": 2
}
```

**Chave no Redis:**
```
mysql_cache:<hash_sha256_da_query>
```

## 📚 API Reference

### MySQLRedisCache

#### `__init__(mysql_config, redis_config=None, default_ttl=3600, cache_enabled=True)`

Inicializa o cache.

**Parâmetros:**
- `mysql_config` (dict): Configuração do MySQL
- `redis_config` (dict, opcional): Configuração do Redis
- `default_ttl` (int): TTL padrão em segundos
- `cache_enabled` (bool): Se cache está habilitado

#### `execute(query, params=None, use_cache=None) → MySQLCacheResult`

Executa uma query com cache.

**Parâmetros:**
- `query` (str): Query SQL
- `params` (tuple, opcional): Parâmetros da query
- `use_cache` (bool, opcional): Sobrescrever configuração de cache

**Retorna:** `MySQLCacheResult`

#### `invalidate_cache(query=None) → int`

Invalida cache de queries e mapeamentos de tabelas.

**Parâmetros:**
- `query` (str, opcional): Query específica ou None para tudo

**Retorna:** Número de chaves removidas

#### `invalidate_cache_by_table(table_name) → int`

Invalida todos os caches relacionados a uma tabela específica.

**Parâmetros:**
- `table_name` (str): Nome da tabela

**Retorna:** Número de caches invalidados

**Exemplo:**
```python
# Invalidar todos os caches que usam a tabela 'usuarios'
deleted = cache.invalidate_cache_by_table('usuarios')
```

#### `set_ttl(query, ttl) → bool`

Ajusta TTL de uma query.

**Parâmetros:**
- `query` (str): Query SQL
- `ttl` (int): Novo TTL em segundos

**Retorna:** True se sucesso

#### `flush_all() → bool`

Remove todos os dados do Redis.

**Retorna:** True se sucesso

#### `enable_cache() → None`

Habilita o cache.

#### `disable_cache() → None`

Desabilita o cache.

#### `get_cache_stats() → dict`

Retorna estatísticas do cache incluindo rastreamento de tabelas.

**Retorna:** Dicionário com:
- `cache_enabled`: Se cache está habilitado
- `redis_available`: Se Redis está disponível
- `total_cached_queries`: Total de queries cacheadas
- `total_tracked_tables`: Total de tabelas rastreadas
- `tracked_tables`: Dict com {tabela: num_queries}
- `default_ttl`: TTL padrão
- `cache_prefix`: Prefixo das chaves de cache
- `table_map_prefix`: Prefixo do mapeamento de tabelas

**Exemplo:**
```python
stats = cache.get_cache_stats()
print(f"Queries cacheadas: {stats['total_cached_queries']}")
print(f"Tabelas rastreadas: {stats['tracked_tables']}")
# {'usuarios': 3, 'pedidos': 2}
```

#### `get_table_queries(table_name) → List[str]`

Retorna lista de hashes de queries que usam uma tabela específica.

**Parâmetros:**
- `table_name` (str): Nome da tabela

**Retorna:** Lista de hashes de queries

**Exemplo:**
```python
hashes = cache.get_table_queries('usuarios')
print(f"Tabela 'usuarios' usada por {len(hashes)} query(ies)")
```

#### `close() → None`

Fecha conexões MySQL e Redis.

### MySQLCacheResult

#### Propriedades

- `rows`: Lista de tuplas com linhas
- `columns`: Lista de nomes de colunas
- `row_count`: Número de linhas
- `from_cache`: Boolean indicando se veio do cache
- `cache_hit`: Boolean indicando cache hit
- `cached_at`: Timestamp do cache (ou None)
- `query`: Query executada

#### Métodos

- `fetchone()`: Retorna próxima linha
- `fetchmany(size=1)`: Retorna múltiplas linhas
- `fetchall()`: Retorna todas as linhas
- `as_dict()`: Retorna lista de dicionários

## 🔧 Exemplos Avançados

### Exemplo 1: Múltiplas Conexões

```python
# Cache para banco de produção
prod_cache = MySQLRedisCache(
    mysql_config={'host': 'prod-db', ...},
    redis_config={'host': 'prod-redis', ...},
    default_ttl=7200
)

# Cache para banco de analytics
analytics_cache = MySQLRedisCache(
    mysql_config={'host': 'analytics-db', ...},
    redis_config={'host': 'analytics-redis', ...},
    default_ttl=300
)
```

### Exemplo 2: Tratamento de Erros

```python
try:
    result = cache.execute("SELECT * FROM usuarios")
    if result.from_cache:
        print("✓ Resultado do cache")
    else:
        print("✓ Resultado do MySQL")
except mysql.connector.Error as e:
    print(f"Erro no MySQL: {e}")
except Exception as e:
    print(f"Erro geral: {e}")
```

### Exemplo 3: Invalidação Automática com JOINs

```python
# Cachear query com JOIN
query_join = """
    SELECT u.nome, u.email, p.total, p.data
    FROM usuarios u
    INNER JOIN pedidos p ON u.id = p.user_id
    WHERE u.status = 'ativo'
"""

result1 = cache.execute(query_join)
print(f"Cache hit? {result1.from_cache}")  # False (primeira vez)

result2 = cache.execute(query_join)
print(f"Cache hit? {result2.from_cache}")  # True (segunda vez)

# UPDATE em qualquer tabela do JOIN invalida AUTOMATICAMENTE
cache.execute("UPDATE usuarios SET nome = 'João' WHERE id = 1")
# [INFO] Cache invalidado automaticamente: 1 entrada(s) das tabelas ['usuarios']

result3 = cache.execute(query_join)
print(f"Cache hit? {result3.from_cache}")  # False (dados atualizados!)

# Também funciona com INSERT e DELETE
cache.execute("INSERT INTO pedidos (user_id, total) VALUES (1, 99.90)")
# [INFO] Cache invalidado automaticamente: 1 entrada(s) das tabelas ['pedidos']
```

### Exemplo 4: Gerenciamento de Cache por Tabela

```python
# Verificar quais queries usam uma tabela
hashes = cache.get_table_queries('usuarios')
print(f"Tabela 'usuarios' é usada por {len(hashes)} query(ies)")

# Invalidar apenas caches de uma tabela específica
deleted = cache.invalidate_cache_by_table('pedidos')
print(f"Invalidados {deleted} cache(s) da tabela 'pedidos'")

# Ver estatísticas detalhadas
stats = cache.get_cache_stats()
print(f"Tabelas rastreadas:")
for table, count in stats['tracked_tables'].items():
    print(f"  - {table}: {count} query(ies)")
```

### Exemplo 5: Configuração com Variáveis de Ambiente

```python
import os
from dotenv import load_dotenv

load_dotenv()

mysql_config = {
    'host': os.getenv('MYSQL_HOST', 'localhost'),
    'user': os.getenv('MYSQL_USER', 'root'),
    'password': os.getenv('MYSQL_PASSWORD'),
    'database': os.getenv('MYSQL_DATABASE')
}

redis_config = {
    'host': os.getenv('REDIS_HOST', 'localhost'),
    'port': int(os.getenv('REDIS_PORT', 6379)),
    'db': int(os.getenv('REDIS_DB', 0))
}

cache = MySQLRedisCache(mysql_config, redis_config)
```

## 🧪 Testes

O projeto inclui testes unitários e de integração completos.

### Instalando Dependências de Teste

```bash
pip install -r requirements.txt
```

### Testes Unitários (com Mocks)

Testes rápidos que não requerem MySQL ou Redis rodando:

```bash
# Executar todos os testes
pytest test_mysql_redis_cache.py -v

# Com cobertura de código
pytest test_mysql_redis_cache.py --cov=mysql_redis_cache --cov-report=html

# Executar testes específicos
pytest test_mysql_redis_cache.py::TestMySQLRedisCache::test_extract_tables_with_join -v
```

**Testes unitários incluem:**
- ✅ Sanitização e hash de queries
- ✅ Extração de tabelas (FROM, JOIN, INSERT, UPDATE)
- ✅ Cache básico (hit/miss)
- ✅ Rastreamento de tabelas
- ✅ Invalidação automática
- ✅ Métodos de MySQLCacheResult
- ✅ Fallback em caso de erro
- ✅ Estatísticas

### Teste de Integração Ponta a Ponta

Teste completo com MySQL e Redis **REAIS**:

```bash
python test_integration.py
```

**Requisitos:**
- MySQL rodando em `localhost:3306`
- Redis rodando em `localhost:6379`
- Usuário com permissões para criar/dropar database
- Ajuste credenciais no arquivo se necessário

**O teste de integração executa:**
1. ✅ Setup automático (cria database e tabelas)
2. ✅ Cache básico de SELECT
3. ✅ Rastreamento de tabelas
4. ✅ Queries com JOIN
5. ✅ Invalidação automática (INSERT/UPDATE/DELETE)
6. ✅ Invalidação de JOINs
7. ✅ Invalidação manual por tabela
8. ✅ Métodos de resultado (fetchone, fetchall, as_dict)
9. ✅ Comparação de performance
10. ✅ Teardown automático (limpa tudo)

**Saída esperada:**
```
╔══════════════════════════════════════════════════════════════════╗
║               TESTE DE INTEGRAÇÃO PONTA A PONTA                  ║
╚══════════════════════════════════════════════════════════════════╝

======================================================================
SETUP: Criando banco de dados e tabelas
======================================================================
  ✓ Database test_mysql_redis_cache removido (se existia)
  ✓ Database test_mysql_redis_cache criado
  ✓ Tabela 'usuarios' criada
  ✓ Tabela 'pedidos' criada
  ✓ 5 usuários inseridos
  ✓ 5 pedidos inseridos
  ✓ Setup completo!

...

======================================================================
RESUMO DOS TESTES
======================================================================
Total de testes: 10
Passaram: 10 ✓
Falharam: 0 ✗

🎉 TODOS OS TESTES PASSARAM COM SUCESSO! 🎉
```

### Executar Todos os Testes

```bash
# Testes unitários + cobertura
pytest test_mysql_redis_cache.py -v --cov=mysql_redis_cache

# Teste de integração (requer MySQL e Redis)
python test_integration.py
```

## 🐛 Troubleshooting

### Redis não conecta

**Sintoma:**
```
[AVISO] Falha ao conectar ao Redis: Connection refused
[AVISO] Continuando sem cache...
```

**Solução:**
1. Verificar se Redis está rodando: `redis-cli ping`
2. Verificar configuração de host/porta
3. Verificar firewall

### Queries não sendo cacheadas

**Possíveis causas:**
1. Query não é SELECT
2. Query tem parâmetros (`params` fornecido)
3. Cache desabilitado
4. Redis indisponível

**Debug:**
```python
result = cache.execute(query)
print(f"From cache: {result.from_cache}")
print(f"Cache enabled: {cache.cache_enabled}")
stats = cache.get_cache_stats()
print(stats)
```

### Performance não melhora

**Checklist:**
1. Verificar se queries são idênticas (diferenças mínimas geram hashes diferentes)
2. Verificar TTL (pode ter expirado)
3. Verificar tamanho do resultado (resultados grandes podem ser lentos para serializar)
4. Verificar latência da rede com Redis

## 📊 Performance

### Benchmarks Típicos

| Cenário | MySQL | Redis Cache | Melhoria |
|---------|-------|-------------|----------|
| Query simples (10 rows) | 50ms | 2ms | 25x |
| Query complexa (100 rows) | 200ms | 5ms | 40x |
| Query JOIN (1000 rows) | 800ms | 15ms | 53x |

### Otimizações

1. **TTL adequado**: Não muito curto (aumenta misses) nem muito longo (dados desatualizados)
2. **Sanitização**: Queries normalizadas geram mais hits
3. **Invalidação estratégica**: Invalidar apenas queries afetadas por UPDATEs
4. **Redis local**: Menor latência de rede

## 📝 Notas Importantes

1. **Rastreamento automático de tabelas**: Toda query SELECT registra automaticamente as tabelas usadas
2. **Invalidação automática**: INSERT/UPDATE/DELETE invalidam TODOS os caches das tabelas afetadas
3. **JOINs suportados**: Queries com múltiplas tabelas são rastreadas corretamente
4. **Queries parametrizadas não são cacheadas** por padrão (segurança)
5. **FLUSH ALL remove TUDO do Redis**, não apenas caches deste módulo
6. **Fallback automático**: Em caso de falha do Redis, sempre usa MySQL
7. **Thread-safety**: Não é thread-safe, use uma instância por thread
8. **Transações**: Cache não participa de transações MySQL
9. **Extração de tabelas**: Usa regex para identificar tabelas em FROM, JOIN, INTO, UPDATE

## 🤝 Contribuindo

Contribuições são bem-vindas! Por favor:

1. Fork o projeto
2. Crie uma branch para sua feature
3. Commit suas mudanças
4. Push para a branch
5. Abra um Pull Request

## 📄 Licença

MIT License - veja LICENSE para detalhes.

## 🆘 Suporte

Para problemas e dúvidas:
- Abra uma issue no GitHub
- Consulte a documentação
- Verifique os exemplos em `example.py`

## 🔮 Roadmap

- [x] ~~Rastreamento de tabelas e invalidação automática~~
- [x] ~~Suporte completo a JOINs com múltiplas tabelas~~
- [ ] Suporte a queries parametrizadas cacheadas
- [ ] Compressão de resultados grandes
- [ ] Métricas detalhadas (hit rate, latência, cache miss rate)
- [ ] Suporte a múltiplos backends de cache (Memcached, etc)
- [ ] Parser SQL mais robusto (usando sqlparse)
- [ ] Interface CLI para gestão de cache
- [ ] Warm-up automático de cache
- [ ] Cache de prepared statements
