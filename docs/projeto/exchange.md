# Exchange

**Repositórios:** [`exchange`](https://github.com/canavero/exchange) (interface) ·
[`exchange-service`](https://github.com/canavero/exchange-service) · pacote `store.exchange`

Cotações de câmbio (exercício *Exchange API*): `GET /exchanges/{from}/{to}` consulta a
[PTAX do Banco Central](https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/aplicacao#!/recursos) (pública, sem chave) e responde no
formato pedido pelo enunciado. Exige usuário autenticado (o gateway injeta o `id-account`).

```http
GET /exchanges/USD/BRL
Cookie: __store_jwt_token=...

200 OK
{"sell":5.7525,"buy":5.7519,"date":"2026-11-16 12:06:13.954181","id-account":"bc38bdca-43ac-4a25-b42c-f3be49851e56"}
```

O PTAX só cota moedas contra o real (AUD, CAD, CHF, DKK, EUR, GBP, JPY, NOK, SEK e USD), então o
par sai **cruzado via BRL** (BRL = 1): `sell` = venda de `from` ÷ compra de `to` e `buy` = compra
de `from` ÷ venda de `to`. Em `USD/BRL`, `sell` e `buy` são a venda e a compra do dólar no boletim
mais recente dos últimos 7 dias (fim de semana e feriado não têm boletim). Moeda desconhecida
(ex.: `XXX/YYY`) → 404; BACEN fora do ar → 503.

!!! info "Por que o BACEN e não a AwesomeAPI?"
    A primeira versão usava a AwesomeAPI. No deploy real no EKS ela devolveu `429 QuotaExceeded`
    para os IPs da AWS; contornamos com uma API key (smoke test 14/14 em 15/11), mas isso exigia
    um Secret no cluster e no CI. Com o aviso do professor (16/11) de que APIs gratuitas recusam
    IPs da AWS, trocamos para o PTAX, que o enunciado sugere: público, sem chave e sem Secret. O
    cache Redis, o retry e o circuit breaker não mudaram.

!!! note "Por que Java e não Python?"
    O exercício individual *Exchange API* pede FastAPI/Python. No projeto, o Exchange foi feito
    em **Spring Boot**, como os outros três serviços, para manter um único padrão
    (módulo de interface Feign `exchange` reutilizável pelo futuro `order-service`, mesmo
    pipeline de CI, mesmo Dockerfile, mesmas métricas/probes). O contrato HTTP é o do enunciado,
    então o serviço é intercambiável com uma versão FastAPI (como o serviço do BACEN em FastAPI
    que o curso disponibiliza).

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

`ExchangeServiceTest` — `MockRestServiceServer` simula o PTAX e confere `cotacaoVenda → sell`,
`cotacaoCompra → buy`, a cotação cruzada `EUR/USD` via BRL e o 404 de moeda desconhecida.
