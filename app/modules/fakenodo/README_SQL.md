# Fakenodo - Simulador de Zenodo con SQL

## 📋 Descripción

Fakenodo es un **simulador completo de Zenodo** que usa **base de datos SQL** en lugar de archivos JSON.

### ✅ Ventajas de SQL vs JSON

| Aspecto | JSON (anterior) | SQL (actual) |
|---------|----------------|--------------|
| **Persistencia en Render** | ❌ Se pierde en cada reinicio | ✅ Permanente en BD |
| **Concurrencia** | ❌ Requiere locks manuales | ✅ Manejada por SQL |
| **Escalabilidad** | ❌ Una instancia | ✅ Múltiples instancias |
| **Consultas** | ❌ Carga todo en memoria | ✅ Queries eficientes |
| **Testing** | ⚠️ Interfiere entre tests | ✅ Aislado por transacciones |

---

## 🗄️ Estructura de Base de Datos

### Tablas creadas (migración `008_add_fakenodo_tables.py`):

1. **`fakenodo_deposition`** - Depositions principales
2. **`fakenodo_file`** - Archivos subidos
3. **`fakenodo_version`** - Historial de versiones publicadas

---

## 🚀 Configuración

### **Desarrollo Local (usar Fakenodo):**
```env
# .env
FAKENODO_URL=http://localhost:5000/fakenodo
```

### **Producción Render (usar Zenodo real):**
```env
# .env en Render
FLASK_ENV=production
ZENODO_ACCESS_TOKEN=tu_token_real

# NO incluir FAKENODO_URL ni USE_FAKE_ZENODO
```

### **Testing en Render con Fakenodo:**
```env
# .env en Render (staging)
USE_FAKE_ZENODO=true
# ✅ Los datos persisten en SQL entre reinicios
```

---

## 🔄 Aplicar Migración

```bash
# 1. Aplicar migración
flask db upgrade

# 2. Verificar
mysql -u usuario -p base_datos
> SHOW TABLES LIKE 'fakenodo%';
```

---

## 📝 Ejemplo de Uso

```python
from app.modules.fakenodo.services import FakenodoService

service = FakenodoService()

# 1. Crear deposition
dep = service.create_deposition(metadata={"title": "Dataset"})
# → {'id': 1, 'state': 'draft', 'dirty': False}

# 2. Subir archivo
with open("weather.csv", "rb") as f:
    service.upload_file(1, "weather.csv", f.read())
# → Marca dirty=True

# 3. Publicar (crea versión)
v1 = service.publish_deposition(1)
# → {'version': 1, 'doi': '10.1234/fakenodo.1.v1'}

# 4. Subir otro archivo y republicar
with open("weather2.csv", "rb") as f:
    service.upload_file(1, "weather2.csv", f.read())

v2 = service.publish_deposition(1)
# → {'version': 2, 'doi': '10.1234/fakenodo.1.v2'}
```

---

## 🔍 Ver Datos en BD

```sql
-- Listar depositions
SELECT id, state, published, dirty, doi FROM fakenodo_deposition;

-- Ver archivos de un deposition
SELECT name, size FROM fakenodo_file WHERE deposition_id = 1;

-- Ver historial de versiones
SELECT version, doi, created_at FROM fakenodo_version
WHERE deposition_id = 1 ORDER BY version DESC;
```

---

## 🧪 Testing

```bash
pytest app/modules/fakenodo/tests/ -v
```

Los tests ahora usan la BD de prueba en lugar de archivos JSON.

---

## ⚠️ Importante

- **Eliminar `fakenodo_db.json` si existe**: Ya no se usa
- **Cascade deletes**: Al borrar un deposition se borran sus archivos/versiones
- **No mezclar JSON y SQL**: Usa solo uno de los dos

---

## 📚 Documentación Completa

Ver README anterior para más detalles sobre:
- API de Zenodo emulada
- Workflow de versionado
- Testing avanzado
- Comparación con Zenodo real
