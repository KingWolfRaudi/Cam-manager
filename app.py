from flask import Flask, render_template, Response, request
import cv2
import datetime
import time
import threading
import os # <-- Imprescindible para manejar las rutas absolutas

app = Flask(__name__)

# --- CONFIGURACIÓN DE CARPETA ---
# Ruta absoluta para que el demonio de Ubuntu sepa exactamente dónde guardar
CARPETA_CAPTURAS = '/mnt/sd/Cam-capturas'

# Si la carpeta no existe, Python la creará automáticamente al iniciar
if not os.path.exists(CARPETA_CAPTURAS):
    os.makedirs(CARPETA_CAPTURAS)

# --- VARIABLES GLOBALES ---
frame_actual = None
ultimo_frame_guardado = None
grabando = False
video_writer = None
resolucion_ancho = 640
resolucion_alto = 480
actualizar_camara = False
camara_activa = False

def capturar_camara_fondo():
    global frame_actual, ultimo_frame_guardado, grabando, video_writer, resolucion_ancho, resolucion_alto, actualizar_camara, camara_activa
    
    camara = None 
    
    while True:
        if camara_activa:
            if camara is None:
                camara = cv2.VideoCapture(0)
                camara.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                camara.set(cv2.CAP_PROP_FRAME_WIDTH, resolucion_ancho)
                camara.set(cv2.CAP_PROP_FRAME_HEIGHT, resolucion_alto)
            
            if actualizar_camara:
                camara.set(cv2.CAP_PROP_FRAME_WIDTH, resolucion_ancho)
                camara.set(cv2.CAP_PROP_FRAME_HEIGHT, resolucion_alto)
                actualizar_camara = False

            exito, frame = camara.read()
            if exito:
                frame = cv2.flip(frame, 1)
                frame_actual = frame.copy()
                ultimo_frame_guardado = frame.copy()
                
                if grabando:
                    if video_writer is None:
                        codigo_video = cv2.VideoWriter_fourcc(*'mp4v')
                        # Guardamos el video en la ruta absoluta
                        nombre_archivo = datetime.datetime.now().strftime("video_%Y%m%d_%H%M%S.mp4")
                        ruta_completa = os.path.join(CARPETA_CAPTURAS, nombre_archivo)
                        video_writer = cv2.VideoWriter(ruta_completa, codigo_video, 20.0, (resolucion_ancho, resolucion_alto))
                    video_writer.write(frame)
                else:
                    if video_writer is not None:
                        video_writer.release()
                        video_writer = None
        else:
            if camara is not None:
                camara.release()
                camara = None
                frame_actual = None
                
                if grabando:
                    grabando = False
                    if video_writer is not None:
                        video_writer.release()
                        video_writer = None
                        
        time.sleep(0.01)

def generar_frames():
    global frame_actual, camara_activa
    while True:
        if camara_activa and frame_actual is not None:
            parametros_jpg = [int(cv2.IMWRITE_JPEG_QUALITY), 80]
            ret, buffer = cv2.imencode('.jpg', frame_actual, parametros_jpg)
            frame_bytes = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        else:
            time.sleep(0.5)
            
        time.sleep(0.03)

@app.route('/')
def inicio():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    return Response(generar_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/toggle_camara', methods=['POST'])
def toggle_camara():
    global camara_activa
    camara_activa = not camara_activa
    return "encendida" if camara_activa else "apagada", 200

@app.route('/tomar_foto', methods=['POST'])
def tomar_foto():
    global ultimo_frame_guardado, camara_activa
    if not camara_activa:
        return "Cámara apagada", 400
    if ultimo_frame_guardado is not None:
        # Guardamos la foto en la ruta absoluta
        nombre_archivo = datetime.datetime.now().strftime("foto_%Y%m%d_%H%M%S.jpg")
        ruta_completa = os.path.join(CARPETA_CAPTURAS, nombre_archivo)
        cv2.imwrite(ruta_completa, ultimo_frame_guardado)
        return "Foto guardada", 200
    return "Error", 500

@app.route('/toggle_video', methods=['POST'])
def toggle_video():
    global grabando, camara_activa
    if not camara_activa:
        return "Cámara apagada", 400
    
    grabando = not grabando 
    return "grabando" if grabando else "detenido", 200

@app.route('/set_resolucion', methods=['POST'])
def set_resolucion():
    global resolucion_ancho, resolucion_alto, actualizar_camara
    datos = request.get_json()
    resolucion_ancho = int(datos['ancho'])
    resolucion_alto = int(datos['alto'])
    actualizar_camara = True
    return "Resolución actualizada", 200

if __name__ == '__main__':
    hilo = threading.Thread(target=capturar_camara_fondo)
    hilo.daemon = True
    hilo.start()
    app.run(host='0.0.0.0', port=5000, threaded=True)