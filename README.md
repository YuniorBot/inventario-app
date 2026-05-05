# Inventario App

Aplicacion Flask para gestionar inventarios de inmuebles, evidencia multimedia, observaciones, firmas y vista publica por token.

## Stack actual

- Flask
- Flask-SQLAlchemy
- Flask-Migrate / Alembic
- PostgreSQL o SQLite para desarrollo local temporal

## Configuracion

Usa variables de entorno. Puedes tomar `.env.example` como referencia.

Variables principales:

- `SECRET_KEY`
- `DATABASE_URL`
- `STORAGE_ROOT`
- `SUPERADMIN_NAME`
- `SUPERADMIN_EMAIL`
- `SUPERADMIN_PASSWORD`
- `MAX_CONTENT_LENGTH`
- `REDIS_URL`
- `PDF_QUEUE_NAME`
- `PDF_JOB_TIMEOUT_SECONDS`

## Storage local persistente

La aplicacion ya no depende de `static/uploads` ni `static/pdfs` como almacenamiento principal.

- `STORAGE_ROOT` define la raiz persistente del almacenamiento local.
- Por defecto se usa `instance/storage/`.
- La app crea automaticamente:
  - `uploads/`
  - `pdfs/`

Los archivos se sirven por rutas internas de la app:

- `/media/uploads/<archivo>`
- `/media/pdfs/<archivo>`

Esto permite mover el storage fuera del repo sin romper templates ni enlaces.

## Desarrollo con PostgreSQL

1. Crea una base local, por ejemplo `inventario_app`.
2. Configura `DATABASE_URL`, por ejemplo:

```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/inventario_app
STORAGE_ROOT=C:/ruta/persistente/inventario-storage
```

3. Instala dependencias:

```bash
pip install -r requirements.txt
```

4. Ejecuta migraciones:

```bash
flask --app app db upgrade
```

5. Arranca la aplicacion:

```bash
python run_local.py
```

6. Para generar PDFs en segundo plano, inicia Redis y ejecuta el worker en otra terminal:

```bash
python worker.py
```

En produccion deben existir dos procesos: `web` para Flask/Gunicorn y `worker` para la cola de PDFs. La ruta de generacion solo encola el trabajo; el worker crea el archivo y actualiza el estado en la base de datos.

## Migraciones

Crear una nueva migracion:

```bash
flask --app app db migrate -m "descripcion"
```

Aplicarla:

```bash
flask --app app db upgrade
```

Revision actual:

```bash
flask --app app db current
```

## Mover datos desde SQLite a PostgreSQL

1. Configura `DATABASE_URL` apuntando a PostgreSQL.
2. Ejecuta el esquema en PostgreSQL:

```bash
flask --app app db upgrade
```

3. Importa datos desde el archivo SQLite existente:

```bash
flask --app app import-sqlite --source inventario.db --reset-target
```

Esto copia, en orden, las tablas:

- `empresa`
- `usuario`
- `inmueble`
- `inventario`
- `seccion`
- `foto`
- `observacion`
- `firma`

Despues del import, la app vuelve a garantizar el seed inicial si faltara el superadmin.

## Utilidad

Ver la URL de base de datos efectiva:

```bash
flask --app app show-db-url
```
