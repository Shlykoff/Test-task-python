# Микросервисы онлайн-магазина

Актуальная короткая инструкция: запуск с нуля, тесты, сиды, базовая проверка.

## Требования

- Docker
- Docker Compose plugin (`docker compose`)
- свободные порты: `80`, `5432`, `5672`, `6379`, `3000`, `9090`, `15672`, `16686`, `3100`

## Быстрый старт с нуля

```bash
cp .env.example .env
```

Сгенерируй JWT-ключи (если `keys/jwt_private.pem` и `keys/jwt_public.pem` отсутствуют):

```bash
mkdir -p keys
python3 -c "
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
pk = rsa.generate_private_key(65537, 2048)
pub = pk.public_key()
open('keys/jwt_private.pem','wb').write(pk.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
open('keys/jwt_public.pem','wb').write(pub.public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
"
```

Подними весь стек:

```bash
docker compose up --build -d
```

Проверь, что всё работает:

```bash
docker compose ps
curl http://localhost/health
```

## Что поднимается

- API Gateway + UI: `nginx` (`http://localhost`)
- сервисы: `auth`, `user`, `product`, `cart`, `order`, `billing`, `notification`
- инфраструктура: `postgres`, `postgres-test`, `redis`, `rabbitmq`
- наблюдаемость: `prometheus`, `grafana`, `jaeger`, `loki`, `promtail`

## Сиды

Сиды создаются при старте приложений:

- `user-service`: пользователь `testuser / testpassword`
- `product-service`: 15 товаров

Важно:

- сиды находятся в `postgres`, а не в `postgres-test`
- сиды идемпотентны (повторно не дублируются)
- при существующем volume PostgreSQL данные сохраняются между перезапусками

Проверка сидов:

```bash
docker exec postgres psql -U postgres -d users -c "select id, username, email, balance from users;"
docker exec postgres psql -U postgres -d products -c "select count(*) from products;"
```

## Запуск тестов

Все тесты в контейнерах:

```bash
for svc in auth-service user-service product-service cart-service order-service billing-service notification-service; do
  echo "=== $svc ==="
  docker compose run --rm "$svc" pytest -q
done
```

## Актуальные URL

- UI: `http://localhost`
- Swagger gateway: `http://localhost/docs`
- Swagger сервисов:
  - `http://localhost/auth/docs`
  - `http://localhost/user/docs`
  - `http://localhost/products/docs`
  - `http://localhost/cart/docs`
  - `http://localhost/orders/docs`
  - `http://localhost/billing/docs`
  - `http://localhost/notifications/docs`

## Актуальные API-префиксы

Все HTTP-роуты сервисов идут через префикс `/api`.

Через gateway:

- `/auth/api/...`
- `/user/api/...`
- `/products/api/...`
- `/cart/api/...`
- `/orders/api/...`
- `/billing/api/...`
- `/notifications/api/...`

WebSocket:

- `/ws/notifications?token=<jwt>`

## Минимальная smoke-проверка

```bash
# Товары
curl http://localhost/products/api/products

# Логин сид-пользователем
curl -X POST http://localhost/auth/api/token \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","password":"testpassword"}'
```

## Остановка и полный сброс

Остановить:

```bash
docker compose down
```

Полный сброс (включая volume БД):

```bash
docker compose down -v
docker compose up --build -d
```
