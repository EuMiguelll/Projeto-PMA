# Auth

**Repositórios:** [`auth`](https://github.com/canavero/auth) (interface) ·
[`auth-service`](https://github.com/canavero/auth-service) · pacote `store.auth`

Autenticação e autorização (hands-on 3): registra contas (delegando ao `account`), faz login
emitindo um **JWT HS256** em cookie `HttpOnly`, e resolve tokens para o gateway. Nunca vê o hash
da senha: quem confere a senha é o `account` (`POST /accounts/login`).

| Método | Caminho | Descrição | Respostas |
|--------|---------|-----------|-----------|
| POST | `/auth/register` | cria a conta via Feign no `account` | 200, 400, 409, 503 |
| POST | `/auth/login` | valida credenciais e devolve `Set-Cookie: __store_jwt_token=<JWT>` | 200, 401, 503 |
| GET | `/auth/me` | conta logada (header `id-account` colocado pelo gateway) | 200, 404 |
| POST | `/auth/solve` | **interno**: `{token}` → `{idAccount}` (usado pelo gateway) | 200, 401 |
| GET | `/auth/logout` | apaga o cookie (`Max-Age=0`) | 200 |

Claims do token: `jti` = id da conta, `sub` = nome, `email`, `iss` = `Insper::PMA`, `nbf`, `exp`
(1 h). A chave vem de `JWT_SECRET_KEY` (Base64, 256 bits; o `deploy.sh` gera uma aleatória no
Kubernetes — a de desenvolvimento do `application.yaml` é pública).

=== "AuthService.java"

    ```java
    --8<-- "api/auth-service/src/main/java/store/auth/AuthService.java"
    ```

=== "JwtService.java"

    ```java
    --8<-- "api/auth-service/src/main/java/store/auth/JwtService.java"
    ```

=== "AuthController.java (interface)"

    ```java
    --8<-- "api/auth/src/main/java/store/auth/AuthController.java"
    ```

=== "application.yaml"

    ```yaml
    --8<-- "api/auth-service/src/main/resources/application.yaml"
    ```

**Bottleneck:** circuit breaker Resilience4j nas chamadas ao `account` — ver
[Bottlenecks](bottlenecks.md#2-circuit-breaker-e-retry-auth-e-exchange).

## Testes

`AuthServiceTest`: token carrega o id da conta; token assinado com outra chave → 401; token
expirado → 401; circuito aberto (`CallNotPermittedException`) → 503.
