# Exchange

**Repositórios:** [`exchange`](https://github.com/canavero/exchange) (interface) ·
[`exchange-service`](https://github.com/canavero/exchange-service) · pacote `store.exchange`

Cotações de câmbio (exercício *Exchange API*): `GET /exchanges/{from}/{to}` consulta a
[AwesomeAPI](https://docs.awesomeapi.com.br/api-de-moedas) (gratuita, sem chave) e responde no
formato pedido pelo enunciado. Exige usuário autenticado (o gateway injeta o `id-account`).

```http
GET /exchanges/USD/BRL
Cookie: __store_jwt_token=...

200 OK
{"sell":5.668,"buy":5.6666,"date":"2026-11-13 18:30:13","id-account":"7586833b-189d-4f47-a27d-0cf8589a8b3b"}
```

`sell` = `ask` (preço de venda) e `buy` = `bid` (preço de compra) da AwesomeAPI. Par inválido
(ex.: `XXX/YYY`) → 404; provedor fora do ar → 503.

!!! note "Por que Java e não Python?"
    O exercício individual *Exchange API* pede FastAPI/Python. No projeto, o Exchange foi feito
    em **Spring Boot**, como os outros três serviços, para manter um único padrão
    (módulo de interface Feign `exchange` reutilizável pelo futuro `order-service`, mesmo
    pipeline de CI, mesmo Dockerfile, mesmas métricas/probes). O contrato HTTP é o do enunciado,
    então o serviço é intercambiável com uma versão FastAPI.

=== "ExchangeService.java"

    ```java
    --8<-- "api/exchange-service/src/main/java/store/exchange/ExchangeService.java"
    ```

=== "ExchangeResource.java"

    ```java
    --8<-- "api/exchange-service/src/main/java/store/exchange/ExchangeResource.java"
    ```

=== "ExchangeController.java (interface)"

    ```java
    --8<-- "api/exchange/src/main/java/store/exchange/ExchangeController.java"
    ```

=== "application.yaml"

    ```yaml
    --8<-- "api/exchange-service/src/main/resources/application.yaml"
    ```

**Bottlenecks:** cache Redis de 60 s + retry com backoff + circuit breaker na API de terceiros —
ver [Bottlenecks](bottlenecks.md).

## Testes

`ExchangeServiceTest` — `MockRestServiceServer` simula a AwesomeAPI e confere o mapeamento
`ask → sell`, `bid → buy`, `create_date → date`.
