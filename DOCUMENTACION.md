# Documentación del Proyecto: Cam-manager

Este servidor Flask se encarga de gestionar una cámara conectada al sistema, permitiendo visualización en tiempo real, captura de fotos, grabación manual y detección de movimiento automática con notificaciones y envío de videos a Telegram.

## Estructura General

### Dependencias Principales
- **Flask:** Servidor web para la interfaz y el streaming de video.
- **OpenCV (`cv2`):** Captura de video, procesamiento de imágenes y detección de movimiento.
- **Requests:** Comunicación con la API de Telegram.

---

## Lógica del Backend (`app.py`)

### Funciones de Utilidad y Notificaciones

- **`cargar_config()`**: Lee `config.json` para obtener el `telegram_token` y `chat_id`.
- **`enviar_notificacion_telegram(mensaje)`**: Envía mensajes de texto a través del bot de Telegram.
- **`enviar_video_telegram(ruta_video)`**: Envía archivos de video grabados a Telegram usando `sendVideo`.

### Hilo de Fondo (`capturar_camara_fondo`)
Es el corazón del sistema. Se ejecuta en un hilo separado para no bloquear el servidor web.

1.  **Gestión de la Cámara**: Si `camara_activa` es `True`, inicializa `cv2.VideoCapture(0)`.
2.  **Procesamiento de Frames**:
    *   Captura el frame, lo redimensiona y aplica inversión (`flip`).
    *   **Detección de Movimiento**:
        *   Convierte el frame a escala de grises y aplica desenfoque gaussiano.
        *   Compara el frame actual con un `background_frame`.
        *   Si el área de diferencia supera el umbral (`15000`), marca `grabando = True`.
    *   **Grabación Automática**:
        *   Si `grabando` es `True`, escribe frames a un archivo MP4.
        *   La grabación dura 10 segundos, tras los cuales se libera el archivo y se envía por Telegram automáticamente.

### Endpoints (API)

| Ruta | Método | Descripción |
| :--- | :--- | :--- |
| `/` | GET | Sirve la interfaz web (`index.html`). |
| `/video_feed` | GET | Stream de video en vivo (multipart). |
| `/toggle_deteccion` | POST | Activa/Desactiva el modo de detección de movimiento. |
| `/toggle_camara` | POST | Enciende o apaga la cámara. |
| `/tomar_foto` | POST | Guarda una instantánea (`.jpg`) en `CARPETA_CAPTURAS`. |
| `/toggle_video` | POST | Inicia/Detiene grabación manual. |
| `/set_resolucion` | POST | Recibe JSON `{ancho, alto}` para ajustar la cámara. |

---

## Configuración y Variables Globales

- **`CARPETA_CAPTURAS`**: Ruta definida para almacenar fotos y videos (`/mnt/sd/Cam-capturas`).
- **`config`**: Almacena credenciales de Telegram.
- **`modo_deteccion`**: Booleano que indica si el sistema está analizando cambios en la escena.
- **`grabando`**: Booleano que indica si el `video_writer` está activo.

## Flujo de Trabajo (Detección de Movimiento)
1. El sistema inicia en modo espera.
2. Si `modo_deteccion` es activado, el sistema calcula el "background frame".
3. Al detectar movimiento, activa la variable `grabando`.
4. El hilo de fondo crea un `VideoWriter`.
5. Tras 10 segundos, el hilo cierra el `VideoWriter`, llama a `enviar_video_telegram` y espera a nueva detección.
