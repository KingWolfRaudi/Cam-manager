from flask import Flask, render_template, Response, request
import cv2
import datetime
import time
import threading
import os
import json
import requests

app = Flask(__name__)

# --- CONFIGURACIÓN ---
def cargar_config():
    with open('config.json', 'r') as f:
        return json.load(f)

config = cargar_config()

CARPETA_CAPTURAS = '/mnt/sd/Cam-capturas'

# --- NOTIFICACIONES ---
def enviar_notificacion_telegram(mensaje):
    print(f"DEBUG: Intentando enviar notificación a Telegram: {mensaje}", flush=True)
    url = f"https://api.telegram.org/bot{config['telegram_token']}/sendMessage"
    payload = {
        "chat_id": config['chat_id'],
        "text": mensaje
    }
    try:
        respuesta = requests.post(url, data=payload)
        print(f"DEBUG: Respuesta recibida: {respuesta.status_code}", flush=True)
        if respuesta.status_code == 200:
            print("Notificación enviada con éxito.", flush=True)
        else:
            print(f"Error al enviar notificación. Código: {respuesta.status_code}, Respuesta: {respuesta.text}", flush=True)
    except Exception as e:
        print(f"Error enviando notificación: {e}", flush=True)

def enviar_video_telegram(ruta_video):
    if not os.path.exists(ruta_video) or os.path.getsize(ruta_video) < 1024:
        print(f"DEBUG: Video {ruta_video} vacío o demasiado pequeño, no se envía.", flush=True)
        return
    print(f"DEBUG: Intentando enviar video a Telegram: {ruta_video}", flush=True)
    url = f"https://api.telegram.org/bot{config['telegram_token']}/sendVideo"
    
    try:
        with open(ruta_video, 'rb') as video_file:
            payload = {
                "chat_id": config['chat_id']
            }
            files = {
                "video": video_file
            }
            respuesta = requests.post(url, data=payload, files=files)
            
        print(f"DEBUG: Respuesta video recibida: {respuesta.status_code}", flush=True)
        if respuesta.status_code == 200:
            print("Video enviado con éxito.", flush=True)
        else:
            print(f"Error al enviar video. Código: {respuesta.status_code}, Respuesta: {respuesta.text}", flush=True)
    except Exception as e:
        print(f"Error enviando video: {e}", flush=True)

def enviar_foto_telegram(ruta_foto):
    if not os.path.exists(ruta_foto):
        print(f"DEBUG: Foto {ruta_foto} no existe.", flush=True)
        return
    print(f"DEBUG: Intentando enviar foto a Telegram: {ruta_foto}", flush=True)
    url = f"https://api.telegram.org/bot{config['telegram_token']}/sendPhoto"
    try:
        with open(ruta_foto, 'rb') as foto_file:
            payload = {"chat_id": config['chat_id']}
            files = {"photo": foto_file}
            respuesta = requests.post(url, data=payload, files=files)
        print(f"DEBUG: Respuesta foto recibida: {respuesta.status_code}", flush=True)
        if respuesta.status_code == 200:
            print("Foto enviada con éxito.", flush=True)
        else:
            print(f"Error al enviar foto. Código: {respuesta.status_code}, Respuesta: {respuesta.text}", flush=True)
    except Exception as e:
        print(f"Error enviando foto: {e}", flush=True)

