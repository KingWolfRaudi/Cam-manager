from flask import Flask, render_template, Response, request
import cv2
import datetime
import time
import threading # <-- NUEVA LIBRERÍA para manejar procesos en segundo plano

app = Flask(__name__)

# --- VARIABLES GLOBALES ---
frame_actual = None # Aquí guardaremos la foto más reciente para que todos la vean
ultimo_frame_guardado = None
grabando = False
video_writer = None
resolucion_ancho = 640
resolucion_alto = 480
actualizar_camara = False

# --- NUEVO HILO EN SEGUNDO PLANO ---
# Esta función se ejecutará eternamente separada de la web, controlando la cámara física
def capturar_camara_fondo():
    global frame_actual, ultimo_frame_guardado, grabando, video_writer, resolucion_ancho, resolucion_alto, actualizar_camara
    
    camara = cv2.VideoCapture(0)
    camara.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    camara.set(cv2.CAP_PROP_FRAME_WIDTH, resolucion_ancho)
    camara.set(cv2.CAP_PROP_FRAME_HEIGHT, resolucion_alto)
    
    while True:
        if actualizar_camara:
            camara.set(cv2.CAP_PROP_FRAME_WIDTH, resolucion_ancho)
            camara.set(cv2.CAP_PROP_FRAME_HEIGHT, resolucion_alto)
            actualizar_camara = False

        exito, frame = camara.read()
        if exito:
            frame = cv2.flip(frame, 1)
            
            # Guardamos la imagen en nuestra variable compartida
            frame_actual = frame.copy()
            ultimo_frame_guardado = frame.copy()
            
            # Grabación de video independiente de los usuarios conectados
            if grabando:
                if video_writer is None:
                    codigo_video = cv2.VideoWriter_fourcc(*'mp4v')
                    nombre_video = datetime.datetime.now().strftime("capturas/video_%Y%m%d_%H%M%S.mp4")
                    video_writer = cv2.VideoWriter(nombre_video, codigo_video, 20.0, (resolucion_ancho, resolucion_alto))
                video_writer.write(frame)
            else:
                if video_writer is not None:
                    video_writer.release()
                    video_writer = None
                    
        time.sleep(0.01) # Pequeña pausa para no quemar el procesador

# --- RUTAS DE LA APLICACIÓN WEB ---

def generar_frames():
    global frame_actual
    while True:
        # Los usuarios simplemente leen el frame_actual que produce el hilo de fondo
        if frame_actual is not None:
            parametros_jpg = [int(cv2.IMWRITE_JPEG_QUALITY), 80]
            ret, buffer = cv2.imencode('.jpg', frame_actual, parametros_jpg)
            frame_bytes = buffer.tobytes()
            
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        
        time.sleep(0.03) # Equivalente a ~30FPS para los usuarios web

@app.route('/')
def inicio():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    return Response(generar_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/tomar_foto', methods=['POST'])
def tomar_foto():
    global ultimo_frame_guardado
    if ultimo_frame_guardado is not None:
        nombre_foto = datetime.datetime.now().strftime("capturas/foto_%Y%m%d_%H%M%S.jpg")
        cv2.imwrite(nombre_foto, ultimo_frame_guardado)
        return "Foto guardada", 200
    return "Error", 500

@app.route('/toggle_video', methods=['POST'])
def toggle_video():
    global grabando
    grabando = not grabando 
    if grabando:
        return "grabando", 200
    else:
        return "detenido", 200

@app.route('/set_resolucion', methods=['POST'])
def set_resolucion():
    global resolucion_ancho, resolucion_alto, actualizar_camara
    datos = request.get_json()
    resolucion_ancho = int(datos['ancho'])
    resolucion_alto = int(datos['alto'])
    actualizar_camara = True
    return "Resolución actualizada", 200

if __name__ == '__main__':
    # Iniciamos el hilo de la cámara antes de arrancar el servidor web
    hilo = threading.Thread(target=capturar_camara_fondo)
    hilo.daemon = True # Esto hace que el hilo se cierre automáticamente si apagamos el servidor
    hilo.start()
    
    app.run(host='0.0.0.0', port=5000, threaded=True)