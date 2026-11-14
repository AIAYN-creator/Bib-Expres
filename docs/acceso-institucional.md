# Acceso a los papers: abierto, biblioteca y "solo lo que puedo leer"

bib_exprés no puede saber con certeza a qué tiene acceso tu institución: esa información vive en los sistemas de cada biblioteca, detrás de su login. Lo que sí hace es combinar tres cosas que se pueden saber:

1. **Si el paper es de acceso abierto**, según OpenAlex, y el enlace a esa versión libre.
2. **Un enlace a través de tu biblioteca**, para que el paper se abra como si estuvieras en el campus (el login lo haces tú en el navegador, como siempre).
3. **Qué editoriales cubre tu institución**, marcadas por ti, para filtrar de forma aproximada.

bib_exprés **no pasa ninguna petición por el proxy de tu biblioteca ni guarda credenciales**: solo construye enlaces que se abren en tu navegador.

## Estado de acceso de cada artículo

| Estado | Significa |
|---|---|
| **abierto** | Hay una versión libre (enlace "Abrir versión libre") |
| **abierto (bronze)** | Gratis en la web de la editorial, pero sin licencia abierta: puede dejar de estarlo |
| **institución** | No es abierto, pero su editorial (o la editorial matriz: *Cell Press* cuenta como *Elsevier*) está en tu lista |
| **sin acceso conocido** | No es abierto y su editorial no está en tu lista |
| **no comprobado** | No hay datos para saberlo (sin editorial conocida, o aún no has marcado editoriales) |

Aparece en la pantalla de resultados y en las columnas **Acceso** y **Enlace de acceso** del Excel.

## 1. El enlace de tu biblioteca

En la GUI: **Ajustes → Enlace de tu biblioteca**. En la CLI: `--library-link`, o `LIBRARY_LINK_TEMPLATE` en el `.env`.

### Cómo encontrarlo

1. Desde casa (fuera de la red de la universidad), entra en la web de tu biblioteca y abre cualquier artículo de una revista suscrita desde su buscador o catálogo.
2. Cuando llegues al artículo, mira la URL del navegador:
   - **Si contiene `login?url=`** (EZproxy, el más común): copia todo hasta `login?url=` incluido. Ejemplo: `https://proxy.tu-uni.es/login?url=`
   - **Si contiene `go.openathens.net/redirector/`** (OpenAthens): copia hasta `?url=` incluido. Ejemplo: `https://go.openathens.net/redirector/tu-uni.es?url=`
   - **Si la URL del artículo tiene un dominio raro** del estilo `www-sciencedirect-com.proxy.tu-uni.es`, también es EZproxy, en su variante que reescribe dominios. Busca en la web de tu biblioteca "acceso remoto" o "EZproxy": casi siempre documentan el enlace `login?url=`.
3. Si no encuentras nada, pregunta en tu biblioteca por **"el prefijo del proxy para acceso remoto"**. Es una pregunta habitual y saben responderla.

### Formatos admitidos

- **Prefijo** (EZproxy, OpenAthens): bib_exprés le añade el enlace `https://doi.org/...` del paper.
- **Con `{doi}` o `{url}`** (resolvedores OpenURL, p.ej. Alma/Primo o SFX): se sustituyen por el DOI o por el enlace de doi.org. Ejemplo: `https://resolver.tu-uni.es/openurl?rft_id=info:doi/{doi}`

Solo se aceptan enlaces `https://`. El botón **"Probar con un paper conocido"** abre un artículo de *Nature* a través de tu enlace: si después del login ves el artículo completo, está bien configurado.

## 2. Las editoriales de tu institución

En la pantalla de resultados, el panel **"Mi institución: qué puedo leer"** muestra las editoriales que aparecen en tu búsqueda, con cuántos artículos tiene cada una. Marca las que cubre tu institución y pulsa **"Guardar mis editoriales"**: se recuerdan para las siguientes búsquedas (`SUBSCRIBED_PUBLISHERS` en el `.env`). En la CLI: `--publishers "Elsevier BV;Springer Nature"`.

Si no sabes cuáles cubre tu universidad, la web de la biblioteca suele tener una lista de "recursos suscritos", "bases de datos" o "revistas electrónicas" por editorial.

**Es aproximado**: un contrato con una editorial no siempre cubre todas sus revistas ni todos los años.

## 3. "Ocultar lo que no puedo leer"

- Casilla en el mismo panel, o `--accessible-only` en la CLI. Oculta los artículos **sin acceso conocido**.
- Los **no comprobados** se mantienen, porque un dato que falta no es motivo para excluir. Para ocultarlos también: la segunda casilla, o `--strict-access`.
- El filtro se aplica **sobre los resultados**, no durante la búsqueda: que no puedas leer un paper no lo hace menos relevante, ni impide llegar a otros que sí puedes leer.
- El paper de partida nunca se oculta.
- Lo oculto no se exporta ni aparece en la curación.

## Privacidad

El enlace de tu biblioteca y tu lista de editoriales se guardan en texto plano en el `.env`. No son secretos, pero revelan a qué institución perteneces. Ten cuidado al compartir esa carpeta.