class CameraSession:
    def __init__(self, cam_config):
        self.id = cam_config['id']
        self.device_index = cam_config['device_index']
        self.config_ancho = cam_config['ancho']
        self.config_alto = cam_config['alto']
        self.is_active = False
        self.grabando = False
        self.modo_deteccion = False
        self.video_writer = None
        self.background_frame = None
        self.frame_actual = None
        self.cam = None
        self.ultima_deteccion = 0
        self.ruta_grabacion_actual = None
        self.tiempo_inicio_grabacion = 0
        self.frames_grabados = 0
        self.fps_actual = 15
        self._lock = threading.Lock()

    def start_camera(self):
        with self._lock:
            if self.cam is not None:
                return
            ancho, alto = self.config_ancho, self.config_alto
            resoluciones_intento = [(ancho, alto), (640, 480), (320, 240)]
            for ancho_int, alto_int in resoluciones_intento:
                self.cam = cv2.VideoCapture(self.device_index, cv2.CAP_V4L2)
                if not self.cam.isOpened():
                    self.cam = cv2.VideoCapture(self.device_index)
                if self.cam.isOpened():
                    try:
                        self.cam.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
                        self.cam.set(cv2.CAP_PROP_FRAME_WIDTH, ancho_int)
                        self.cam.set(cv2.CAP_PROP_FRAME_HEIGHT, alto_int)
                        ret, _ = self.cam.read()
                        if ret:
                            self.is_active = True
                            print(f"Cámara {self.id} abierta exitosamente con códec MJPEG.", flush=True)
                            return
                        self.cam.release()
                    except Exception as e:
                        print(f"Advertencia al configurar {self.id} a {ancho_int}x{alto_int}: {e}", flush=True)
                        if self.cam:
                            self.cam.release()
                self.cam = None
                time.sleep(0.5)

            # Workaround Chromebook ISP: si no es la cámara interna y falló,
            # abrir video0 brevemente para "despertar" el subsistema de video
            if self.device_index != 0:
                print(f"DEBUG: Realizando ISP warm-up con video0 para desbloquear {self.id}...", flush=True)
                try:
                    warmup = cv2.VideoCapture(0)
                    if warmup.isOpened():
                        warmup.read()
                        warmup.release()
                    time.sleep(0.5)
                    # Reintentar con la resolución más baja después del warm-up
                    self.cam = cv2.VideoCapture(self.device_index)
                    if self.cam.isOpened():
                        self.cam.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
                        self.cam.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
                        self.cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
                        ret, _ = self.cam.read()
                        if ret:
                            self.is_active = True
                            print(f"Cámara {self.id} abierta exitosamente tras ISP warm-up.", flush=True)
                            return
                        self.cam.release()
                    self.cam = None
                except Exception as e:
                    print(f"DEBUG: ISP warm-up falló para {self.id}: {e}", flush=True)
                    if self.cam:
                        self.cam.release()
                        self.cam = None

            self.is_active = False
            print(f"Error fatal al abrir {self.id} (device {self.device_index}) tras reintentos y warm-up.", flush=True)


    def run(self):
        print(f"Hilo de captura iniciado para {self.id}", flush=True)
        while True:
            with self._lock:
                active = self.is_active
                cam_obj = self.cam
            if active:
                if cam_obj is None:
                    self.start_camera()
                self.process_frame()
            else:
                if cam_obj is not None:
                    self.stop_camera()
            time.sleep(0.01)

    def stop_camera(self):
        with self._lock:
            if self.cam is not None:
                self.cam.release()
                self.cam = None
            self.is_active = False
            self.grabando = False
            self.modo_deteccion = False
            if self.video_writer:
                self.video_writer.release()
                self.video_writer = None
        print(f"Cámara {self.id} detenida.", flush=True)

    def process_frame(self):
        with self._lock:
            if not self.is_active or self.cam is None:
                return
            cam = self.cam
        
        exito, frame = cam.read()
        if not exito:
            return

        frame = cv2.flip(frame, 1)
        self.frame_actual = frame.copy()

        # Lógica de detección
        if self.modo_deteccion:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (21, 21), 0)
            if self.background_frame is None:
                self.background_frame = gray
            else:
                delta = cv2.absdiff(self.background_frame, gray)
                thresh = cv2.threshold(delta, 25, 255, cv2.THRESH_BINARY)[1]
                thresh = cv2.dilate(thresh, None, iterations=2)
                movimiento = cv2.countNonZero(thresh)
                if movimiento > 25000:
                    if not self.grabando:
                        self.grabando = True
                        self.tiempo_inicio_grabacion = time.time()
                        self.frames_grabados = 0
                        enviar_notificacion_telegram(f"⚠️ Movimiento en {self.id}.")
        else:
            self.background_frame = None

        # Lógica de grabación
        if self.grabando:
            if self.video_writer is None:
                if not os.path.exists(CARPETA_CAPTURAS):
                    os.makedirs(CARPETA_CAPTURAS, exist_ok=True)
                codigo = cv2.VideoWriter_fourcc(*'mp4v')
                nombre = datetime.datetime.now().strftime(f"video_{self.id}_%Y%m%d_%H%M%S.mp4")
                ruta = os.path.join(CARPETA_CAPTURAS, nombre)
                h, w = frame.shape[:2]
                self.video_writer = cv2.VideoWriter(ruta, codigo, self.fps_actual, (w, h))
                if not self.video_writer.isOpened():
                    print(f"ERROR: VideoWriter no pudo abrir {ruta}, reintentando...", flush=True)
                    self.video_writer = None
                    return
                self.ruta_grabacion_actual = ruta
                self.frames_grabados = 0
            
            if self.video_writer.write(frame):
                self.frames_grabados += 1
            
            if time.time() - self.tiempo_inicio_grabacion > 10:
                self.grabando = False
                self.video_writer.release()
                self.video_writer = None
                ruta = self.ruta_grabacion_actual
                self.ruta_grabacion_actual = None
                tam = os.path.getsize(ruta) if os.path.exists(ruta) else 0
                if (self.frames_grabados > 5 or tam > 51200) and tam > 1024:
                    enviar_notificacion_telegram(f"📹 Video por movimiento en {self.id} ({tam//1024}KB)")
                    enviar_video_telegram(ruta)
                else:
                    print(f"DEBUG: Grabación auto de {self.id} no enviada: frames={self.frames_grabados}, tamaño={tam}", flush=True)
        elif self.video_writer is not None:
            ruta = self.ruta_grabacion_actual
            self.video_writer.release()
            self.video_writer = None
            self.ruta_grabacion_actual = None
            tam = os.path.getsize(ruta) if os.path.exists(ruta) else 0
            if (self.frames_grabados > 5 or tam > 51200) and tam > 1024:
                enviar_notificacion_telegram(f"📹 Video grabado ({self.id}) — {tam//1024}KB")
                enviar_video_telegram(ruta)
            else:
                print(f"DEBUG: Grabación manual de {self.id} no enviada: frames={self.frames_grabados}, tamaño={tam}", flush=True)
            self.frames_grabados = 0

