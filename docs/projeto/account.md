# Account

**Repositórios:** [`account`](https://github.com/canavero/account) (interface) ·
[`account-service`](https://github.com/canavero/account-service) · pacote `store.account`

CRUD de contas (hands-on 1) em arquitetura limpa: `AccountResource` (controller) →
`AccountService` (regras) → `AccountRepository` (JPA) → PostgreSQL, com conversões por
`AccountParser` (`AccountIn → Account → AccountModel` e volta). O schema `accounts` é criado
pelo **Flyway** (`V2026.08.24.001__create_schema.sql`, `...002__create_table.sql`).

| Método | Caminho | Sucesso | Erros |
|--------|---------|---------|-------|
| POST | `/accounts` | 201 + `Location: /accounts/{id}` | 400 (nome/email vazios, senha < 6), **409 (email já cadastrado)** |
| GET | `/accounts` | 200 lista de `AccountOut` | — |
| GET | `/accounts/{id}` | 200 `AccountOut` (**cacheado no Redis**) | 404 |
| DELETE | `/accounts/{id}` | 204 (remove também do cache) | — |
| POST | `/accounts/login` | 200 `AccountOut` | 400, 401 |
| GET | `/accounts/health-check` | 200 | — |

A senha nunca é guardada: só o hash SHA-256 (Base64) na coluna `hash_password`, e o
`AccountOut` não tem campo de senha. Melhorias em relação à referência: validação do nome e do
e-mail duplicado (409 em vez de 500 vindo da constraint `UNIQUE`).

=== "AccountService.java"

    ```java
    --8<-- "api/account-service/src/main/java/store/account/AccountService.java"
    ```

=== "AccountResource.java"

    ```java
    --8<-- "api/account-service/src/main/java/store/account/AccountResource.java"
    ```

=== "AccountController.java (interface)"

    ```java
    --8<-- "api/account/src/main/java/store/account/AccountController.java"
    ```

=== "application.yaml"

    ```yaml
    --8<-- "api/account-service/src/main/resources/application.yaml"
    ```

**Bottleneck:** cache Redis em `findById` — ver [Bottlenecks](bottlenecks.md#1-cache-redis-account-e-exchange).

## Testes

`AccountServiceTest` (JUnit 5 + Mockito, sem banco): senha curta → 400; e-mail duplicado → 409;
só o hash é salvo; credenciais erradas → 401.
