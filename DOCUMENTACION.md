# Documentación del Proyecto: Cam-manager

Servidor Flask para gestión de múltiples cámaras en tiempo real. Cada cámara opera en su propio hilo de captura, permitiendo visualización, grabación manual, detección de movimiento y notificaciones por Telegram de forma totalmente independiente.

## Dependencias

- **Flask**: Servidor web y streaming MJPEG.
- **OpenCV (`cv2`)**: Captura de video, procesamiento y detección de movimiento.
- **Requests**: API de Telegram (notificaciones, fotos y videos).

## Estructura de Configuración (`config.json`)

```json
{
    "telegram_token": "...",
    "chat_id": "...",
    "cameras": [
        { "id": "camara1", "device_index": 0, "ancho": 640, "alto": 480 }
    ]
}
```

Cada cámara se define con un `id` único, su `device_index` en el sistema, y resolución por defecto.

## Backend (`app.py`)

### Clase `CameraSession`

Encapsula el estado y la lógica de una cámara individual:

- **`start_camera()`**: Abre el dispositivo con reintentos degradando resolución (`config → 640x480 → 320x240`). Si falla y no es la cámara interna, ejecuta un **ISP warm-up** (abre brevemente `video0` para despertar el subsistema de video del Chromebook) y reintenta.
- **`process_frame()`**: Lee un frame, lo espeja horizontalmente, ejecuta detección de movimiento si está activa, y maneja la escritura de video (manual o por detección).
- **`stop_camera()`**: Libera la cámara y el `video_writer` si existe.
- **`run()`**: Bucle infinito en un hilo dedicado. Cada cámara tiene su propio hilo.

### Funciones de Telegram

| Función | Propósito |
|---------|-----------|
| `enviar_notificacion_telegram(mensaje)` | Envía texto a Telegram |
| `enviar_video_telegram(ruta_video)` | Envía archivo MP4 mediante `sendVideo`. Valida tamaño mínimo de 1KB |
| `enviar_foto_telegram(ruta_foto)` | Envía archivo JPG mediante `sendPhoto` |

### Grabación

- **Manual**: El usuario inicia/detiene desde la interfaz. Se envía a Telegram al detener si hay frames válidos (>5 o >50KB).
- **Automática (detección de movimiento)**: Se activa por 10 segundos al detectar cambio significativo en la escena. Se envía a Telegram al cumplirse el tiempo si hay frames válidos.
- **Control de frames válidos**: Se verifica `frames_grabados > 5` y tamaño en disco > 1KB antes de enviar.

### Endpoints API

| Ruta | Método | Descripción |
|------|--------|-------------|
| `/` | GET | Interfaz web (rejilla CCTV) |
| `/video_feed/<cam_id>` | GET | Stream MJPEG de una cámara |
| `/listar_camaras` | GET | Lista de cámaras disponibles (configuradas + detectadas) |
| `/status/<cam_id>` | GET | Estado de una cámara `{active, recording, motion}` |
| `/toggle_camara` | POST | Enciende/apaga una cámara. Body: `{camera_id}` |
| `/toggle_video` | POST | Inicia/detiene grabación manual. Body: `{camera_id}` |
| `/toggle_deteccion` | POST | Activa/desactiva detección de movimiento. Body: `{camera_id}` |
| `/tomar_foto` | POST | Captura y guarda foto, la envía a Telegram. Body: `{camera_id}` |
| `/set_resolucion` | POST | Cambia resolución de una cámara. Body: `{camera_id, ancho, alto}` |

## Frontend (`templates/index.html`)

- Interfaz tipo **rejilla CCTV** responsiva (`CSS Grid`).
- Cada cámara se muestra en una tarjeta independiente con visor MJPEG y controles propios (Encender, Foto, Grabar, Detección, Resolución).
- Sincronización periódica cada 3 segundos con el backend para reflejar cambios de estado.

## Flujo de Detección de Movimiento

1. La cámara debe estar encendida y el modo detección activado.
2. Se calcula un `background_frame` inicial (escala de grises + desenfoque).
3. Cada frame se compara con el fondo. Si la diferencia supera el umbral (25000 píxeles), se inicia grabación automática de 10 segundos.
4. Al cumplirse los 10 segundos, el video se envía a Telegram.

## Arquitectura de Hilos

- Cada cámara definida en `config.json` lanza su propio hilo de captura al iniciar el servidor.
- Las cámaras detectadas dinámicamente (`videoX`) también reciben su propio hilo al ser usadas por primera vez (`get_or_create_session`).
- El acceso a recursos compartidos (estado de la cámara, writer) está protegido con `threading.Lock`.

## Notas de Hardware

- En Chromebooks, la cámara USB externa (`video2+`) puede fallar si el subsistema ISP no se ha inicializado abriendo la cámara interna al menos una vez. El backend maneja esto automáticamente con ISP warm-up.
- El formato MJPEG se fuerza para reducir ancho de banda USB y evitar errores `Insufficient buffer memory`.