# Inicialización de sesiones
cameras = {cfg['id']: CameraSession(cfg) for cfg in config.get('cameras', [])}

# Iniciar hilos por cada cámara configurada
for cam_id in cameras:
    hilo = threading.Thread(target=cameras[cam_id].run)
    hilo.daemon = True
    hilo.start()

def generar_frames(cam_id):
    session = cameras.get(cam_id)
    while True:
        if session and session.is_active and session.frame_actual is not None:
            parametros_jpg = [int(cv2.IMWRITE_JPEG_QUALITY), 80]
            ret, buffer = cv2.imencode('.jpg', session.frame_actual, parametros_jpg)
            frame_bytes = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        else:
            time.sleep(0.5)
        time.sleep(0.03)

@app.route('/')
def inicio():
    return render_template('index.html')

@app.route('/video_feed/')
@app.route('/video_feed/<cam_id>')
def video_feed(cam_id=None):
    if cam_id is None:
        cam_id = list(cameras.keys())[0] if cameras else None
    return Response(generar_frames(cam_id), mimetype='multipart/x-mixed-replace; boundary=frame')

def get_or_create_session(cam_id):
    if cam_id in cameras:
        return cameras[cam_id]
    
    # Si no existe, intentar crear dinámicamente si es un videoX
    if cam_id.startswith('video'):
        try:
            index = int(cam_id.replace('video', ''))
            cfg = {'id': cam_id, 'device_index': index, 'ancho': 640, 'alto': 480}
            new_session = CameraSession(cfg)
            cameras[cam_id] = new_session
            # Iniciar su hilo de captura independiente
            hilo = threading.Thread(target=new_session.run)
            hilo.daemon = True
            hilo.start()
            return new_session
        except:
            pass
    return None

@app.route('/toggle_deteccion', methods=['POST'])
def toggle_deteccion():
    datos = request.get_json(silent=True) or {}
    cam_id = datos.get('camera_id') or (list(cameras.keys())[0] if cameras else None)
    session = get_or_create_session(cam_id)
    if session:
        was_motion = session.modo_deteccion
        session.modo_deteccion = not session.modo_deteccion
        if was_motion and not session.modo_deteccion and session.grabando:
            session.grabando = False
        return "activa" if session.modo_deteccion else "desactivada", 200
    return "Cámara no encontrada", 404

@app.route('/toggle_camara', methods=['POST'])
def toggle_camara():
    datos = request.get_json(silent=True) or {}
    cam_id = datos.get('camera_id') or (list(cameras.keys())[0] if cameras else None)
    session = get_or_create_session(cam_id)
    if session:
        if session.is_active:
            session.stop_camera()
            return "apagada", 200
        else:
            session.start_camera()
            return "encendida", 200
    return "Cámara no encontrada", 404

@app.route('/tomar_foto', methods=['POST'])
def tomar_foto():
    datos = request.get_json(silent=True) or {}
    cam_id = datos.get('camera_id') or (list(cameras.keys())[0] if cameras else None)
    session = get_or_create_session(cam_id)
    if session and session.is_active and session.frame_actual is not None:
        nombre_archivo = datetime.datetime.now().strftime(f"foto_{cam_id}_%Y%m%d_%H%M%S.jpg")
        ruta_completa = os.path.join(CARPETA_CAPTURAS, nombre_archivo)
        cv2.imwrite(ruta_completa, session.frame_actual)
        enviar_foto_telegram(ruta_completa)
        return "Foto guardada", 200
    return "Error", 400

@app.route('/toggle_video', methods=['POST'])
def toggle_video():
    datos = request.get_json(silent=True) or {}
    cam_id = datos.get('camera_id') or (list(cameras.keys())[0] if cameras else None)
    session = get_or_create_session(cam_id)
    if session and session.is_active:
        session.grabando = not session.grabando
        if session.grabando:
            session.tiempo_inicio_grabacion = time.time()
            session.frames_grabados = 0
        return "grabando" if session.grabando else "detenido", 200
    return "Error", 400

@app.route('/set_resolucion', methods=['POST'])
def set_resolucion():
    datos = request.get_json(silent=True) or {}
    cam_id = datos.get('camera_id') or (list(cameras.keys())[0] if cameras else None)
    session = get_or_create_session(cam_id)
    if session:
        session.config_ancho = int(datos.get('ancho', 640))
        session.config_alto = int(datos.get('alto', 480))
        if session.is_active:
             session.stop_camera()
             session.start_camera()
        return "Resolución actualizada", 200
    return "Cámara no encontrada", 404

@app.route('/listar_camaras', methods=['GET'])
def listar_camaras():
    index_to_config_id = {session.device_index: cam_id for cam_id, session in cameras.items()}
    dispositivos_finales = []
    processed_buses = {} # bus_path -> index

    # 1. Añadir configuradas primero (tienen prioridad)
    for cam_id, session in cameras.items():
        dispositivos_finales.append(cam_id)
        dev_path = f'/sys/class/video4linux/video{session.device_index}'
        if os.path.exists(dev_path):
            real_path = os.path.realpath(dev_path)
            parent = '/'.join(real_path.split('/')[:-2])
            processed_buses[parent] = session.device_index
    
    # 2. Añadir físicas no configuradas
    for i in range(10):
        dev_path = f'/sys/class/video4linux/video{i}'
        if os.path.exists(dev_path):
            real_path = os.path.realpath(dev_path)
            parent = '/'.join(real_path.split('/')[:-2])
            
            if parent not in processed_buses:
                # Test de salud
                cap = cv2.VideoCapture(i)
                if cap.isOpened():
                    ret, _ = cap.read()
                    if ret:
                        # Si tiene nombre configurado, usarlo, si no, usar videoX
                        nombre = index_to_config_id.get(i, f"video{i}")
                        if nombre not in dispositivos_finales:
                            dispositivos_finales.append(nombre)
                            processed_buses[parent] = i
                    cap.release()
            
    return {"camaras": dispositivos_finales}, 200

@app.route('/status/<cam_id>', methods=['GET'])
def get_status(cam_id):
    session = cameras.get(cam_id)
    if session:
        return {"active": session.is_active, "recording": session.grabando, "motion": session.modo_deteccion}, 200
    return "Cámara no encontrada", 404

@app.route('/set_camara', methods=['POST'])
def set_camara():
    # Esta ruta ya no es estrictamente necesaria para cambiar la cámara en el backend
    # pero el frontend la llama. Podemos dejarla vacía o simplemente responder OK.
    return "OK", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, threaded=True)
